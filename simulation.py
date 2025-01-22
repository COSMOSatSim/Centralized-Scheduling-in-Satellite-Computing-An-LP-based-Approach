import json
import random
import logging
import experiments
import globals
from topology import update_counters_dictionary

hop = 0  # Inizializza la variabile hop a zero

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

simulation_results = []

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

# Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
try:
    with open("data/configurations.json", "r") as f:
        print("Configuration file loaded.\n")
        data_configurations = json.load(f)
except Exception as e:
    print(f"Error loading configuration file: {e}")


def TaskAssignment(env, selected_server, task_id, required_cpu, required_ram, required_disk, task_priority,
                   arrival_time_system, utilization_CPU, num_hops, transfer_time, original_TaskPriority, initial_server_counter, different_server_counter, other_server_counter):
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
    if initial_server_counter == 0 and different_server_counter == 0:
        other_server_counter += 1
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
        print(
            f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}")

        yield request
        start_time = env.now
        time_in_queue = start_time - arrival_time_task_queue

        # Valori presi dal file di configurazione (già in secondi)
        mean_seconds = config["CPU_timeout"]["mean"]  # Ad esempio, 900
        min_seconds = config["CPU_timeout"]["min"]  # Ad esempio, 600
        max_seconds = config["CPU_timeout"]["max"]  # Ad esempio, 1500

        yield env.timeout(experiments.truncated_exponential(mean=mean_seconds, lower=min_seconds, upper=max_seconds))

        end_time = env.now
        execution_time = end_time - start_time if start_time > 0 and end_time > 0 else 0
        print("execution time task assignment", execution_time, 'task', task_id)

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
               Tmax_latency, initial_server_counter, different_server_counter, other_server_counter):
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
    global sorted_servers, transfer_time, hop
    print(f'SearchNode, Server selezionato --> {server_selected.name}')

    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    print(f'I server vicini al server {server_selected.name} sono: {[n.name for n in neighbors_at_distance_one]}')

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        else:
            transfer_time = 0

        if neighbor == server_selected:
            server_selected.UpdateUtilityValue(env, required_cpu, transfer_time, 0, download_time, server_selected,
                                               task_priority)
        else:
            neighbor.UpdateUtilityValue(env, required_cpu, transfer_time, restart_time, download_time, neighbor,
                                        task_priority)
        #print(f'server {neighbor.name}, latenza {latency_to_server}, banda {bandwidth_to_server}, Transfer time {transfer_time}')

    sorted_servers = sorted(neighbors_at_distance_one, key=lambda server: server.utility_value)

    Tmax_high -= 2 * Tmax_latency

    sorted_servers = [server for server in sorted_servers if server.utility_value < Tmax_high]

    for server in sorted_servers:
        print(f"Server {server.name}: Utility Value = {server.utility_value} ")
    print(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')
    original_TaskPriority = task_priority

    initial_server_counter[server_selected.name] += 1

    if len(sorted_servers) > 0:
        server = sorted_servers.pop(0)

        if server != server_selected:
            different_server_counter[server_selected.name] += 1
            other_server_counter[server.name] += 1
            hop += 1

        print(f'Seleziono il server con utility più bassa: {server.name}')

        AVG_service_time = server.AVG_service_time
        Th_ij = server.Th_ij
        Tl_ij = server.Th_ij + server.Tl_ij
        waiting_time = server.waiting_time

        if waiting_time <= AVG_service_time:
            task_priority = 1
            print(f"Task {task_id} assegnato alla coda ad alta priorità")
        elif Th_ij <= waiting_time <= Tl_ij:
            print(f"Task {task_id} mantenuto nella sua coda di priorità {task_priority}")
        else:
            task_priority = 100
            print(f"Task {task_id} assegnato alla coda a bassa priorità")

        yield from TaskAssignment(env, server, task_id, required_cpu, required_ram, required_disk, task_priority,
                                  arrival_time_system, utilization_CPU, hop, transfer_time, original_TaskPriority, initial_server_counter, different_server_counter, other_server_counter)

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

            yield env.process(
                SearchNode(env, random_server, task_id, required_cpu, required_ram, required_disk, image_size,
                           Volume_size, restart_time, download_time, task_priority, arrival_time_system,
                           utilization_CPU, Tmax_high, Tmax_Low, Tmax_latency, initial_server_counter, different_server_counter, other_server_counter))


def LocalScheduler(env, task_id, required_cpu, required_ram, required_disk, server, image_size, Volume_size, restart_time,
                   download_time, task_priority, arrival_time_system, utilization_CPU, initial_server_counter, different_server_counter, other_server_counter):
    # print('Local Scheduler')
    global hop  # Indica che la variabile hop è globale e non locale
    hop += 1  # Incrementa hop ogni volta che la funzione viene richiamata

    # controlla la configurazione se deve essere esclusa la parte della search_node.
    # se la search_node è esclusa, i server vengono scelti tramite roud-robin e non viene utilizzata l'utility.
    if config["search_node"] == 0:
        # print("Without search_node")
        yield from TaskAssignment(env, server, task_id, required_cpu, required_ram, required_disk, task_priority,
                                  arrival_time_system, utilization_CPU, hop)
    else:
        # print("With search_node")
        Tmax_latency = int(0)
        yield from SearchNode(env, server, task_id, required_cpu, required_ram, required_disk, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, utilization_CPU, Tmax_H,
                              Tmax_L, Tmax_latency, initial_server_counter, different_server_counter, other_server_counter)


def task(env, task_id, server, task_priority, initial_server_counter, different_server_counter, other_server_counter):
    # Calcola la media della distribuzione esponenziale
    mean = (config["MI"]["min"] + config["MI"]["max"]) / 2

    # Calcola il tasso di arrivo (lambda) corrispondente
    Avg_service_demand = 1 / mean

    # Genera un numero casuale distribuito esponenzialmente
    MI = random.expovariate(Avg_service_demand)

    required_cpu = random.choice(
        [config["required_cpu"]["min"], config["required_cpu"]["max"]])  # CPU richiesta dal task
    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"][
        "max"])  # RAM richiesta dal task #######cercare quali distributioni caratterizzano tipicamente la richiesta di RAM
    required_disk = random.randint(config["required_disk"]["min"],
                                   config["required_disk"]["max"])  # Spazio su disco richiesto dal task
    image_size = random.uniform(config["image_size"]["min"], config["image_size"][
        "max"])  # Genera casualmente la dimensione dell'immagine con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container
    Volume_size = random.uniform(config["Volume_size"]["min"], config["Volume_size"][
        "max"])  # Genera casualmente la dimensione dell'Volume con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container

    utilization_CPU = MI / (config["cpu_capacity"] * required_cpu)  # MI/(limits × C_i^max )
    # utilization_CPU = #MI / (config["cpu_capacity"] * required_cpu)  #MI/(limits × C_i^max )

    restart_time = random.uniform(config["restart_time"]["min"],
                                  config["restart_time"]["max"])  # Tempo di riavvio del task (ad esempio, in secondi)
    download_time = 0  # image_size / available_bandwidth
    arrival_time_system = env.now
    print(f"---> Task {task_id} (Priority: {task_priority}) arriva in {arrival_time_system:.2f}")

    yield from LocalScheduler(env, task_id, required_cpu, required_ram, required_disk, server, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, utilization_CPU, initial_server_counter, different_server_counter, other_server_counter)


# Dichiarazione di una variabile globale per tenere traccia del prossimo server da selezionare


def generate_tasks(env, initial_server_counter, different_server_counter, other_server_counter):

    global next_server_index, priority_combination, arrival_time, selected_server, global_access_point
    print('Genero i task')

    task_id = 1

    while True:
        # Read the distribution type from the configuration
        distribution_type = config["generate_tasks"]["distribution"]

        # Get the corresponding function based on the distribution type
        distribution_function = getattr(experiments, distribution_type, None)

        # Check if the function exists
        if distribution_function is not None and callable(distribution_function):
            arrival_time = distribution_function('Task')  # Inter arrival time, tempo tra l'arrivo di 2 task.
        else:
            logging.debug(f"Unrecognized or invalid distribution type: {distribution_type}")
            raise ValueError("Unrecognized distribution type")

        yield env.timeout(arrival_time)
        
        print(f"[Generate Task] index: {globals.next_server_index}")
        [print(f"\tAccPoints: {acc.name}") for acc in globals.global_access_point]
        # ! Prendo il prossimo server in base al round robin dalla lista di access point
        globals.next_server_index = (globals.next_server_index + 1) % len(globals.global_access_point)
        selected_server = globals.global_access_point[globals.next_server_index]  # ho cambiato il nome

        priority_combination_string = config["priority_combination"]["distribution"]
        priority_combination_values = list(map(int, priority_combination_string.split("_")))
        priority_combination = experiments.priority_combination(*priority_combination_values)

        task_priority = priority_combination
        print(f"Access Point Selezionato: {selected_server.satellite.name} task priority: {task_priority}")

        env.process(task(env, task_id, selected_server, task_priority, initial_server_counter, different_server_counter, other_server_counter))
        task_id += 1