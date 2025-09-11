import json5
import logging
from math import sqrt
import simpy
from skyfield.api import EarthSatellite
from collections import OrderedDict
from user_based_topology import getSystemFromSat
from Task import Task
import globals


# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

BATMAN = config["Routing_algorithm"]["BATMAN"]
GREEDY = config["Routing_algorithm"]["GREEDY"]

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

total_time = 0  # Imposta il valore iniziale di total_time


class EdgeServer:
    def __init__(self, env, name, satellite: EarthSatellite, orbitalSunset, is_acc_point, elev_angle):
        '''
        Initialize an EdgeServer instance.

        :param env: Simulation environment.
        :param name: Name of the edge server.
        '''

        self.env = env
        self.name = name
        self.satellite = satellite
        self.orbitalSunset = orbitalSunset
        self.is_acc_point = is_acc_point
        self.elev_angle = elev_angle
        self.neighbors = {}
        self.latency = {}
        self.bandwidth = {}

        # Code classiche come in precedenza (non verrà più utilizzata)
        self.process_queue = simpy.PriorityResource(env, capacity=5)
        self.server_queue = []

        # Nuove code CPU + NET per modello a 2 stadi
        self.cpu_dev = simpy.PriorityResource(env, capacity=5)
        self.net_dev = simpy.PriorityResource(env, capacity=5)
        self.queue_cpu = []
        self.queue_net = []
        self.cpu_busy_until = 0.0
        self.net_busy_until = 0.0

        self.utility_value = 0
        self.completed_tasks = []
        self.energy = config.get("initial_energy", 10000.0)  # J (valore più alto)

        self.tasks = []  # Lista task da Spedire
        self.dead_tasks = []  # Lista dei Task Morti (TTL = 0)
        self.OGMs_position = {}  # Dizionario delle posizioni dei vicini

        self.ogm_sequence = 0
        self.OGMs = []
        self.OGMs_NP = []
        self.ogm_table = {}
        self.OGMs_History = OrderedDict()
        self.OGMs_History_dim = 2046

    # --------------------------------------------------
    # Gestione Energetica
    # --------------------------------------------------
    def compute_routing_energy(self, file_size, bandwidth, Ptrasm=1.0):
        """
        Energia di routing (trasmissione) [Joule].
        file_size in Byte, bandwidth in Byte/s
        """
        if bandwidth and bandwidth > 0:
            return Ptrasm * (file_size / bandwidth)
        return 0.0

    def compute_execution_energy(self, execution_time, C_sen, e=5e-26):
        """
        Energia di computazione [Joule].
        execution_time ~ domanda di servizio (s)
        C_sen ~ capacità CPU in cicli/s
        """
        d = execution_time
        return d * e * (C_sen ** 3)

    # Wrapper dedicati a CPU e NET
    def eps_cpu(self, d_cpu_s, C_sen):
        return self.compute_execution_energy(d_cpu_s, C_sen)

    def eps_net(self, bytes_out, bw_Bps):
        P = config.get("Ptrasm", 1.0)
        return P * (bytes_out / bw_Bps) if bw_Bps > 0 else float('inf')

    # --------------------------------------------------
    # Waiting time (W^cpu, W^net)
    # --------------------------------------------------
    def _remaining(self, busy_until, now):
        return max(0.0, busy_until - now)

    def W_cpu(self, now):
        sum_q = sum(d for (_id, d, _prio, _t) in self.queue_cpu)
        rem = 0.5 * self._remaining(self.cpu_busy_until, now) if self.cpu_dev.count > 0 else 0.0
        return sum_q + rem

    def W_net(self, now):
        sum_q = sum(d for (_id, d, _prio, _t) in self.queue_net)
        rem = 0.5 * self._remaining(self.net_busy_until, now) if self.net_dev.count > 0 else 0.0
        return sum_q + rem

    # --------------------------------------------------
    # Pipeline CPU -> NET
    # --------------------------------------------------
    def process_locally(self, env, task_id, prio, d_cpu_s, d_net_bytes,
                        deadline, bw_to_obs_Bps, lat_to_obs_s, C_sen):
        """
        Simula l’esecuzione di un task sul server (CPU -> NET).
        """
        # 1) Ammissione
        Wc = self.W_cpu(env.now)
        Wn = self.W_net(env.now)
        d_net_svc = (d_net_bytes / bw_to_obs_Bps) + (lat_to_obs_s or 0.0)
        R = Wc + Wn + d_cpu_s + d_net_svc
        eps = self.eps_cpu(d_cpu_s, C_sen) + self.eps_net(d_net_bytes, bw_to_obs_Bps)

        if (deadline is not None and R > deadline) or (self.energy < eps) \
                or (self.orbitalSunset and (env.now + R) > self.orbitalSunset):
            return False, R, eps

        # 2) Enqueue
        if d_cpu_s > 0:
            self.queue_cpu.append((task_id, d_cpu_s, prio, env.now))
        if d_net_bytes > 0:
            self.queue_net.append((task_id, d_net_svc, prio, env.now))

        # 3) CPU stage
        if d_cpu_s > 0:
            with self.cpu_dev.request(priority=prio) as req:
                yield req
                self.queue_cpu = [x for x in self.queue_cpu if x[0] != task_id]
                self.cpu_busy_until = env.now + d_cpu_s
                yield env.timeout(d_cpu_s)
                self.cpu_busy_until = env.now
                self.energy -= self.eps_cpu(d_cpu_s, C_sen)

        # 4) NET stage
        if d_net_bytes > 0:
            with self.net_dev.request(priority=prio) as req:
                yield req
                self.queue_net = [x for x in self.queue_net if x[0] != task_id]
                t_tx = (d_net_bytes / bw_to_obs_Bps) + (lat_to_obs_s or 0.0)
                self.net_busy_until = env.now + t_tx
                yield env.timeout(t_tx)
                self.net_busy_until = env.now
                self.energy -= self.eps_net(d_net_bytes, bw_to_obs_Bps)

        return True, R, eps

    def task_completed(self, task_id, task_priority, arrival_time_system, arrival_time_task_queue,
                       start_time, end_time, execution_time, service_time, time_in_queue,
                       selected_server, num_hops, lunghezza_coda, original_TaskPriority,
                       estimated_execution_time, transfer_time, utility,
                       TMAX_exceeded, exec_after_set,
                       eps_cpu=0.0, eps_net=0.0):
        '''
        Record completed tasks, including energy metrics (CPU + NET).
        '''
        if self.elev_angle < config["Phi_max"]:
            exec_after_set = True

        total_energy = eps_cpu + eps_net
        self.completed_tasks.append(
            (task_id, task_priority, arrival_time_system, arrival_time_task_queue,
             start_time, end_time, execution_time, service_time, time_in_queue,
             selected_server, num_hops, lunghezza_coda, original_TaskPriority,
             estimated_execution_time, transfer_time, utility,
             TMAX_exceeded, exec_after_set, eps_cpu, eps_net, total_energy)
        )

        print(f"[Task {task_id}] COMPLETED on {self.name} | "
              f"CPU={eps_cpu:.4f}J, NET={eps_net:.4f}J, TOTAL={total_energy:.4f}J, "
              f"Remaining={self.energy:.2f}J")

    def add_neighbor(self, neighbor_server, hop_count, latency, bandwidth):
        '''
                Add a neighbor server with its hop count and latency.

                :param neighbor_server: Neighbor server to add.
                :param hop_count: Number of hops to reach the neighbor server.
                :param latency: Latency to the neighbor server.

                :return: None
                '''
        self.neighbors[neighbor_server] = hop_count
        self.latency[neighbor_server] = latency
        self.bandwidth[neighbor_server] = bandwidth

    def update_neighbors(self, new_neighbors, new_latency, new_bandwidth):
        """
        Update the neighbors, latency, and bandwidth of the edge server.

        :param new_neighbors: Dictionary of new neighbors and their hop counts.
        :param new_latency: Dictionary of new latencies to the neighbors.
        :param new_bandwidth: Dictionary of new bandwidths to the neighbors.

        :return: None
        """
        self.neighbors = new_neighbors
        self.latency = new_latency
        self.bandwidth = new_bandwidth

    def get_neighbors(self):
        '''
        Get neighbor servers at a distance of one hop.

        :return: List of neighbor servers at a distance of one hop.
        '''
        neighbors_at_distance_one = []

        for neighbor, hop_count in self.neighbors.items():
            if hop_count <= 1:
                neighbors_at_distance_one.append(neighbor)

        return neighbors_at_distance_one

    def get_satellite(self):
        return self.satellite

    def get_latency(self, neighbor_server):
        '''
        Get latency to a specific neighbor server.

        :param neighbor_server: Neighbor server to get the latency for.

        :return: Latency to the neighbor server.
        '''
        return self.latency.get(neighbor_server, None)

    def get_bandwidth(self, neighbor_server):
        '''
        Get bandwidth to a specific neighbor server.

        :param neighbor_server: Neighbor server to get the bandwidth for.

        :return: Bandwidth to the neighbor server.
        '''
        return self.bandwidth.get(neighbor_server, None)

    def __str__(self):
        return f"Satellite :{self.name}\n\telev:{self.elev_angle}\n\tis_AP:{self.is_acc_point}"

    def getPositionVector(self, t):
        """
        Questa funzione ritorna un vettore in 3 dimensioni,
        rappresenta la posizione del satellite in un determinato istante.
        """

        return getSystemFromSat(self.satellite, t, True).position.km.tolist()

    def greedy_approach(self, env, task):
        destination_pos = self.OGMs_position[task.dest_node][1]  # Posizione della destinazione
        ranked_neighbors = []

        for server in self.neighbors:
            ogm_data = self.OGMs_position.get(server.name)
            if ogm_data:

                dist = get_pos_proximity(destination_pos, ogm_data[1])
                ## t = (server, vect, dist_from_dest, isAP)
                t = (server, ogm_data[1], dist, ogm_data[2])
                ranked_neighbors.append(t)
            else:
                continue
        ranked_neighbors.sort(key=lambda x: (not x[3], x[2]))
        # [print(f"[{t[0].name}] \t| D_from_Dest : {t[2]} \tAP: {t[3]}") for t in ranked_neighbors]

        best_server = None
        for neighbor_tuple in ranked_neighbors:
            if neighbor_tuple[0].name not in task.visited:
                best_server = neighbor_tuple[0]
                break

        if best_server:
            # print(f"--> BEST SERVER: {best_server.name}")
            yield from sendTask(env, task, self, best_server, 'GREEDY')

        # else:
        #     print(f"{self.name} Non ha Vicini al quale mandare il Task {task.id}")
        #     print(f"Miei vicini : {len(self.neighbors)}")
        #     print(f"Sono un access Point? {self.is_acc_point}")
        #     print("Vedo se uno dei miei vicini è un access point")
        #     [print(f"\t{a.name} : ap? {a.is_acc_point} dist: {get_pos_proximity(destination_pos, a.getPositionVector(globals.instant_in_configuration))}") for a in self.neighbors]

    def deliver_to_Observer(self, env, mode, task):
        print(f"[MODE: {mode}]")
        task.routingEndTime = env.now
        yield from sendTask(env, task, self, globals.observer, 'DIRECT')

    def forward_packet(self, env):
        if len(self.neighbors) > 0:
            for task in self.tasks:

                if not task.arrived:
                    if config["AP_routing_bidirectional"]:
                        # Bidirezionale, mandiamo il task verso gli access Point
                        if self.is_acc_point:
                            yield from self.deliver_to_Observer(env, 'BIDIRECTIONAL', task)
                            continue
                    else:
                        # Controllo che il satellite sia nella Dome
                        if self.elev_angle >= 40:
                            yield from self.deliver_to_Observer(env, 'MONODIRECTIONAL', task)
                            continue

                    # ! Algorithm
                    max_neighbor = None
                    if BATMAN:
                        max_neighbor, max_value = find_OGM_intersection(
                            self.ogm_table[task.dest_node], self.neighbors, task
                        )
                    # Se entrambi attivi: prova BATMAN, altrimenti passa a GREEDY
                    if BATMAN and GREEDY:
                        if max_neighbor:
                            yield from sendTask(env, task, self, max_neighbor, 'BATMAN')
                        else:
                            yield from self.greedy_approach(env, task)

                    elif BATMAN:
                        if max_neighbor:
                            yield from sendTask(env, task, self, max_neighbor, 'BATMAN')

                    elif GREEDY:
                        yield from self.greedy_approach(env, task)

        # else:
        # print(f"{self.name} NON HA PIù VICINI AI QUALI TRASMETTERE elev: {self.elev_angle}°")
        # print("Task IDs:", [task.id for task in self.tasks])

    def UpdateUtilityValue(self, env, estimated_execution_time, transfer_time,
                           restart_time, download_time, server, task_priority):
        '''
        Aggiorna il valore di utilità del server in base alle code CPU/NET reali.
        '''
        now = env.now

        # Nuovo: waiting times reali da code CPU/NET
        Wc = self.W_cpu(now)
        Wn = self.W_net(now)

        #  Penalizzazione per sunset
        if server.orbitalSunset is not None and server.orbitalSunset > 0:
            sunset_penalty = 1 / server.orbitalSunset
        else:
            sunset_penalty = float('inf')

        # Tempo complessivo: CPU demand stimata + overhead (download, restart, transfer)
        total_demand = estimated_execution_time + transfer_time + restart_time + download_time

        # Utility in base al tipo di task
        if task_priority == 1:  # alta priorità → focus CPU
            self.utility_value = Wc + total_demand  # + sunset_penalty se vuoi enfatizzarlo
        elif task_priority == 100:  # bassa priorità → focus CPU+NET
            self.utility_value = Wc + Wn + total_demand
        else:  # default
            self.utility_value = Wc + Wn + total_demand

        # Debug
        print(f"[Utility] {self.name} | Wc={Wc:.2f}, Wn={Wn:.2f}, "
              f"total_demand={total_demand:.2f}, utility={self.utility_value:.2f}")


def getTransmissionTime(bandwidht, weight, latency):
    return (weight/bandwidht) + latency

def sendTask(env, task, sender, receiver, algorithm):

    """
    Transfers a task from a sender satellite to a receiver satellite, updating its state and attributes.

    Args:
        task (Task): The task object to be transferred. It contains attributes such as `hop`, `ttl`, 
                     `id`, `current_server`, and `satellite_destination`.
        sender (Satellite): The satellite currently holding the task. It must have a `remove_task` method.
        receiver (Satellite): The satellite to which the task is being sent. It must have an `add_task` method.

    Behavior:
        - Increments the `hop` count of the task by 1 to track the number of hops.
        - Decrements the `ttl` (time-to-live) of the task by 1 to reflect its remaining lifespan.
        - Removes the task from the sender using `sender.remove_task(task.id)`.
        - Adds the task to the receiver using `receiver.add_task(task)`.
        - Updates the `current_server` attribute of the task to the receiver.
        - Checks if the receiver is the task's `satellite_destination`. If so, marks the task as arrived by 
          setting `task.arrived` to `True`.
        - Logs the transfer operation in the format: "[task.id] sender.name -> receiver.name".

    Note:
        This function assumes that the `task`, `sender`, and `receiver` objects are properly defined and 
        implement the required attributes and methods.
    """
    if task.ttl > 0:
        # Gestione dell'attesa nell'env
        if receiver.name != 'OBS':
            bandwidth = sender.bandwidth[receiver] * (1024**2)  # da MB/s a Byte/s
            trasmission_time = getTransmissionTime(bandwidth, task.weight, sender.latency[receiver])
            print(f"[{task.id}][{algorithm}] {sender.name} -> {receiver.name} | Tramission-time: {trasmission_time}")

            energy_tx = sender.compute_routing_energy(task.weight, bandwidth)
            sender.energy -= energy_tx
            print(
                f"[{task.id}] Energy routing consumed by {sender.name}: {energy_tx:.6f} J (remaining {sender.energy:.2f})")


        else:
            bandwidth = 10000 * (1024**2)  # da MB/s a Byte/s
            trasmission_time = getTransmissionTime(bandwidth, task.weight, 0)
            print(f"[{task.id}][{algorithm}] CONSEGNATO! {sender.name} -> {receiver.name} | Tramission-time: {trasmission_time}")

        yield env.timeout(trasmission_time)

        task.hop += 1
        task.ttl -= 1   
        
        task.add_algorithm(algorithm)   # Contiamo quale algoritmo abbiamo usato

        # Rimuoviamo il task dal Sender
        sender.tasks.remove(task)
        # Inviamo il task al Receiver
        receiver.tasks.append(task)
        #print(f"{sender.name} -> {receiver.name}")
        # Modifichiamo le informazioni sul task
        task.current_node = receiver.name

        # ! USIAMO SOLO I NOMI E NON PROPRIO L'oggetto
        if task.dest_node == receiver.name:
            task.arrived = True
            task.label = 'TASK_ARRIVED'

        task.hop_History.append(receiver.name)     # Aggiorno la History
        task.visited.add(receiver.name)            # Aggiorno i visitati

    else:
        # Rimuoviamo il task
        print(f"[{task.id}] RIMOZIONE TASK DA {sender.name}, TTL finito")
        task.label = 'TTL_EXPIRED'
        sender.dead_tasks.append(task)
        sender.tasks.remove(task)

def find_OGM_intersection(ogm_table, neighbors, task):
    """
    Trova l'intersezione tra i vicini reali e quelli presenti nella tabella OGM,
    escludendo i satelliti già visitati dal task, e restituisce il vicino con il valore OGM più alto.

    Args:
        ogm_table (dict): Dizionario che mappa i nomi dei vicini ai valori OGM.
        neighbors (dict): Dizionario vicini.
        task (Task): Oggetto task che contiene l'insieme dei satelliti già visitati.

    Returns:
        tuple: (max_neighbor, max_value)
            - max_neighbor: Il vicino con il valore OGM più alto (oggetto neighbor).
            - max_value: Il valore OGM associato a max_neighbor.
            Se non ci sono vicini validi, entrambi sono None.
    """
    # Costruisce un dizionario di vicini che sono sia nella tabella OGM sia tra i vicini reali,
    # escludendo quelli già visitati dal task (per evitare loop).
    intersection = {
        neighbor: ogm_table[neighbor.name]
        for neighbor in neighbors
        if (
            neighbor.name in ogm_table
            and neighbor.name not in task.visited  # filtro anti-loop
        )
    }

    # Trova il vicino con il valore OGM più alto nell'intersezione.
    max_neighbor, max_value = None, None
    if intersection:  # Evita ValueError se intersection è vuoto
        max_neighbor, max_value = max(
            intersection.items(), key=lambda item: item[1])

    return max_neighbor, max_value

def get_pos_proximity(pos1, pos2):
    """
    Calcola la distanza fra due punti in uno spazio tridimensionale
    Args:
        pos1: Vettore posizionale dell'obj1
        pos2: Vettore posizionale dell'obj2
    :return: lunghezza del segmento obj1 -> obj2
    """
    # Extraction of coordinate components
    x1, y1, z1 = pos1
    x2, y2, z2 = pos2

    # Calculate the Euclidean distance
    return sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

def build_task_csv_path(folder, at, cpu):
    csv_routing_task = ""
    if BATMAN and GREEDY:
        csv_routing_task = f"{folder}/BATMAN_GREEDY_AT_{at}_CPU_{cpu}.csv"
    elif BATMAN:
        csv_routing_task = f"{folder}/BATMAN_AT_{at}_CPU_{cpu}.csv"
    elif GREEDY:
        csv_routing_task = f"{folder}/GREEDY_AT_{at}_CPU_{cpu}.csv"
    return csv_routing_task