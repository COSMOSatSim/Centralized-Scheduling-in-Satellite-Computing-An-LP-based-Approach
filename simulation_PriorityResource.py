import json
import math
import random

import simpy
import time
import logging
import threading
#from numpy import random
from skyfield.api import EarthSatellite

import experiments
from SaveCurrentSATOnFile import saveTLEOnFile
from user_based_topology import get_orbit_proximity, get_current_time, getLatency, are_satellites_equal, getAllSatOnMe, printSatList



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
    global hop
    other_server_counter = 0
    if initial_server_counter == 0 and different_server_counter == 0:
        other_server_counter += 1
    logging.debug('Task Assignment')
    # print('Task Assignment')
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
        # print(f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}")
        logging.debug(
            f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}")

        #print_stats(selected_server)

        yield request
        start_time = env.now
        time_in_queue = start_time - arrival_time_task_queue
        # yield env.timeout(utilization_CPU) #deprecated
        yield env.timeout(config["CPU_timeout"])  # msec
        end_time = env.now
        execution_time = (end_time - start_time)
        service_time = execution_time + time_in_queue + transfer_time
        logging.debug(f"Task ID {task_id} eseguito sul server {selected_server.name}, Priorità: {task_priority} "
                      f"Arrival Time in System: {arrival_time_system:.2f}, "
                      f"start time: {start_time:.2f}, "
                      f"rimasto in coda: {time_in_queue:.2f}, "
                      f"lascia il sistema in {env.now:.2f}, "
                      f"execution time {execution_time}, "
                      f"Service time: {service_time:.2f}")

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


initial_server_counter = [0] * config["topology"]
different_server_counter = [0] * config["topology"]
other_server_counter = [0] * config["topology"]

Tmax_H = config["Tmax_H"]
Tmax_L = config["Tmax_H"]


def SearchNode(env, server_selected, task_id, required_cpu, required_ram, required_disk, image_size, Volume_size,
               restart_time, download_time, task_priority, arrival_time_system, utilization_CPU, Tmax_high, Tmax_Low,
               Tmax_latency):
    global sorted_servers, initial_server_selected, different_server_counter, other_server_counter, transfer_time, hop

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

        print(
            f'server {neighbor.name}, latenza {latency_to_server}, banda {bandwidth_to_server}, Transfer time {transfer_time}')
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
        print(f"Server {server.name}: Utility Value = {server.utility_value}")
        logging.debug(f"Server {server.name}: Utility Value = {server.utility_value}")

    print(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    for server in sorted_servers:
        print(f"Server {server.name}: Utility Value = {server.utility_value} ")
        logging.debug(f"Server {server.name}: Utility Value = {server.utility_value} ")
    print(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    logging.debug(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    original_TaskPriority = task_priority

    #initial_server_counter[int(server_selected.name) - 1] += 1

    if len(sorted_servers) > 0:
        server = sorted_servers.pop(0)

        if server != server_selected:
            #different_server_counter[int(server_selected.name) - 1] += 1
            #other_server_counter[int(server.name) - 1] += 1
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

def compute_distances_from_target_satellite(sat, closerSatellite_Sorted, t):
    """
    Compute the distances from the target satellite to other satellites.

    :param sat: The target satellite.
    :param closerSatellite_Sorted: List of satellites sorted by proximity.
    :param t: Current time.

    :return: List of tuples containing satellites and their distances from the target satellite.
    """
    
    vector_Sat_Topology = []
    for i in range(0, len(closerSatellite_Sorted)):
        if are_satellites_equal(sat.satellite, closerSatellite_Sorted[i].satellite):
            pass
        else:
            proximity = get_orbit_proximity(sat.get_satellite() , closerSatellite_Sorted[i].get_satellite(), t)         
            if  proximity < config["Laser_Comunication_Range"] :                                # Check laser distance
                vector_Sat_Topology.append((closerSatellite_Sorted[i], proximity)) 

    sat_vector_Topology_sorted = sorted(vector_Sat_Topology, key=lambda x: x[1])
    return sat_vector_Topology_sorted

#Richiamiamo questa funzione periodicamente per aggiornare la topologia
def periodic_Recall():
    global edge_servers
    time.sleep(config["topology_sleeping_time"] * 60)
    edge_servers = create_topology_dome()


def create_topology_dome():
    
    global global_access_point
    time = get_current_time()

    edge_servers = []
    acc_point ,satellites_dome, satellites_buffer = getAllSatOnMe(time = time)
    num_sat_dome, num_sat_buffer, num_AP = len(satellites_dome), len(satellites_buffer), len(acc_point)

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
        neighbor = compute_distances_from_target_satellite(current_server, edge_servers, time)
        for n in neighbor:
            current_server.add_neighbor(n[0], 1, getLatency(n[1]), 
                                        random.uniform(config["available_bandwidth"]["min"], config["available_bandwidth"]["max"]))
        print(current_server)
    return edge_servers

if __name__ == "__main__":
    
    #global edge_servers

    # Setup and start the simulation
    random.seed(config["seed"])
    
    env = simpy.Environment()
    hop = 0  # Inizializza la variabile hop a zero
    edge_servers = create_topology_dome()

    #Gestione del Thread per la creazione della topologia Periodicamente
    thread = threading.Thread(target=periodic_Recall)
    thread.daemon = True 
    thread.start()

    env.process(generate_tasks(env))
    env.run(config['simulation_duration'])

    end_time = time.time()    # Tempo finale

    