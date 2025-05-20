import json
import random
import logging
import experiments
import globals

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
        #print("Configuration file loaded.\n")
        data_configurations = json.load(f)
except Exception as e:
    print(f"Error loading configuration file: {e}")


def TaskAssignment(env, selected_server, task_id, required_ram, required_disk, task_priority,
                   arrival_time_system, num_hops, transfer_time, original_TaskPriority, initial_server_counter, different_server_counter, other_server_counter, estimated_execution_time, utility):
    '''
        Assign a task to a selected server and process it.

        :param env: The simulation environment.
        :param selected_server: The server to which the task will be assigned.
        :param task_id: The ID of the task.
        :param required_ram: RAM requirement for the task.
        :param required_disk: Disk space requirement for the task.
        :param task_priority: Priority of the task.
        :param arrival_time_system: Arrival time of the task in the system.
        :param num_hops: Number of hops to reach the selected server.
        :param transfer_time: Time required to transfer data.
        :param original_TaskPriority: Original task priority.

        :return: None
        '''

    global hop

    if initial_server_counter[selected_server.name] == 0 and different_server_counter == 0:
        other_server_counter += 1
    #print('Task Assignment')
    # Azzera il numero di hop
    hop = 0
    lunghezza_coda = len(list(selected_server.server_queue))
    higher_priority_tasks = [task for task in list(selected_server.server_queue) if task[3] == 1]
    low_priority_tasks = [task for task in list(selected_server.server_queue) if task[3] == 100]
    yield env.timeout(transfer_time)

    arrival_time_task_queue = env.now
    task = task_id, required_ram, required_disk, task_priority, arrival_time_system, estimated_execution_time, transfer_time, utility, num_hops, arrival_time_task_queue, original_TaskPriority

    selected_server.server_queue.append(task)

    with selected_server.process_queue.request(priority=task[3]) as request:
        print(f"Task {task_id} messo in coda sul server {selected_server.name} in {env.now:.2f} con priorità = {task_priority}. Tranfer Time = {transfer_time}")

        yield request
        start_time = env.now
        time_in_queue = start_time - arrival_time_task_queue

        yield env.timeout(estimated_execution_time)

        end_time = env.now
        execution_time = estimated_execution_time #end_time - start_time if start_time > 0 and end_time > 0 else 0
        #print("execution time task assignment", execution_time, 'task', task_id)

        service_time = estimated_execution_time + time_in_queue + transfer_time

        '''print(f"Task ID {task_id} eseguito sul server {selected_server.name}, Priorità: {task_priority} "
              f"Arrival Time in System: {arrival_time_system:.2f}, "
              f"start time: {start_time:.2f}, "
              f"rimasto in coda: {time_in_queue:.2f}, "
              f"lascia il sistema in {env.now:.2f}, "
              f"execution time {execution_time}, "
              f"Service time: {service_time:.2f}")'''

        priority_mapping = {100: "low", 1: "high"}
        task_p = priority_mapping.get(task_priority, "NaN")
        if task_p == "low":

            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, len(low_priority_tasks),
                                           original_TaskPriority, estimated_execution_time, transfer_time, selected_server.utility_value,  TMAX_exceeded=False, exec_after_set = False )
        elif task_p == "high":
            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, len(higher_priority_tasks),
                                           original_TaskPriority, estimated_execution_time, transfer_time, selected_server.utility_value, TMAX_exceeded=False, exec_after_set = False)
        else:
            selected_server.task_completed(task_id, task_p, arrival_time_system, arrival_time_task_queue,
                                           start_time, end_time, execution_time, service_time, time_in_queue,
                                           selected_server.name, num_hops, lunghezza_coda, original_TaskPriority, estimated_execution_time, transfer_time, selected_server.utility_value,
                                           TMAX_exceeded=False, exec_after_set = False )

        # Rimuovi il task completato dalla coda
        if task in selected_server.server_queue:
             selected_server.server_queue.remove(task)


Tmax_H = config["Tmax_H"]
Tmax_L = config["Tmax_H"]
MaxTry = config["max_try"]

def estimate_execution_time():
    # Valori presi dal file di configurazione (già in secondi)
    mean_seconds = config["CPU_timeout"]["mean"]
    min_seconds = config["CPU_timeout"]["min"]
    max_seconds = config["CPU_timeout"]["max"]

    estimated_time = experiments.truncated_exponential(mean=mean_seconds, lower=min_seconds, upper=max_seconds)
    #print(f"Tempo di esecuzione stimato: {estimated_time:.2f} secondi")
    return estimated_time

def SearchNode(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
               restart_time, download_time, task_priority, arrival_time_system, Tmax_high, Tmax_Low,
               Tmax_latency, initial_server_counter, different_server_counter, other_server_counter):
    '''
        Search for the most suitable server to assign a task, considering utility values, latency, and task priorities.

        This function evaluates the available servers based on their utility value and selects the best one
        based on the highest priority task and the given constraints (such as Tmax latency).

        It updates the counters for each server (initial, different, and other) and assigns the task to the selected server.

        :param env: The simulation environment.
        :param server_selected: The initially selected server for the task.
        :param task_id: The ID of the task to be assigned.
        :param required_ram: RAM requirement for the task.
        :param required_disk: Disk space requirement for the task.
        :param image_size: Size of the image associated with the task.
        :param Volume_size: Size of the volume associated with the task.
        :param restart_time: Time needed to restart the task.
        :param download_time: Time required for downloading the task's image.
        :param task_priority: Priority of the task (high or low).
        :param arrival_time_system: The time when the task arrives in the system.
        :param Tmax_high: High threshold for utility value.
        :param Tmax_Low: Low threshold for utility value.
        :param Tmax_latency: Latency threshold for the server selection.

        :return: None

        This function will either:
        - Assign the task to the most suitable server based on its utility value and priority,
        - Or recursively select another server if no suitable server is available within the latency threshold.
        '''
    global sorted_servers, transfer_time, hop, total_estimated_time
    #print(f'SearchNode, Server selezionato --> {server_selected.name}')

    # Stima il tempo di esecuzione del task
    estimated_execution_time = estimate_execution_time()

    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    #print(f'I server vicini al server {server_selected.name} sono: {[n.name for n in neighbors_at_distance_one]}')

    server_metrics = []

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        if bandwidth_to_server and latency_to_server is None:
            transfer_time = 0

        # Aggiorna il valore di utilità e i parametri relativi alla coda
        if neighbor == server_selected:
            server_selected.UpdateUtilityValue(env, estimated_execution_time, transfer_time, 0, download_time, server_selected, task_priority)
            total_estimated_time = estimated_execution_time + transfer_time
        else:
            neighbor.UpdateUtilityValue(env, estimated_execution_time, transfer_time, restart_time, download_time, neighbor, task_priority)
            total_estimated_time = estimated_execution_time + transfer_time + restart_time

        # Calcola il tempo atteso in coda usando Th_ij e Tl_ij
        if task_priority == 1:
            # Per task ad alta priorità, consideriamo solo Th_ij
            waiting_time_adjusted = neighbor.Th_ij + neighbor.waiting_time
            expected_completion_time = total_estimated_time + waiting_time_adjusted

        else:
            # Per task a bassa priorità, consideriamo sia Th_ij che Tl_ij
            waiting_time_adjusted = neighbor.Th_ij + neighbor.Tl_ij + neighbor.waiting_time
            expected_completion_time = total_estimated_time + waiting_time_adjusted

        # Aggiungi le metriche del server alla lista
        server_metrics.append({
            'server': neighbor,
            'utility_value': neighbor.utility_value,
            'estimated_total_time': total_estimated_time,
            'transfer_time': transfer_time,
            'queue_length': len(neighbor.server_queue),
            'waiting_time': waiting_time_adjusted,
            'orbitalSunset': neighbor.orbitalSunset,
            'Sunset': neighbor.elev_angle,
            'expected_completion_time': expected_completion_time
        })

    '''Modifica del criterio di ordinamento dei server per considerare:
        Prima il valore di utility (come prima)
        Poi il tempo totale stimato (tra 10 e 25 minuti esponenziale con media 15 minuti)
        Infine la lunghezza della coda
        In questo modo, a parità di utility value, verrà selezionato il server che dovrebbe completare il task più velocemente e con la coda più corta.'''

    # Filtra i server: esclude i server con orbitalSunset non valido e quelli che non riescono a completare il task in tempo
    server_metrics = [
        metrics for metrics in server_metrics
        if metrics['orbitalSunset'] is not None
           and metrics['orbitalSunset'] != 0
           and metrics['expected_completion_time'] < metrics['orbitalSunset']
    ]

    # Ordina i server in base ai criteri scelti (utility, tempo stimato, lunghezza della coda, ecc.)
    sorted_servers = sorted(server_metrics,
                            key=lambda x: (x['utility_value']))

    sorted_servers2 = sorted(server_metrics,
                            key=lambda x: (x['utility_value']/['orbitalSunset']))

    Tmax_high -= 2 * Tmax_latency

    #print("\nServer ordinati per metriche:")

    for metrics in sorted_servers:
            print(f"Server {metrics['server'].name}:")
            print(f"- Utility: {metrics['utility_value']:.2f}")
            print(f"- Tempo stimato esecuzione task: {metrics['estimated_total_time']:.2f}")
            print(f"- waiting_time: {metrics['waiting_time']:.2f}")
            print(f"- Tempo di completamento totale in base alla coda: {metrics['expected_completion_time']:.2f}")
            print(f"- Lunghezza coda: {metrics['queue_length']}")
            print(f"- Orbital Sunset: {metrics['orbitalSunset']}")
            print(f"- Transfer time: {metrics['transfer_time']}")

    # Converti la lista di dizionari in lista di server, escludendo quelli con orbitalSunset pari a 0 o None

    #Versione originale
    sorted_servers = [metrics['server'] for metrics in sorted_servers if metrics['expected_completion_time'] < Tmax_high ]
    sorted_servers_MOD = [metrics['server'] for metrics in sorted_servers if metrics['utility_value'] < Tmax_high ]

    #versione mod, con penalità aggiunta qui invece che nell'utility
    '''sorted_servers = [metrics['server'] for metrics in sorted_servers
                      if metrics['expected_completion_time'] < Tmax_high
                      and metrics['expected_completion_time'] < metrics['orbitalSunset']
                      and metrics['orbitalSunset'] not in (0, None)]'''

    '''sorted_servers2 = [metrics['server'] for metrics in sorted_servers
                      if metrics['utility_value'] < Tmax_high
                      and metrics['utility_value'] < metrics['orbitalSunset']
                      and metrics['orbitalSunset'] not in (0, None)]'''

    '''for server in sorted_servers:
         print(f"Server {server.name}: Utility Value = {server.utility_value}, orbitalSunset {server.orbitalSunset}")'''

    print(f'hop eseguiti = {hop}, server totali rimasti con utility = {len(sorted_servers)}')

    original_TaskPriority = task_priority

    initial_server_counter[server_selected.name] += 1

    if len(sorted_servers) > 0:
        server = sorted_servers.pop(0)

        if server != server_selected:
            different_server_counter[server_selected.name] += 1
            other_server_counter[server.name] += 1
            transfer_time = transfer_time + server.get_latency(server_selected)
            hop += 1

        #print(f'Seleziono il server con utility più bassa: {server.name}, priorità {task_priority}, lunghezza coda, {len(server.server_queue)}, tempo di attesa {server.Th_ij + server.Tl_ij + server.waiting_time}, AVG {server.AVG_service_time}')
        #print(server.waiting_time, 'tempo di attesa wt')

        # Parametri utili per la gestione della coda
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

        #print(
         #   f'server: {server.name}, priorità {task_priority},task execution time: {total_estimated_time}, lunghezza coda, {len(server.server_queue)}, tempo di attesa {server.Th_ij + server.Tl_ij + server.waiting_time}, AVG {server.AVG_service_time}, orbitalSunset: {server.orbitalSunset}, Sunset: {server.elev_angle}')

        yield from TaskAssignment(env, server, task_id, required_ram, required_disk, task_priority,
                                  arrival_time_system, hop, transfer_time, original_TaskPriority, initial_server_counter, different_server_counter, other_server_counter, estimated_execution_time, server.utility_value)

    else:
        if Tmax_high <= 0 or hop > MaxTry:
            #print("Tmax è arrivato a zero, termina la ricorsione.")
            priority_mapping = {100: "low", 1: "high"}
            task_p = priority_mapping.get(task_priority, "NaN")
            server_selected.task_completed(task_id, task_p, arrival_time_system, 0,
                                           0, 0, 0, 0, 0,
                                           server_selected.name, hop, 0, original_TaskPriority, estimated_execution_time, transfer_time, server_selected.utility_value, TMAX_exceeded=True, exec_after_set = False)
            if hop >= MaxTry:
                print(f'Termina ricorsione, superato il MaxTry, task {task_id} scartato')
            else: print(f'Termina ricorsione, task {task_id} scartato')
            hop = 0
            return
        else:
            available_servers = [neighbor for neighbor in neighbors_at_distance_one if neighbor != server_selected]
            ####prendere quello con sunset time maggiore
            random_server = random.choice(available_servers)
            Tmax_latency = random_server.get_latency(server_selected)
            transfer_time = transfer_time + random_server.get_latency(server_selected)
            hop += 1
            print(f"server random scelto {random_server}")
            print(
               f'server: {random_server.name}, priorità {task_priority},task execution time: {total_estimated_time}, lunghezza coda, {len(random_server.server_queue)}, tempo di attesa {random_server.Th_ij + random_server.Tl_ij + random_server.waiting_time}, AVG {random_server.AVG_service_time}, orbitalSunset: {random_server.orbitalSunset}, Sunset: {random_server.elev_angle}')

            yield env.process(
                SearchNode(env, random_server, task_id, required_ram, required_disk, image_size,
                           Volume_size, restart_time, download_time, task_priority, arrival_time_system,
                           Tmax_high, Tmax_Low, Tmax_latency, initial_server_counter, different_server_counter, other_server_counter))


def LocalScheduler(env, task_id, required_ram, required_disk, server, image_size, Volume_size, restart_time,
                   download_time, task_priority, arrival_time_system, initial_server_counter, different_server_counter, other_server_counter):
    # print('Local Scheduler')
    global hop  # Indica che la variabile hop è globale e non locale
    hop += 1  # Incrementa hop ogni volta che la funzione viene richiamata

    # controlla la configurazione se deve essere esclusa la parte della search_node.
    # se la search_node è esclusa, i server vengono scelti tramite roud-robin e non viene utilizzata l'utility.
    if config["search_node"] == 0:
        # print("Without search_node")
        yield from TaskAssignment(env, server, task_id, required_ram, required_disk, task_priority,
                                  arrival_time_system, hop)
    else:
        # print("With search_node")
        Tmax_latency = int(0)
        yield from SearchNode(env, server, task_id, required_ram, required_disk, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, Tmax_H,
                              Tmax_L, Tmax_latency, initial_server_counter, different_server_counter, other_server_counter)


def task(env, task_id, server, task_priority, initial_server_counter, different_server_counter, other_server_counter):
    # Calcola la media della distribuzione esponenziale
    #mean = (config["MI"]["min"] + config["MI"]["max"]) / 2

    # Calcola il tasso di arrivo (lambda) corrispondente
    #Avg_service_demand = 1 / mean

    # Genera un numero casuale distribuito esponenzialmente
    #MI = random.expovariate(Avg_service_demand)

    #required_cpu = random.choice([config["required_cpu"]["min"], config["required_cpu"]["max"]])  # CPU richiesta dal task
    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"][
        "max"])  # RAM richiesta dal task #######cercare quali distributioni caratterizzano tipicamente la richiesta di RAM
    required_disk = random.randint(config["required_disk"]["min"],
                                   config["required_disk"]["max"])  # Spazio su disco richiesto dal task
    image_size = random.uniform(config["image_size"]["min"], config["image_size"][
        "max"])  # Genera casualmente la dimensione dell'immagine con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container
    Volume_size = random.uniform(config["Volume_size"]["min"], config["Volume_size"][
        "max"])  # Genera casualmente la dimensione dell'Volume con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container

    #utilization_CPU = MI / (config["cpu_capacity"] * required_cpu)  # MI/(limits × C_i^max )
    # utilization_CPU = #MI / (config["cpu_capacity"] * required_cpu)  #MI/(limits × C_i^max )

    restart_time = random.uniform(config["restart_time"]["min"],
                                  config["restart_time"]["max"])  # Tempo di riavvio del task (ad esempio, in secondi)
    download_time = 0  # image_size / available_bandwidth
    arrival_time_system = env.now
    print(f"---> Task {task_id} (Priority: {task_priority}) arriva in {arrival_time_system:.2f}")

    yield from LocalScheduler(env, task_id, required_ram, required_disk, server, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, initial_server_counter, different_server_counter, other_server_counter)


def generate_tasks(env, initial_server_counter, different_server_counter, other_server_counter):

    global  priority_combination, arrival_time, selected_server
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
            raise ValueError("Unrecognized distribution type")

        yield env.timeout(arrival_time)
        
        # print(f"[Generate Task] index: {globals.next_server_index}")
        # [print(f"\tAccPoints: {acc.name}") for acc in globals.global_access_point]
        # ! Prendo il prossimo server in base al round robin dalla lista di access point
        globals.next_server_index = (globals.next_server_index + 1) % len(globals.global_access_point)
        selected_server = globals.global_access_point[globals.next_server_index]  # ho cambiato il nome

        priority_combination_string = config["priority_combination"]["distribution"]
        priority_combination_values = list(map(int, priority_combination_string.split("_")))
        priority_combination = experiments.priority_combination(*priority_combination_values)

        task_priority = priority_combination
        #print(f"Access Point Selezionato: {selected_server.satellite.name} task priority: {task_priority}")

        env.process(task(env, task_id, selected_server, task_priority, initial_server_counter, different_server_counter, other_server_counter))
        task_id += 1