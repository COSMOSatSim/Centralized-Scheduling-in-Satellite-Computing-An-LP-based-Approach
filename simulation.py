import json, json5
import random
import logging
import experiments
import globals
from Task import Task, assign_resolution

hop = 0  # Inizializza la variabile hop a zero

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

simulation_results = []

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

def TaskAssignment(env, selected_server, task_id, required_ram, required_disk, task_priority,
                   arrival_time_system, num_hops, transfer_time, original_TaskPriority,
                   initial_server_counter, different_server_counter, other_server_counter,
                   estimated_execution_time, utility, task_type="CPU+NET"):
    """
    Assign a task to a selected server and process it through CPU and/or Network queues.
    Uses SimPy resources selected_server.cpu_dev and selected_server.net_dev (PriorityResource).
    """
    task_p_label = "high" if task_priority == 1 else "low"

    # L'energia del trasferimento viene sottratta e verificata in SearchNode
    yield env.timeout(transfer_time)
    arrival_time_task_queue = env.now

    eps_cpu, eps_net = 0.0, 0.0
    start_time = env.now
    time_in_queue = 0.0

    # NEW: Logica di routing basata sul tipo di task
    if task_type in ("Generic_Service", "CPU_Intensive"):
        C_sen = config.get("C_sen", 1e9)
        e_coeff = config.get("energy_coefficient", 5e-26)
        eps_cpu = selected_server.compute_execution_energy(estimated_execution_time, C_sen, e=e_coeff)

        if selected_server.energy < eps_cpu:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for CPU",
                                                 task_priority)
            return

        with selected_server.cpu_dev.request(priority=task_priority) as req_cpu:
            yield req_cpu
            time_in_queue = env.now - arrival_time_task_queue
            yield env.timeout(estimated_execution_time)

            selected_server.energy -= eps_cpu

    elif task_type in ("CPU_and_Data_Intensive"):
        C_sen = config.get("C_sen", 1e9)
        e_coeff = config.get("energy_coefficient", 5e-26)
        eps_cpu = selected_server.compute_execution_energy(estimated_execution_time, C_sen, e=e_coeff)

        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
        data_MB = (required_ram + required_disk)
        data_bytes = data_MB * (1024 ** 2)
        eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

        if selected_server.energy < (eps_cpu + eps_net):
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system,
                                                 "Insufficient Energy for CPU+NET", task_priority)
            return

        with selected_server.cpu_dev.request(priority=task_priority) as req_cpu:
            yield req_cpu
            Wc = env.now - arrival_time_task_queue
            yield env.timeout(estimated_execution_time)
            selected_server.energy -= eps_cpu

            with selected_server.net_dev.request(priority=task_priority) as req_net:
                yield req_net
                Wn = env.now - arrival_time_task_queue

                net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
                yield env.timeout(net_time)
                selected_server.energy -= eps_net

                time_in_queue = Wc + Wn

    elif task_type == "Batch":
        # Solo coda Network
        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
        data_MB = (required_ram + required_disk)
        data_bytes = data_MB * (1024 ** 2)
        eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

        if selected_server.energy < eps_net:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for NET",
                                                 task_priority)
            return

        with selected_server.net_dev.request(priority=task_priority) as req_net:
            yield req_net
            time_in_queue = env.now - arrival_time_task_queue

            net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
            yield env.timeout(net_time)
            selected_server.energy -= eps_net

    end_time = env.now
    execution_time = end_time - start_time
    service_time = execution_time + transfer_time

    print(f"Task {task_id} Routing Start")
    category, resolution = assign_resolution(required_ram, required_disk)
    task_OBS = Task(task_id, selected_server.name, 'OBS', env.now, category, resolution)
    if selected_server.elev_angle < config["Phi_max"] - config["Phi_buffer"]:
        task_OBS.label = 'SEN_OUT_OF_BUFF'
        print(f"{selected_server} {selected_server.elev_angle}° {task_OBS.id} set as {task_OBS.label}")

    selected_server.tasks.append(task_OBS)
    globals.gbl_tasks.append(task_OBS)

    qlen = len(selected_server.cpu_dev.queue) + len(selected_server.net_dev.queue)

    # NEW: Passa il tipo di task e i valori energetici
    selected_server.task_completed(
        task_id, task_p_label, task_type, arrival_time_system, arrival_time_task_queue,
        start_time, end_time, execution_time, service_time, time_in_queue,
        selected_server.name, num_hops, qlen,
        original_TaskPriority, estimated_execution_time, transfer_time,
        utility, TMAX_exceeded=False, exec_after_set=False,
        eps_cpu=eps_cpu, eps_net=eps_net
    )
Tmax_H = config["Tmax_H"]
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
               restart_time, download_time, task_priority, arrival_time_system, Tmax_high,
               Tmax_latency, initial_server_counter, different_server_counter, other_server_counter,
               task_type="CPU+NET"):
    global hop
    estimated_execution_time = estimate_execution_time()

    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    server_metrics = []

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server is not None and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        else:
            transfer_time = 0.0

        # NEW: Calcola il punteggio di selezione in base al tipo di task
        # Richiede che tu abbia già aggiunto la funzione get_selection_score in EdgeServer.py
        # come spiegato nella risposta precedente.
        selection_score = neighbor.get_selection_score(task_type)

        server_metrics.append({
            'server': neighbor,
            'selection_score': selection_score,  # NEW: Usa il nuovo punteggio di selezione
            'transfer_time': transfer_time,
            'orbitalSunset': neighbor.orbitalSunset,
        })

    # Filtra i server non validi
    # Nota: questa logica di filtro non è stata modificata
    server_metrics = [m for m in server_metrics
                      if m['orbitalSunset'] not in (None, 0)]

    if not server_metrics:
        print(f"[Task {task_id}] Nessun server valido trovato.")
        return

    # NEW: Ordina i server in base al nuovo punteggio di selezione, in ordine decrescente
    sorted_servers = sorted(server_metrics, key=lambda x: x['selection_score'], reverse=True)

    chosen = sorted_servers.pop(0)
    server = chosen['server']
    transfer_time = chosen['transfer_time']  # NEW: Ottieni il transfer_time dal dizionario

    # Aggiorna contatori
    initial_server_counter[server_selected.name] += 1
    if server != server_selected:
        different_server_counter[server_selected.name] += 1
        other_server_counter[server.name] += 1
        hop += 1

        bw_MBps = server_selected.get_bandwidth(server)
        if bw_MBps is None:
            bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
        data_MB = (image_size + Volume_size)
        data_bytes = data_MB * (1024 ** 2)
        if bw_Bps > 0:
            eps_net = server_selected.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))
        else:
            eps_net = 0.0
        server_selected.energy -= eps_net

        print(f"[{env.now:.2f}] [Task {task_id}] Routed {server_selected.name} -> {server.name} | "
              f"E_NET={eps_net:.6f} J | Remaining={server_selected.energy:.2f} J")

    # Chiamo TaskAssignment sul server scelto
    yield from TaskAssignment(env, server, task_id, required_ram, required_disk,
                              task_priority, arrival_time_system, hop,
                              transfer_time, task_priority,
                              initial_server_counter, different_server_counter, other_server_counter,
                              estimated_execution_time, server.utility_value, task_type=task_type)

def LocalScheduler(env, task_id, required_ram, required_disk, server, image_size, Volume_size, restart_time,
                   download_time, task_priority, arrival_time_system, initial_server_counter, different_server_counter, other_server_counter, task_type):
    # print('Local Scheduler')
    global hop
    hop += 1

    Tmax_latency = int(0)
    yield from SearchNode(env, server, task_id, required_ram, required_disk, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, Tmax_H,
                               Tmax_latency, initial_server_counter, different_server_counter, other_server_counter, task_type)


def task(env, task_id, server, task_priority, initial_server_counter, different_server_counter, other_server_counter):
    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"]["max"])
    required_disk = random.randint(config["required_disk"]["min"], config["required_disk"]["max"])
    image_size = random.uniform(config["image_size"]["min"], config["image_size"]["max"])
    Volume_size = random.uniform(config["Volume_size"]["min"], config["Volume_size"]["max"])
    restart_time = random.uniform(config["restart_time"]["min"], config["restart_time"]["max"])
    download_time = 0
    arrival_time_system = env.now

    task_type = "Generic_Service" ## Low resolution 10-88k
    if task_priority == 1:
        if random.random() < 0.5:
            task_type = "CPU_Intensive" ## Low resolution
        else:
            task_type = "CPU_and_Data_Intensive" ## Medium, high and very high resolution
    elif task_priority == 0:
        if random.random() < 0.5:
            task_type = "Data_Intensive" ## come batch, High e very high


    print(f"---> Task {task_id} (Priority: {task_priority}, Type: {task_type}) arriva in {arrival_time_system:.2f}")

    yield from LocalScheduler(env, task_id, required_ram, required_disk, server, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, initial_server_counter,
                              different_server_counter, other_server_counter, task_type)


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