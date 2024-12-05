import json
import math
import simpy
import time
import logging
import threading
from numpy import random
from skyfield.api import EarthSatellite

import experiments
from SaveCurrentSATOnFile import saveTLEOnFile
from user_based_topology import get_orbit_proximity, get_current_time, getLatency, are_satellites_equal, getAllSatOnMe, classifySat_BufferZone, printSatList



def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

simulation_results = []

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

class EdgeServer:
    def __init__(self, env, name, satellite : EarthSatellite):
        '''
                Initialize an EdgeServer instance.

                :param env: Simulation environment.
                :param name: Name of the edge server.
                '''
        self.env = env
        self.name = name
        self.satellite = satellite
        self.neighbors = {}
        self.latency = {}
        self.bandwidth = {}
        self.distance_from_user = -1
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

    def set_DistanceFromUser(self, distance):
        self.distance_from_user = distance


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

#funzione per generare n numeri random da 0 alla lunghezza di num_server
random_numbers = []
def generate_random_numbers(n, num_server):
    # Genera 5 numeri casuali non uguali tra 0 e 25
    while len(random_numbers) < n:
        random_number = random.randint(0, num_server)
        if random_number not in random_numbers:
            random_numbers.append(random_number)
def generate_tasks(env):
    # funzione per generare 5 access point random in base al numero totale di server
    generate_random_numbers(config["access_point"], config["topology"])

    global next_server_index, priority_combination, arrival_time, random_server, next_index, next_number
    #print('Genero i task')
    logging.info('Genero i task')
    num_servers = len(edge_servers)
    task_id = 1

    while True:
        # Read the distribution type from the configuration
        distribution_type = config["generate_tasks"]["distribution"]

        # Get the corresponding function based on the distribution type
        distribution_function = getattr(experiments, distribution_type, None)

        # Check if the function exists
        if distribution_function is not None and callable(distribution_function):
            arrival_time = distribution_function('Task') #Inter arrival time, tempo tra l'arrivo di 2 task.
        else:
            logging.debug(f"Unrecognized or invalid distribution type: {distribution_type}")
            raise ValueError("Unrecognized distribution type")

        yield env.timeout(arrival_time)

        # Calcola l'indice del server da selezionare in base al round-robin
        #next_server_index = (next_server_index + 1) % num_servers  # Incrementa l'indice e ritorna a 0 se è l'ultimo server
        #random_server = edge_servers[next_server_index]

        # Data la lista random numbers, Calcola l'indice del server successivo da selezionare in base al round-robin
        next_server_index = (next_server_index + 1) % len(random_numbers)
        random_server = edge_servers[random_numbers[next_server_index]-1]
        #print(f"Prossimo server selezionato: {random_server.name}")

        '''
        #per avere una distibuzione su server specifici togliere il commento
        distribution_string = config["request_distribution"]["distribution"]
        distribution_values = list(map(int, distribution_string.split("_")))
        random_server = edge_servers[experiments.request_distribution(*distribution_values)]'''

        priority_combination_string = config["priority_combination"]["distribution"]
        priority_combination_values = list(map(int, priority_combination_string.split("_")))
        priority_combination = experiments.priority_combination(*priority_combination_values)

        task_priority = priority_combination
        print(task_priority)

        #env.process(task(env, task_id, random_server, task_priority))
        task_id += 1





def compute_distances_from_target_satellite(accessPoint, closerSatellite_Sorted, t):
    vector_Sat_Topology = []
    for i in range(0, len(closerSatellite_Sorted)):
        if are_satellites_equal(accessPoint.satellite, closerSatellite_Sorted[i].satellite):
            pass
        else:
            proximity = get_orbit_proximity(accessPoint.get_satellite() , closerSatellite_Sorted[i].get_satellite(), t)         
            if  proximity < config["Laser_Comunication_Range"] :                                # Check laser distance
                vector_Sat_Topology.append((closerSatellite_Sorted[i], proximity)) 

    sat_vector_Topology_sorted = sorted(vector_Sat_Topology, key=lambda x: x[1])
    return sat_vector_Topology_sorted

def periodic_Recall():
    time.sleep(config["topology_sleeping_time"] * 60)
    edge_servers = create_topology_dome()

def create_topology_dome():
    time = get_current_time()

    edge_servers = []
    acc_point ,satellites_dome, satellites_buffer = getAllSatOnMe(time = time)
    num_sat_dome, num_sat_buffer, num_AP = len(satellites_dome), len(satellites_buffer), len(acc_point)

    print(f"Satelliti Considerati TOT: {num_sat_buffer + num_sat_dome + num_AP} AP: {num_AP} DOME: {num_sat_dome} BUFF: {num_sat_buffer} \n")
    tmp_sat = satellites_dome + satellites_buffer
    
    for k in range(0, num_AP):
        server_id = f"{acc_point[k][0].name}"
        edge_server = EdgeServer(env, server_id, acc_point[k][0])
        edge_server.set_DistanceFromUser(acc_point[k][1])
        edge_servers.append(edge_server)

    for i in range(0, num_sat_dome + num_sat_buffer):
        server_id = f"{tmp_sat[i][0].name}"
        edge_server = EdgeServer(env, server_id, tmp_sat[i][0])
        edge_server.set_DistanceFromUser(tmp_sat[i][1])
        edge_servers.append(edge_server)
    
    for i in range(len(edge_servers)):
        current_server = edge_servers[i]
        neighbor = compute_distances_from_target_satellite(current_server, edge_servers)
        for n in neighbor:
            current_server.add_neighbor(n[0], 1, getLatency(n[1]), 
                                        random.uniform(config["available_bandwidth"]["min"], config["available_bandwidth"]["max"]))
    
    return edge_servers

if __name__ == "__main__":
    
    global edge_servers

    # Setup and start the simulation
    random.seed(config["seed"])
    
    env = simpy.Environment()
    
    edge_servers = create_topology_dome()

    thread = threading.Thread(target=periodic_Recall)
    thread.daemon = True 
    thread.start()

    env.process(generate_tasks(env))
    env.run(config['simulation_duration'])

    end_time = time.time()    # Tempo finale

    