import json5
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
        self.completed_tasks = []
        self.cpu_busy_until = 0.0
        self.net_busy_until = 0.0

        # Nuove code CPU + NET per modello a 2 stadi
        cpu_capacity = config.get("cpu_capacity_queue", 5)
        net_capacity = config.get("net_capacity_queue", 5)
        self.cpu_dev = simpy.Resource(env, capacity=cpu_capacity)
        self.net_dev = simpy.Resource(env, capacity=net_capacity)
        self._cpu_capacity = cpu_capacity
        self._net_capacity = net_capacity

        self.energy_reserved = 0.0

        self.rejected_tasks = []  # Lista per i task scartati
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

    def export_state(self, env):
        """
        Esporta lo stato corrente del satellite come dizionario, recuperando
        i dettagli del task direttamente dagli eventi di richiesta di SimPy.
        """
        ENABLE_MONITORING = config.get("enable_queue_monitoring", False)

        # Recupera i dettagli dei task in coda CPU
        if ENABLE_MONITORING:
            tasks_in_cpu_queue = []
            for req in self.cpu_dev.queue:
                # Controlla se l'attributo 'task_data' è stato allegato
                if hasattr(req, 'task_data'):
                    task_obj = req.task_data
                    tasks_in_cpu_queue.append({
                        "task_id": task_obj.id,
                        "d_cpu": task_obj.d_cpu,
                        "deadline": task_obj.deadline,
                    })

            # Recupera i dettagli dei task in coda NET
            tasks_in_net_queue = []
            for req in self.net_dev.queue:
                if hasattr(req, 'task_data'):
                    task_obj = req.task_data
                    tasks_in_net_queue.append({
                        "task_id": task_obj.id,
                        "d_net": task_obj.d_net,  # Assumi che 'd_net' sia un attributo di Task
                        "deadline": task_obj.deadline,
                    })

            state = {
                "time": env.now,
                "satellite": self.name,
                "in_listening_dome": self.elev_angle >= 40,
                "elev_angle": self.elev_angle,
                "energy_budget": self.energy,
                "neighbors": [n.name for n in self.get_neighbors()],
                "queue_cpu_len": len(self.cpu_dev.queue),
                "queue_net_len": len(self.net_dev.queue),
                "queue_cpu": tasks_in_cpu_queue,
                "queue_net": tasks_in_net_queue
            }
            return state

    def record_rejected_task(self, task_id, task_type, arrival_time_system, rejection_reason ):
        """
        Registra un task scartato con la motivazione del rifiuto.
        """
        self.rejected_tasks.append(
            (task_id, task_type, arrival_time_system, rejection_reason )
        )
        print(f"[Task {task_id}] REJECTED on {self.name} due to: {rejection_reason}")

    def task_completed(self, task_id, task_type, arrival_time_system, arrival_time_task_queue,
                       start_time, end_time, execution_time, service_time, time_in_queue,
                       selected_server, num_hops, lunghezza_coda, estimated_execution_time, transfer_time,
                       TMAX_exceeded, exec_after_set,
                       eps_cpu=0.0, eps_net=0.0):
        '''
        Record completed tasks, including energy metrics (CPU + NET) and task type.
        '''

        # Calcola l'energia totale all'inizio della funzione per evitare l'errore
        total_energy = eps_cpu + eps_net

        if self.elev_angle < config["Phi_max"]:
            exec_after_set = True

        self.completed_tasks.append(
            (task_id,  task_type, arrival_time_system, arrival_time_task_queue,
             start_time, end_time, execution_time, service_time, time_in_queue,
             selected_server, num_hops, lunghezza_coda,
             estimated_execution_time, transfer_time,
             TMAX_exceeded, exec_after_set, eps_cpu, eps_net, total_energy, self.energy)
        )

        print(f"[Task {task_id}] COMPLETED on {self.name} {self.elev_angle} degrees | "
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

    # --------------------------------------------------
    # Waiting time (W^cpu, W^net)
    # --------------------------------------------------

    def _get_min_remaining(self, resource, kind='cpu'):
        """
        Ritorna il tempo minimo residuo tra i task in servizio (tempo fino al primo rilascio).
        Se ci sono slot liberi, ritorna 0.0.
        """
        now = self.env.now
        if len(resource.users) < resource.capacity:
            return 0.0

        min_remaining = float('inf')
        for user in resource.users:
            if hasattr(user, 'task_data'):
                td = user.task_data
                if kind == 'cpu':
                    d = getattr(td, 'd_cpu', None)
                    start = getattr(td, 'start_time_cpu', None)
                    legacy_busy_until = getattr(self, 'cpu_busy_until', None)
                else:
                    d = getattr(td, 'd_net', None)
                    start = getattr(td, 'start_time_net', None)
                    legacy_busy_until = getattr(self, 'net_busy_until', None)

                if d is None:
                    continue

                if start is not None:
                    remaining = max(0.0, d - (now - start))
                else:
                    # fallback su busy_until se disponibile, altrimenti assumiamo d come upper bound
                    if legacy_busy_until is not None:
                        remaining = max(0.0, legacy_busy_until - now)
                    else:
                        remaining = d

                min_remaining = min(min_remaining, remaining)

        return min_remaining if min_remaining != float('inf') else 0.0
    def _get_running_remaining_total(self, resource, kind='cpu'):
        """
        Somma del tempo residuo dei task attualmente in esecuzione (tutti i server).
        Serve per calcolare il lavoro totale in corso.
        """
        now = self.env.now
        running_sum = 0.0
        for user in resource.users:
            if hasattr(user, 'task_data'):
                td = user.task_data
                if kind == 'cpu':
                    d = getattr(td, 'd_cpu', None)
                    start = getattr(td, 'start_time_cpu', None)
                    legacy_busy_until = getattr(self, 'cpu_busy_until', None)
                else:
                    d = getattr(td, 'd_net', None)
                    start = getattr(td, 'start_time_net', None)
                    legacy_busy_until = getattr(self, 'net_busy_until', None)

                if d is None:
                    continue

                if start is not None:
                    remaining = max(0.0, d - (now - start))
                else:
                    if legacy_busy_until is not None:
                        remaining = max(0.0, legacy_busy_until - now)
                    else:
                        remaining = 0.5 * d  # fallback conservativo

                running_sum += remaining

        return running_sum

    def W_cpu(self):
        queue_sum = self._get_queue_demand_sum(self.cpu_dev.queue, kind='cpu')
        min_rem = self._get_min_remaining(self.cpu_dev, kind='cpu')
        running_total = self._get_running_remaining_total(self.cpu_dev, kind='cpu')
        capacity = max(1, getattr(self, '_cpu_capacity', 1))

        work_tot = running_total + queue_sum
        # lavoro residuo dopo il primo intervallo min_rem (durante min_rem i c server producono c*min_rem lavoro)
        work_after_first = max(0.0, work_tot - capacity * min_rem)
        return min_rem + (work_after_first / capacity)

    def W_net(self):
        queue_sum = self._get_queue_demand_sum(self.net_dev.queue, kind='net')
        min_rem = self._get_min_remaining(self.net_dev, kind='net')
        running_total = self._get_running_remaining_total(self.net_dev, kind='net')
        capacity = max(1, getattr(self, '_net_capacity', 1))

        work_tot = running_total + queue_sum
        work_after_first = max(0.0, work_tot - capacity * min_rem)
        return min_rem + (work_after_first / capacity)

    def _get_queue_demand_sum(self, simpy_resource_queue, kind='cpu'):
        total_demand = 0.0
        for req in simpy_resource_queue:
            if hasattr(req, 'task_data'):
                task_obj = req.task_data
                if kind == 'cpu':
                    total_demand += getattr(task_obj, 'd_cpu', 0.0)
                else:
                    total_demand += getattr(task_obj, 'd_net', 0.0)
        return total_demand

    # --------------------------------------------------
    # Pipeline CPU -> NET
    # --------------------------------------------------

    def greedy_approach(self, env, task):
        dest_pos = globals.observer.getPositionVector(globals.instant_in_configuration)
        ranker_neighbors = []

        for server in self.neighbors:
            neighbor_distance = get_pos_proximity(dest_pos, server.getPositionVector(globals.instant_in_configuration))
            t = (server, neighbor_distance, server.is_acc_point)
            ranker_neighbors.append(t)

        ranker_neighbors.sort(key=lambda x: (not x[2], x[1]))

        best_server = None
        for neighbor_tuple in ranker_neighbors:
            if neighbor_tuple[0].name not in task.visited:
                best_server = neighbor_tuple[0]
                break

        if best_server:
            yield from sendTask(env, task, self, best_server, 'SIMPLE_GREEDY')

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

    def get_selection_score(self, task_type, d_cpu, d_net, energy_budget_max=1.0):
        """
        Calcola lo score di selezione in base all'euristica semplice del modello LaTeX.
        Lo score è massimizzato: (Beneficio) - (Costo/Ritardo)
        """
        # 1. Calcola R e W predetti (usa le tue funzioni W_cpu/W_net modificate)
        Wc = self.W_cpu()
        Wn = self.W_net()
        R_predicted = Wc + d_cpu + Wn + d_net

        max_r_acceptable = config.get("Tmax_H", 100.0)

        # Se il tempo totale previsto (R) supera Tmax_H, il server non è idoneo.
        # Restituiamo un punteggio molto basso (ad esempio, negativo infinito)
        # per assicurarci che non venga scelto.
        if R_predicted > max_r_acceptable:
            return -float('inf')

            # 2. Definisci il Beneficio (B_i) e il Costo (R) in base al tipo di task

        if task_type in ("Generic_Service", "CPU_Intensive"):
            # Criterio LaTeX: shortest W_r^cpu and the higher B_i.
            # Score = Beneficio (B_i) - Costo (W_cpu)
            # R normalizzato rispetto a un massimo di R accettabile (ad esempio Tmax_H)
            max_r_acceptable = config.get("Tmax_H", 100.0)
            B_normalized = self.energy / energy_budget_max
            Wc_normalized = Wc / max_r_acceptable if max_r_acceptable > 0 else Wc

            # Se Wc è l'unico ritardo di coda, massimizza B e minimizza Wc
            # Score = B_normalized - Wc_normalized
            return B_normalized - Wc_normalized

        elif task_type == "Batch":
            # Criterio LaTeX: shortest W_r^net and the higher B_i.
            # Score = Beneficio (B_i) - Costo (W_net)
            max_r_acceptable = config.get("Tmax_H", 100.0)
            B_normalized = self.energy / energy_budget_max
            Wn_normalized = Wn / max_r_acceptable if max_r_acceptable > 0 else Wn

            # Score = B_normalized - Wn_normalized
            return B_normalized - Wn_normalized

        elif task_type == "CPU_and_Data_Intensive":
            # Criterio LaTeX: shortest W_r^net + W_r^cpu and higher B_i.
            # Score = Beneficio (B_i) - Costo (W_tot)
            W_tot = Wc + Wn
            max_r_acceptable = config.get("Tmax_H", 100.0)
            B_normalized = self.energy / energy_budget_max
            W_tot_normalized = W_tot / max_r_acceptable if max_r_acceptable > 0 else W_tot

            # Score = B_normalized - W_tot_normalized
            return B_normalized - W_tot_normalized

        # Per il caso 'Generic Service' puro (solo energy budget):
        # Criterio LaTeX: lower B_i (to use residual energy budget).
        # Score = Costo (B_i) -> Minimizza B_i, quindi Score = -B_i
        # if task_type == "Generic_Service":
        #     return - (self.energy / energy_budget_max)

        return 0.0  # Score di default

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
        print(f"TASK {task.id} {sender.name} -> {receiver.name}")
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