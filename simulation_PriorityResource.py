import json
import math
import simpy
import logging
from numpy import random

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

simulation_results = []

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

class EdgeServer:
    def __init__(self, env, name):
        '''
                Initialize an EdgeServer instance.

                :param env: Simulation environment.
                :param name: Name of the edge server.
                '''
        self.env = env
        self.name = name
        self.neighbors = {}
        self.latency = {}
        self.bandwidth = {}
        self.process_queue = simpy.PriorityResource(env, capacity=1)  # Initialize a PriorityResource for the task queue
        self.server_queue = []
        self.utility_value = 0  # Valore iniziale di utilità del server
        self.completed_tasks = []

    def task_completed(self, task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time, execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda, original_TaskPriority, TMAX_exceeded):
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
        self.completed_tasks.append((task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time, execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda, original_TaskPriority, TMAX_exceeded))

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

    def UpdateUtilityValue(self, required_cpu, transfer_time, restart_time, download_time, server, task_priority):
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


def create_topology(num_servers, network_type):
    edge_servers = []

    for i in range(num_servers):
        server_id = f"{1 + i}"
        edge_server = EdgeServer(env, server_id)
        edge_servers.append(edge_server)

    # Aggiunta dei collegamenti solo con i vicini a destra, sinistra, sopra e sotto
    rows = int(math.sqrt(config["topology"]))
    cols = int(math.sqrt(config["topology"]))

    for i in range(rows):
        for j in range(cols):
            index = i * cols + j
            current_server = edge_servers[index]

            # Collegamento con il vicino a destra
            if j + 1 < cols:
                right_neighbor = edge_servers[index + 1]
                current_server.add_neighbor(right_neighbor, 1,
                                            random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                            random.uniform(config["available_bandwidth"]["min"],
                                                           config["available_bandwidth"]["max"]))
            # Collegamento con il vicino a sinistra
            if j - 1 >= 0:
                left_neighbor = edge_servers[index - 1]
                current_server.add_neighbor(left_neighbor, 1,
                                            random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                            random.uniform(config["available_bandwidth"]["min"],
                                                           config["available_bandwidth"]["max"]))
            # Collegamento con il vicino sopra
            if i - 1 >= 0:
                upper_neighbor = edge_servers[index - cols]
                current_server.add_neighbor(upper_neighbor, 1,
                                            random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                            random.uniform(config["available_bandwidth"]["min"],
                                                           config["available_bandwidth"]["max"]))
            # Collegamento con il vicino sotto
            if i + 1 < rows:
                lower_neighbor = edge_servers[index + cols]
                current_server.add_neighbor(lower_neighbor, 1,
                                            random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                            random.uniform(config["available_bandwidth"]["min"],
                                                           config["available_bandwidth"]["max"]))
    # Aggiungi i collegamenti "a ponte"
    if network_type == "close":
        for i in range(num_servers):
            # Collegamenti "a ponte" lungo le colonne
            if num_servers >= cols and (i + 1) % cols == 0:
                next_server_index = (i - cols + 1) % num_servers
                edge_servers[i].add_neighbor(edge_servers[next_server_index], 1,
                                             random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                             random.uniform(config["available_bandwidth"]["min"],
                                                            config["available_bandwidth"]["max"]))
                # Aggiungi il collegamento inverso
                edge_servers[next_server_index].add_neighbor(edge_servers[i], 1,
                                                             random.uniform(config["latency"]["min"],
                                                                            config["latency"]["max"]),
                                                             random.uniform(config["available_bandwidth"]["min"],
                                                                            config["available_bandwidth"]["max"]))
            # Collegamenti "a ponte" lungo le righe
            if num_servers >= rows and i >= cols * (rows - 1):
                next_server_index = (i - cols * (rows - 1)) % num_servers
                edge_servers[i].add_neighbor(edge_servers[next_server_index], 1,
                                             random.uniform(config["latency"]["min"], config["latency"]["max"]),
                                             random.uniform(config["available_bandwidth"]["min"],
                                                            config["available_bandwidth"]["max"]))
                # Aggiungi il collegamento inverso
                edge_servers[next_server_index].add_neighbor(edge_servers[i], 1,
                                                             random.uniform(config["latency"]["min"],
                                                                            config["latency"]["max"]),
                                                             random.uniform(config["available_bandwidth"]["min"],
                                                                            config["available_bandwidth"]["max"]))
    # Stampa dei nodi e dei loro collegamenti
    print("# Matrice delle adiacenze")
    print("   ", end="")
    for i in range(len(edge_servers)):
        print(f"s{i} ", end="")
    print()

    for i, server in enumerate(edge_servers):
        print(f"s{i} ", end="")
        for j in range(len(edge_servers)):
            neighbor = edge_servers[j]
            if neighbor in server.neighbors:
                print(" 1 ", end="")
            else:
                print(" 0 ", end="")
        print()

    return edge_servers


if __name__ == "__main__":

    # Setup and start the simulation
    random.seed(config["seed"])

    env = simpy.Environment()