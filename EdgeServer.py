import json
import logging
import simpy
from skyfield.api import EarthSatellite

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

total_time = 0  # Imposta il valore iniziale di total_time

class EdgeServer:
    def __init__(self, env, name, satellite: EarthSatellite, orbitalSunset):
        '''
                Initialize an EdgeServer instance.

                :param env: Simulation environment.
                :param name: Name of the edge server.
                '''
        self.env = env
        self.name = name
        self.satellite = satellite
        self.orbitalSunset = orbitalSunset
        self.neighbors = {}
        self.latency = {}
        self.bandwidth = {}
        self.process_queue = simpy.PriorityResource(env, capacity=5)  # Initialize a PriorityResource for the task queue
        self.server_queue = []
        self.utility_value = 0  # Valore iniziale di utilità del server
        self.completed_tasks = []

    def task_completed(self, task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time,
                       execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda,
                       original_TaskPriority, TMAX_exceeded):
        '''
                Record completed tasks.

                :param task_id: ID of the completed task.
                :param task_priority: Priority of the completed task.
                :param arrival_time_system: Arrival time of the task in the system.
                :param arrival_time_task_queue: Arrival time of the task in the server queue.
                :param start_time: Start time of task execution.
                :param end_time: End time of task execution.
                :param execution_time: Execution time of the task.
                :param service_time: Service time of the task.
                :param time_in_queue: Time spent by the task in the queue.
                :param selected_server: Server selected for task execution.
                :param num_hops: Number of hops to reach the selected server.
                :param lunghezza_coda: Length of the server queue.

                :return: None
                '''
        print(f"Completamento Task {task_id}: Start {start_time}, End {end_time}, {self.name}")

        self.completed_tasks.append((task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time,
                                     end_time, execution_time, service_time, time_in_queue, selected_server, num_hops,
                                     lunghezza_coda, original_TaskPriority, TMAX_exceeded))

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
        return f"Satellite : (nome={self.name}) neighbor: ({self.neighbors})\n"

    def UpdateUtilityValue(self, env, required_cpu, transfer_time, restart_time, download_time, server, task_priority):
        '''
        Aggiorna il valore di utilità del server in base ai task attualmente in coda e al carico richiesto.

        :param required_cpu: CPU richiesta dal task.
        :param transfer_time: Tempo di trasferimento del contesto.
        :param restart_time: Tempo di riavvio del task.
        :param download_time: Tempo di download dell'immagine.
        :param task_priority: Priorità del task (1 = alta, 100 = bassa).
        :param server: Server su cui viene aggiornato il valore di utilità.

        :return: Nessun valore di ritorno, aggiorna l'attributo utility_value del server.
        '''
        # Ottiene la lista di task attualmente in coda nel server
        tasks_in_queue = list(server.server_queue)
        logging.debug(f'Server: {server.name} Task in coda: {tasks_in_queue}')

        # Se ci sono task in coda, calcola i parametri di utilità
        if len(tasks_in_queue) > 0:
            # Calcola il numero di task che sono arrivati prima del tempo attuale (env.now)
            total_priority_in_queue = sum([1 for r in tasks_in_queue if r[5] < env.now])

            # Calcola il tempo di attesa totale dei task (waiting_time)
            self.waiting_time = sum([r[6] for r in tasks_in_queue if r[5] < env.now])
            logging.debug(f'waiting_time {self.waiting_time}')

            # Calcola il tempo medio di servizio (AVG_service_time)
            self.AVG_service_time = self.waiting_time / total_priority_in_queue if total_priority_in_queue > 0 else 0
            logging.debug(f'AVG_service_time {self.AVG_service_time}')

            # Conta il numero di task ad alta priorità nella coda
            num_high_priority = sum(1 for r in tasks_in_queue if r[4] == 1 and (env.now - 1) < r[5] <= (env.now))
            logging.debug(f'num_high_priority {num_high_priority}')

            # Conta il numero di task a bassa priorità nella coda
            num_low_priority = sum(1 for r in tasks_in_queue if r[4] == 100 and (env.now - 1) < r[5] <= (env.now))
            logging.debug(f'num_low_priority {num_low_priority}')

            # Calcola rho_l_ij (carico della bassa priorità)
            rho_l_ij = num_low_priority * self.AVG_service_time
            logging.debug(f'Server: {server.name} RHO l ij: {rho_l_ij}')

            # Calcola rho_h_ij (carico dell'alta priorità)
            rho_h_ij = num_high_priority * self.AVG_service_time
            if rho_h_ij > 1:
                rho_h_ij = 0.99  # Se rho_h_ij è maggiore di 1, lo limitiamo a 0.99
            logging.debug(f'Server: {server.name} RHO h ij: {rho_h_ij}')

            # Calcola il tempo di attesa per i task ad alta priorità (Th_ij)
            self.Th_ij = ((1 + rho_l_ij) * self.AVG_service_time) / (1 - rho_h_ij)

            # Calcola rho totale (somma di carico alta e bassa priorità)
            rho = rho_h_ij + rho_l_ij
            if rho > 1:
                rho = 0.99  # Limitiamo rho a 0.99 per evitare sovraccarichi

            # Calcola il tempo di attesa per i task a bassa priorità (Tl_ij)
            self.Tl_ij = ((1 - rho_h_ij * (1 - rho)) * self.AVG_service_time) / ((1 - rho_h_ij) * (1 - rho))

        # Se non ci sono task in coda, setta i valori di utilità a zero
        else:
            self.AVG_service_time = 0
            self.Th_ij = 0
            self.Tl_ij = 0
            self.waiting_time = 0

        # Calcola il tempo totale per trasferimento, riavvio e download
        total_time = transfer_time + restart_time + download_time

        # Massima capacità della CPU
        C_i_MAX = config['cpu_capacity']

        # Aggiorna il valore di utilità del server in base alla priorità del task
        if task_priority == 1:  # Task ad alta priorità
            self.utility_value = self.Th_ij + (required_cpu / C_i_MAX) + total_time
        else:  # Task a bassa priorità
            self.utility_value = self.Th_ij + self.Tl_ij + (required_cpu / C_i_MAX) + total_time
