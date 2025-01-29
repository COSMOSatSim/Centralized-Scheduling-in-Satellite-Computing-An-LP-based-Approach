import csv
import json
import os
import random
import simpy
import time
import logging
import threading
import sys
from skyfield.api import EarthSatellite, load
import experiments
from user_based_topology import get_orbit_proximity, get_current_time, getLatency, are_satellites_equal, getAllSatOnMe, compute_distances_from_target_satellite, create_satellite_neighbors_dict, advance_time


def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

# Gestione thread
lock = threading.Lock() # Meccanismo di lock

simulation_results = []
config_index = 0 # This parameters allows to iterate over the configurations

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

#Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
try:
    with open("data/configurations.json", "r") as f:
        print("Configuration file loaded.\n")
        data_configurations = json.load(f)
except Exception as e:
    print(f"Error loading configuration file: {e}")

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
        print(f"Completamento Task {task_id}: Start {start_time}, End {end_time}")

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


def TaskAssignment(env, selected_server, task_id, required_cpu, required_ram, required_disk, task_priority,
                   arrival_time_system, utilization_CPU, num_hops, transfer_time, original_TaskPriority):
    '''
        Assign a task to a selected server and process it.

        :param env: The simulation environment.
        :param selected_server: The server to which the task will be assigned.
        :param task_id: The ID of the task.
        :param required_cpu: CPU requirement for the task.
        :param required_ram: RAM requirement for the task.
        :param required_disk: Disk space requirement for the task.
        :param task_priority: Priority of the task.
        :param arrival_time_system: Arrival time of the task in the system.
        :param utilization_CPU: CPU utilization for the task.
        :param num_hops: Number of hops to reach the selected server.
        :param transfer_time: Time required to transfer data.
        :param original_TaskPriority: Original task priority.

        :return: None
        '''
    global hop
    other_server_counter = 0
    if initial_server_counter == 0 and different_server_counter == 0:
        other_server_counter += 1
    logging.debug('Task Assignment')
    print('Task Assignment')
    # Azzera il numero di hop
    hop = 0
    lunghezza_coda = len(list(selected_server.server_queue))
    higher_priority_tasks = [task for task in list(selected_server.server_queue) if task[4] == 1]
    low_priority_tasks = [task for task in list(selected_server.server_queue) if task[4] == 100]
    yield env.timeout(transfer_time)

    arrival_time_task_queue = env.now
    task = task_id, required_cpu, required_ram, required_disk, task_priority, arrival_time_system, utilization_CPU, num_hops, arrival_time_task_queue, original_TaskPriority

    selected_server.server_queue.append(task)

    with selected_server.process_queue.request(priority=task[4]) as request:
        print(f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}")
        logging.debug(
            f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}")

        yield request
        start_time = env.now
        time_in_queue = start_time - arrival_time_task_queue

        #esponenziale con media 15 per CPU timeout

        # Valori presi dal file di configurazione (già in secondi)
        mean_seconds = config["CPU_timeout"]["mean"]  # Ad esempio, 900
        min_seconds = config["CPU_timeout"]["min"]  # Ad esempio, 600
        max_seconds = config["CPU_timeout"]["max"]  # Ad esempio, 1500

        yield env.timeout(experiments.truncated_exponential(mean=mean_seconds, lower=min_seconds, upper=max_seconds))

        end_time = env.now
        execution_time = end_time - start_time if start_time > 0 and end_time > 0 else 0
        print("execution time task assignment",execution_time, 'task', task_id)

        #execution_time = (end_time - start_time)
        service_time = execution_time + time_in_queue + transfer_time

        print(f"Task ID {task_id} eseguito sul server {selected_server.name}, Priorità: {task_priority} "
              f"Arrival Time in System: {arrival_time_system:.2f}, "
              f"start time: {start_time:.2f}, "
              f"rimasto in coda: {time_in_queue:.2f}, "
              f"lascia il sistema in {env.now:.2f}, "
              f"execution time {execution_time}, "
              f"Service time: {service_time:.2f}")

        priority_mapping = {100: "low", 1: "high"}
        task_p = priority_mapping.get(task_priority, "NaN")
        if task_p == "low":

            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, len(low_priority_tasks),
                                           original_TaskPriority, TMAX_exceeded=False)
        elif task_p == "high":
            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, len(higher_priority_tasks),
                                           original_TaskPriority, TMAX_exceeded=False)
        else:
            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, lunghezza_coda, original_TaskPriority,
                                           TMAX_exceeded=False)

        if len(selected_server.server_queue) > 0:
            selected_server.server_queue.pop(0)


Tmax_H = config["Tmax_H"]
Tmax_L = config["Tmax_H"]


def SearchNode(env, server_selected, task_id, required_cpu, required_ram, required_disk, image_size, Volume_size,
               restart_time, download_time, task_priority, arrival_time_system, utilization_CPU, Tmax_high, Tmax_Low,
               Tmax_latency):
    '''
        Search for the most suitable server to assign a task, considering utility values, latency, and task priorities.

        This function evaluates the available servers based on their utility value and selects the best one
        based on the highest priority task and the given constraints (such as Tmax latency).

        It updates the counters for each server (initial, different, and other) and assigns the task to the selected server.

        :param env: The simulation environment.
        :param server_selected: The initially selected server for the task.
        :param task_id: The ID of the task to be assigned.
        :param required_cpu: CPU requirement for the task.
        :param required_ram: RAM requirement for the task.
        :param required_disk: Disk space requirement for the task.
        :param image_size: Size of the image associated with the task.
        :param Volume_size: Size of the volume associated with the task.
        :param restart_time: Time needed to restart the task.
        :param download_time: Time required for downloading the task's image.
        :param task_priority: Priority of the task (high or low).
        :param arrival_time_system: The time when the task arrives in the system.
        :param utilization_CPU: The CPU utilization required for the task.
        :param Tmax_high: High threshold for utility value.
        :param Tmax_Low: Low threshold for utility value.
        :param Tmax_latency: Latency threshold for the server selection.

        :return: None

        This function will either:
        - Assign the task to the most suitable server based on its utility value and priority,
        - Or recursively select another server if no suitable server is available within the latency threshold.
        '''
    global sorted_servers, different_server_counter, other_server_counter, transfer_time, hop

    print(f'SearchNode, Server selezionato --> {server_selected.name}')
    logging.debug(f'SearchNode, Server selezionato --> {server_selected.name}')

    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    print(f'I server vicini al server {server_selected.name} sono: {[n.name for n in neighbors_at_distance_one]}')
    logging.debug(
        f'I server vicini al server {server_selected.name} sono: {[n.name for n in neighbors_at_distance_one]}')

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        else:
            transfer_time = 0

        #print(f'server {neighbor.name}, latenza {latency_to_server}, banda {bandwidth_to_server}, Transfer time {transfer_time}')
        logging.debug(
            f'server {neighbor.name}, latenza {latency_to_server}, banda {bandwidth_to_server}, Transfer time {transfer_time}')

        if neighbor == server_selected:
            server_selected.UpdateUtilityValue(required_cpu, transfer_time, 0, download_time, server_selected,
                                               task_priority)
        else:
            neighbor.UpdateUtilityValue(required_cpu, transfer_time, restart_time, download_time, neighbor,
                                        task_priority)

    sorted_servers = sorted(neighbors_at_distance_one, key=lambda server: server.utility_value)

    Tmax_high -= 2 * Tmax_latency

    sorted_servers = [server for server in sorted_servers if server.utility_value < Tmax_high]

    for server in sorted_servers:
        print(f"Server {server.name}: Utility Value = {server.utility_value} ")
        logging.debug(f"Server {server.name}: Utility Value = {server.utility_value} ")
    print(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    logging.debug(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    original_TaskPriority = task_priority

    initial_server_counter[server_selected.name] += 1

    if len(sorted_servers) > 0:
        server = sorted_servers.pop(0)

        if server != server_selected:
            different_server_counter[server_selected.name] += 1
            other_server_counter[server.name] += 1
            hop += 1

        logging.debug(f'Seleziono il server con utility più bassa: {server.name}')
        print(f'Seleziono il server con utility più bassa: {server.name}')

        AVG_service_time = server.AVG_service_time
        Th_ij = server.Th_ij
        Tl_ij = server.Th_ij + server.Tl_ij
        waiting_time = server.waiting_time

        if waiting_time <= AVG_service_time:
            task_priority = 1
            logging.debug(f"Task {task_id} assegnato alla coda ad alta priorità")
            print(f"Task {task_id} assegnato alla coda ad alta priorità")
        elif Th_ij <= waiting_time <= Tl_ij:
            logging.debug(f"Task {task_id} mantenuto nella sua coda di priorità {task_priority}")
            print(f"Task {task_id} mantenuto nella sua coda di priorità {task_priority}")
        else:
            task_priority = 100
            logging.debug(f"Task {task_id} assegnato alla coda a bassa priorità")
            print(f"Task {task_id} assegnato alla coda a bassa priorità")

        yield from TaskAssignment(env, server, task_id, required_cpu, required_ram, required_disk, task_priority,
                                  arrival_time_system, utilization_CPU, hop, transfer_time, original_TaskPriority)

    else:
        if Tmax_high <= 0:
            logging.debug("Tmax è arrivato a zero, termina la ricorsione.")
            priority_mapping = {100: "low", 1: "high"}
            task_p = priority_mapping.get(task_priority, "NaN")
            server_selected.task_completed(task_id, task_p, arrival_time_system, 0,
                                           0, 0, 0, 0, 0,
                                           server_selected.name, hop, 0, original_TaskPriority, TMAX_exceeded=True)
            print(f'Termina ricorsione, task {task_id} scartato')
            hop = 0
            return
        else:
            available_servers = [neighbor for neighbor in neighbors_at_distance_one if neighbor != server_selected]
            random_server = random.choice(available_servers)
            Tmax_latency = random_server.get_latency(server_selected)
            hop += 1
            logging.debug(
                f'Nessun server disponibile con utilità inferiore a Tmax. Selezionato server casuale: {random_server.name}')
            yield env.process(
                SearchNode(env, random_server, task_id, required_cpu, required_ram, required_disk, image_size,
                           Volume_size, restart_time, download_time, task_priority, arrival_time_system,
                           utilization_CPU, Tmax_high, Tmax_Low, Tmax_latency))


def LocalScheduler(task_id, required_cpu, required_ram, required_disk, server, image_size, Volume_size, restart_time, download_time, task_priority, arrival_time_system, utilization_CPU):
    #print('Local Scheduler')
    logging.debug('Local Scheduler')
    global hop  # Indica che la variabile hop è globale e non locale
    hop += 1  # Incrementa hop ogni volta che la funzione viene richiamata

    #controlla la configurazione se deve essere esclusa la parte della search_node.
    #se la search_node è esclusa, i server vengono scelti tramite roud-robin e non viene utilizzata l'utility.
    if config["search_node"] == 0:
        #print("Without search_node")
        logging.debug("Without search_node")
        yield from TaskAssignment(env, server, task_id, required_cpu, required_ram, required_disk, task_priority,
                              arrival_time_system, utilization_CPU, hop)
    else:
        #print("With search_node")
        logging.debug("With search_node")
        Tmax_latency = int(0)
        yield from SearchNode(env, server, task_id, required_cpu, required_ram, required_disk, image_size, Volume_size,
                          restart_time, download_time, task_priority, arrival_time_system, utilization_CPU, Tmax_H, Tmax_L, Tmax_latency)

def task(env, task_id, server, task_priority):

    # Calcola la media della distribuzione esponenziale
    mean = (config["MI"]["min"] + config["MI"]["max"]) /2

    # Calcola il tasso di arrivo (lambda) corrispondente
    Avg_service_demand = 1 / mean

    # Genera un numero casuale distribuito esponenzialmente
    MI = random.expovariate(Avg_service_demand)

    required_cpu = random.choice([config["required_cpu"]["min"], config["required_cpu"]["max"]])  # CPU richiesta dal task
    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"]["max"])  # RAM richiesta dal task #######cercare quali distributioni caratterizzano tipicamente la richiesta di RAM
    required_disk = random.randint(config["required_disk"]["min"], config["required_disk"]["max"])  # Spazio su disco richiesto dal task
    image_size = random.uniform(config["image_size"]["min"], config["image_size"]["max"])  # Genera casualmente la dimensione dell'immagine con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container
    Volume_size = random.uniform(config["Volume_size"]["min"], config["Volume_size"]["max"])  # Genera casualmente la dimensione dell'Volume con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container

    utilization_CPU = MI / (config["cpu_capacity"] * required_cpu)  #MI/(limits × C_i^max )
    #utilization_CPU = #MI / (config["cpu_capacity"] * required_cpu)  #MI/(limits × C_i^max )

    restart_time = random.uniform(config["restart_time"]["min"], config["restart_time"]["max"])  # Tempo di riavvio del task (ad esempio, in secondi)
    download_time = 0 #image_size / available_bandwidth
    arrival_time_system = env.now
    print(f"---> Task {task_id} (Priority: {task_priority}) arriva in {arrival_time_system:.2f}")
    logging.debug(f"---> Task {task_id} (Priority: {task_priority}) arriva in {arrival_time_system:.2f}")

    yield from LocalScheduler(task_id, required_cpu, required_ram, required_disk, server, image_size, Volume_size, restart_time, download_time, task_priority, arrival_time_system, utilization_CPU)


# Dichiarazione di una variabile globale per tenere traccia del prossimo server da selezionare
next_server_index = 0
def generate_tasks(env):

    global next_server_index, priority_combination, arrival_time, selected_server, next_index, next_number
    #print('Genero i task')
    logging.info('Genero i task')

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

        #! Prendo il prossimo server in base al round robin dalla lista di access point
        next_server_index = (next_server_index + 1) % len(global_access_point)
        selected_server = global_access_point[next_server_index]      # ho cambiato il nome
        
        priority_combination_string = config["priority_combination"]["distribution"]
        priority_combination_values = list(map(int, priority_combination_string.split("_")))
        priority_combination = experiments.priority_combination(*priority_combination_values)

        task_priority = priority_combination
        print(f"Access Point Selezionato: {selected_server.satellite.name} task priority: {task_priority}")

        env.process(task(env, task_id, selected_server, task_priority))
        task_id += 1

def compute_distances_from_target_sw(sat, closerServer_Sorted, t):
    """
    Compute the distances from the target satellite to other satellites.

    :param sat: The target satellite.
    :param closerSatellite_Sorted: List of satellites sorted by proximity.
    :param t: Current time.

    :return: List of tuples containing satellites and their distances from the target satellite.
    """
    
    vector_Sat_Topology = []
    for i in range(0, len(closerServer_Sorted)):
        if are_satellites_equal(sat.satellite, closerServer_Sorted[i].satellite):
            pass
        else:
            proximity = get_orbit_proximity(sat.get_satellite() , closerServer_Sorted[i].get_satellite(), t)         
            if  proximity < config["Laser_Communication_Range"] :                                # Check laser distance
                vector_Sat_Topology.append((closerServer_Sorted[i], proximity)) 

    sat_vector_Topology_sorted = sorted(vector_Sat_Topology, key=lambda x: x[1])
    return sat_vector_Topology_sorted

global_access_point = []

def create_topology_dome(time = get_current_time()):
    
    global global_access_point

    edge_servers = []
    acc_point ,satellites_dome, satellites_buffer = getAllSatOnMe(time)
    num_sat_dome, num_sat_buffer, num_AP = len(satellites_dome), len(satellites_buffer), len(acc_point)

    print(f"TIME: {time.utc_strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"Satelliti Considerati TOT: {num_sat_buffer + num_sat_dome + num_AP} AP: {num_AP} DOME: {num_sat_dome} BUFF: {num_sat_buffer} \n")
    tmp_sat = satellites_dome + satellites_buffer
    
    #Access Point Edge Servers
    for k in range(0, num_AP):
        server_id = f"{acc_point[k][0].name}"
        edge_server = EdgeServer(env, server_id, acc_point[k][0])
        edge_servers.append(edge_server)
        
    global_access_point = edge_servers.copy()   #Salvo i nuovi access point globali

    # Tutti i satelliti nella cupola
    for i in range(0, num_sat_dome + num_sat_buffer):
        server_id = f"{tmp_sat[i][0].name}"
        edge_server = EdgeServer(env, server_id, tmp_sat[i][0])
        edge_servers.append(edge_server)
    
    # Calcola i vicini di ogni server
    for i in range(len(edge_servers)):
        current_server = edge_servers[i]
        neighbor = compute_distances_from_target_sw(current_server, edge_servers, time)
        for n in neighbor:
            #print(type(n[0]), " n -> ", n[0])
            current_server.add_neighbor(n[0], 1, getLatency(n[1]), 
                                        random.uniform(config["available_bandwidth"]["min"], config["available_bandwidth"]["max"]))
        #print(current_server.name)
    return edge_servers

def createTopology_serializzable_dome(time_top, serializable):
    """
        Creates a topology of satellites and access points based on the given time and serializable object.

        Args:
            time_top (datetime): The time at which to get the satellites and access points.
            serializable (object): An object that can be serialized to obtain satellite data.

        Returns:
            list: A combined list of access points, satellites in the dome, and satellites in the buffer.

        Prints:
            A formatted string showing the time, the number of access points, satellites in the dome, 
            satellites in the buffer, and the total count of these elements.
    """
    acc_point ,satellites_dome, satellites_buffer = getAllSatOnMe(time_top, serializable = serializable)                          #Ottengo i satelliti 
    print(f"({time_top.utc_strftime('%Y-%m-%d %H:%M:%S')}) | (A:{len(acc_point)},D:{len(satellites_dome)},B:{len(satellites_buffer)}) | TOT:({len(acc_point) + len(satellites_dome) + len(satellites_buffer)})")
    return acc_point + satellites_dome + satellites_buffer

def genConfigs(t0, interval, num_configs):
    """
    Generates a list of configurations over a specified time period.
    Args:
        t0 (datetime, optional): The initial time for generating configurations. Defaults to the current time.
        interval (int, optional): The time interval (in seconds) between each configuration. Defaults to 2 minutes.
        num_configs (int, optional): The total number of Configurations in the building process.

    Returns:
        list: A list of configurations generated over the specified time period.
    """
    t, configs = t0, []                                     # Initialize time and configuration list
    num_access_point = config["access_point"]               # Number of access points
    totSecs = num_configs * interval                        # Total duration in seconds

    for elapsed_time in range(0, totSecs, interval):
        configuration = []
        topology = createTopology_serializzable_dome(t, True)             # Create the topology

        for i in range(len(topology)):
            current_server = topology[i]
            neighbor = compute_distances_from_target_satellite(current_server, topology, t)     # Compute distances to neighbors

            if i < num_access_point:
                info_sat = create_satellite_neighbors_dict(current_server, neighbor, True)      # Create neighbor info for access points
            else:
                info_sat = create_satellite_neighbors_dict(current_server, neighbor, False)     # Create neighbor info for other satellites

            configuration.append(info_sat)  # Save this satellite's configuration

        print(f"Configuration ({elapsed_time // interval}/{num_configs-1})")
        print("#" * 70)

        data = {
            "time": t.utc_datetime().isoformat(),   # Current time in ISO format
            "configuration": configuration         # List of satellite configurations
        }
        configs.append(data)                        # Append the configuration to the list
        t = advance_time(t, interval / 60)          # Advance time by the interval

    output = {
        "t0": t0.utc_datetime().isoformat(),        # Initial time in ISO format
        "interval": interval,                       # Time interval between configurations
        "total_seconds": totSecs,                   # Total duration for configurations
        "observer_position": config["simulation_location"],     # Observer's position
        "configurations": configs                   # List of all configurations
    }

    # Salva il file JSON
    try:
        with open("data/configurations.json", "w") as f:
            json.dump(output, f, indent=4)
        print("File saved successfully!")
    except IOError as e:
        print(f"Error saving configuration file: {e}")

def build_EdgeServer_from_config(configuration):
    global global_access_point, ne
    neighbors_SAT, tmp_ES = {}, []
    
    for sat_info in configuration["configuration"]: 
            server_id = f"{sat_info['satellite']}"
            name = sat_info["TLE-DATA"][0]["name"]
            line1 = sat_info["TLE-DATA"][0]["line1"]
            line2 = sat_info["TLE-DATA"][0]["line2"]

            neighbors_SAT[server_id] = sat_info["neighbors"]
            edge_server = EdgeServer(env, server_id, EarthSatellite(line1, line2, name, load.timescale()))
            tmp_ES.append(edge_server)
                
    # Salvo gli Access_point globali
    print("### ACCESS POINT ###")
    with lock:
        global_access_point = tmp_ES[:config["access_point"]]  
    [print(f"({i})-{global_access_point[i].name}") for i in range(config["access_point"])]         
    print("####################")

    return tmp_ES, neighbors_SAT

def periodic_recall_monitor(env):
    while True:
        yield env.timeout(config["Interval_between_Configurations_in_seconds"])
        
        print("-"*70)
        print(f"\t||TIME IN SIMULATION : (seconds:{env.now}) (minutes: {env.now//60}) ||\n")
        print("MODIFICA CONFIGURAZIONE IN CORSO...\n")
        loadConfiguration() # Carica la configurazione
        print("MODIFICA CONFIGURAZIONE COMPLETATA\n")

def update_counters_dictionary(all_server, initial_server_counter, different_server_counter, other_server_counter):
    """
    Aggiunge nuovi server ai dizionari dei contatori o li inizializza.

    Args:
        edge_servers (list): Lista attuale di server.
        initial_server_counter (dict): Dizionario per il contatore iniziale dei server.
        different_server_counter (dict): Dizionario per il contatore dei server diversi.
        other_server_counter (dict): Dizionario per il contatore degli altri server.

    Returns:
        None: Aggiorna i dizionari in-place.
    """
    for server_name in all_server:
        if server_name not in initial_server_counter:
            initial_server_counter[server_name] = 0
        if server_name not in different_server_counter:
            different_server_counter[server_name] = 0
        if server_name not in other_server_counter:
            other_server_counter[server_name] = 0

def update_servers(edge_servers, new_servers):
    """
    Aggiorna i server esistenti o aggiunge nuovi server se non presenti.

    Args:
        edge_servers (list): Lista di server esistenti (da mantenere).
        new_servers (list): Lista di nuovi server dalla nuova configurazione.

    Returns:
        dict: Dizionario aggiornato dei server.
    """
    # Crea un dizionario per i server esistenti basato sul nome
    old_servers = {server.name: server for server in edge_servers}
    new_servers = {server.name: server for server in new_servers}

    # Dizionari per i risultati
    intersection = {name: server for name, server in new_servers.items() if name in old_servers}    # Servers nell'intersezione
    A = {name: server for name, server in old_servers.items() if name not in new_servers}           # Server che sono tramontati
    B = {name: server for name, server in new_servers.items() if name not in old_servers}           # Server che non sono sorti

    return intersection, A, B

def update_servers_neighbors(servers_dict, neighbors_SAT):
    """
    Updates the neighbors of each server in the servers_dict based on the provided neighbors_SAT information.
    Args:
        servers_dict (dict): A dictionary where keys are server names and values are server objects.
        neighbors_SAT (dict): A dictionary where keys are server names and values are lists of dictionaries 
                              containing neighbor information with 'name' and 'latency' keys.
    Returns:
        dict: The updated servers_dict with neighbors information added to each server.
    The function performs the following steps:
    1. Constructs a dictionary (servers_updated_neighbors) to store updated neighbor information for each server.
    2. Iterates through each server in servers_dict and updates its neighbors based on neighbors_SAT.
    3. For each server, it creates dictionaries for hop_neighbors, latency, and bandwidth.
    4. Updates each server's neighbors using the update_neighbors method with the constructed dictionaries.
    """
    servers_updated_neighbors = {}  # Dizionario per i server con i vicini aggiornati

    # Costruzione del dizionario per salvare le informazioni dei server e dei loro vicini
    for k, v in servers_dict.items():   
        neighbor, neighbors = {}, []
        for neighbor in neighbors_SAT[k]:
            neighbor = { 
                'server': servers_dict[neighbor['name']],
                'latency': neighbor['latency'] 
            }
            neighbors.append(neighbor)

        servers_updated_neighbors[k] = {
            "obj":v,
            "neighbors": neighbors
        }

    # Inserisco i vicini per ogni Edge_server
    for name, server in servers_dict.items():
        hop_neighbors, latency, bandwidth = {}, {}, {}
        info = servers_updated_neighbors[name]
        
        for neighbor in info["neighbors"]:
            hop_neighbors[neighbor['server']] =  1                  
            latency[neighbor['server']] = neighbor['latency']       
            bandwidth[neighbor['server']] = random.uniform(config["available_bandwidth"]["min"], config["available_bandwidth"]["max"]) 

        # Aggiungo i dizionari riguardanti i vicini ai rispettivi server
        server.update_neighbors(hop_neighbors, latency, bandwidth)

    return servers_dict

def loadConfiguration():
    """
    Carica una configurazione dal file e aggiorna la lista edge_servers senza sostituirla completamente.

    Returns:
        None
    """
    global config_index, global_access_point, edge_servers

    if config_index > 0:
        print("#" * 30)
        configuration = data_configurations["configurations"][config_index]
        print(f'Conf: {config_index} | time : {configuration["time"]}')
        print(f"In Aggiornamento edge_servers. Totale server: {len(edge_servers)}")

        # Costruisci i nuovi server dalla configurazione
        new_servers, new_neighbors = build_EdgeServer_from_config(configuration)

        # Aggiorna i server esistenti o aggiunge nuovi server se non presenti.
        intersection, old_edge_servers, new_edge_servers = update_servers(edge_servers, new_servers)
        update_counters_dictionary({**intersection, **new_edge_servers}, initial_server_counter, different_server_counter, other_server_counter)    # Aggiorno i dizionari dei nuovi aggiunti

        # Stampa per debug
        print(f"Configurazione aggiornata. Totale server: {len({**intersection, **new_edge_servers, **old_edge_servers})}")
        
        #Aggiorno i vicini
        servers_in_dome_updated = update_servers_neighbors({**intersection, **new_edge_servers}, new_neighbors) # Aggiorno i vicini per i server nell'intersection e i nuovi aggiunti
        [server.update_neighbors({}, {}, {}) for server in old_edge_servers.values()]   # Pulisco i dizionari che riguardano i vicini dei server tramontati
        
        '''# Stampa per debug
        print("-"*20," CHECK QUEUE TASK ","-"*20)
        for server in edge_servers:
             print(f"\t{server.name} : ")
             for task in server.server_queue:
                 print(f"\t\t{task[0]}")
        print("-"*20," CHECK COMPLETED TASK ","-"*20)
        for server in edge_servers:
             print(f"\t{server.name} : completed({len(server.completed_tasks)})")
             for task in server.completed_tasks:
                 print(f"\t\t{task[0]}")'''

        with lock: # ! Meccanismo di Lock
            edge_servers = list(servers_in_dome_updated.values()) + list(old_edge_servers.values())

        # Incrementa l'indice di configurazione
        if config_index == config["Number_of_Configurations"] - 1:
            print("(!) Hai finito le configurazioni")
        else:
            config_index += 1
    else:
        # Caricamento iniziale della configurazione
        configuration = data_configurations["configurations"][config_index]
        print(f'Conf: {config_index} | time : {configuration["time"]}')

        # Costruisci i server iniziali
        edge_servers, neighbors_SAT = build_EdgeServer_from_config(configuration)

        # Stampa per debug
        print(f"Configurazione iniziale caricata. Totale server: {len(edge_servers)}")
        server_dict = {server.name: server for server in edge_servers}
        
        #Aggiungiamo i vicini per ogni elemento
        for server in edge_servers:
            neighbors = neighbors_SAT[server.name]

            for n in neighbors:
                neighbor_server = server_dict.get(n["name"])
                server.add_neighbor(neighbor_server, 1, n["latency"],
                                                random.uniform(config["available_bandwidth"]["min"], config["available_bandwidth"]["max"]))
        
        config_index += 1

if __name__ == "__main__":

    global edge_servers, initial_server_counter, different_server_counter, other_server_counter

    # Setup and start the simulation
    random.seed(config["seed"])

    env = simpy.Environment()
    hop = 0  # Inizializza la variabile hop a zero
    MaxTry = config["max_try"]  # Imposta il valore massimo di MaxTry
    total_time = 0  # Imposta il valore iniziale di total_time

    if config["Build_Configurations"]:  # Gestione costruizione configurazioni
        genConfigs(get_current_time(), config["Interval_between_Configurations_in_seconds"], config["Number_of_Configurations"])
        config["Build_Configurations"] = False
        try:
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=1)
        except IOError as e:
            print(f"Errore nella scrittura del file di configurazione: {e}")
            sys.exit(1)  # Termina lo script

        sys.exit("File of configurations created")

    if config["Load_Configuration"]:
        print("Carico le configurazioni dal File")
        loadConfiguration() # Carico la prima configurazione
        env.process(periodic_recall_monitor(env)) # Faccio partire il thread per cambiare configurazione
    else:
        print("Creo la topologia")
        edge_servers = create_topology_dome()

    initial_server_counter = {server.name: 0 for server in edge_servers}
    different_server_counter = {server.name: 0 for server in edge_servers}
    other_server_counter = {server.name: 0 for server in edge_servers}

    env.process(generate_tasks(env))

    end_time = time.time()    # Tempo finale

    network_type = config["network_type"]["type"]  # open / close

    # Costruisce il nome del file CSV
    # Ottiene i valori di priority_combination e generate_tasks
    priority_distribution = config["priority_combination"]["distribution"]
    generate_tasks_distribution = config["generate_tasks"]["distribution"]
    config_seed = config["seed"]
    config_arrival_time = config["arrival_time_exponential"]
    distribution_string = config["request_distribution"]["distribution"]
    if distribution_string == "0_0_0":
        distribution_string = "RR"
    latency = config["latency"]["min"]
    access_point = config["access_point"]

    # Specifica il percorso della directory che vuoi creare
    # percorso_directory = f"simulation result_{distribution_string}_request_distribution_latency_{latency}_distribuited/{config_seed}"
    percorso_directory = f"simulation result-{network_type}-System_AP{access_point}/simulation result_{distribution_string}_request_distribution_latency_{latency}_distribuited/{config_seed}"
    os.makedirs(percorso_directory, exist_ok=True)

    csv_name = f"{percorso_directory}/simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.csv"
    csv_name_server = f"{percorso_directory}/server_name_migration_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.csv"
    # Crea un file CSV per registrare i risultati
    csv_file = config["csv_name"]["name"] = csv_name
    log_name = f"simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.log"

    print(
        f"Start simulation for seed {config_seed}, priority distribution {priority_distribution}, arrival time {config_arrival_time}")

    log_file_path = os.path.join(os.path.dirname(csv_file), log_name)

    # setup_logging(log_file_path) #abilita la scrittura dei log

    env.run(config['simulation_duration'])

    # Scrive i dati dei task nel file CSV
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(
            ["Task ID", "Task Priority", "Arrival time in system", "arrival_time_task_queue", "Start Time", "End Time",
             "Execution time", "Time in system", "Time in queue", "Server Name", "Num Hops", "Queue length",
             "original_TaskPriority", "TMAX_exceeded"])

        for server in edge_servers:
            for task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time, execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda, original_TaskPriority, TMAX_exceeded in server.completed_tasks:
                if original_TaskPriority == 1:
                    original_TaskPriority = 'high'
                else:
                    original_TaskPriority = 'low'

                writer.writerow(
                    [task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time,
                     execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda,
                     original_TaskPriority, TMAX_exceeded])
            for task_id, required_cpu, required_ram, required_disk, task_priority, arrival_time_system, utilization_CPU, num_hops, arrival_time_task_queue, original_TaskPriority in server.server_queue:
                TMAX_exceeded = False
                if task_priority == 1 or original_TaskPriority == 1:
                    #print('executiontime', execution_time, 'task id', task_id, 'utilization', utilization_CPU)
                    writer.writerow(
                        [task_id, 'high', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now - arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'high', TMAX_exceeded])
                else:
                    writer.writerow(
                        [task_id, 'low', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now - arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'low', TMAX_exceeded])
                # il task salvato in coda ha i seguenti parametri nel seguente ordine:
                # task = task_id, required_cpu, required_ram, required_disk, task_priority, arrival_time_system, utilization_CPU, num_hops

    print(f"Simulation results saved to: {csv_file}")
    print('R_j user', initial_server_counter, 'F_j other', different_server_counter, 'R_j other', other_server_counter)

    # Compute statistics for the results
    I_j = {}
    for server_key in other_server_counter.keys():  # Iterate over dictionary keys
        numerator = other_server_counter[server_key]
        denominator = sum(different_server_counter.values())  # Sum all values
        if denominator != 0:
            I_j[server_key] = numerator / denominator
        else:
            I_j[server_key] = 0  # Avoid division by zero

    F_j = {}
    for server_key in other_server_counter.keys():  # Iterate over dictionary keys
        numerator = different_server_counter[server_key]
        denominator = initial_server_counter[server_key] + other_server_counter[server_key]
        if denominator != 0:
            F_j[server_key] = numerator / denominator
        else:
            F_j[server_key] = 0  # Avoid division by zero

    # Print results
    print("I_j:", I_j)
    print("F_j:", F_j)
    # Write data to CSV file
    with open(csv_name_server, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Server', 'R_j_user', 'F_j_other', 'R_j_other', 'I_j', 'F_j'])
        for server_key in initial_server_counter.keys():
            writer.writerow(
                [server_key, initial_server_counter[server_key], different_server_counter[server_key],
                 other_server_counter[server_key], I_j.get(server_key, 0), F_j.get(server_key, 0)]
            )

    print(f"Data of migration server saved to {csv_name_server} ")

    logging.info(f"Simulation results saved to: {csv_file}")
    print(f"Simulation LOG saved to: {log_name}")
    logging.info("Simulation completed")
    