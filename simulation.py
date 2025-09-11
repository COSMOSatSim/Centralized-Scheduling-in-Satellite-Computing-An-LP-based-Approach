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
    # Simulo il tempo di trasferimento accumulato fino ad ora (dal SearchNode)
    yield env.timeout(transfer_time)
    arrival_time_task_queue = env.now

    eps_cpu, eps_net = 0.0, 0.0
    start_time = env.now


    # === CPU Queue (simpy PriorityResource) ===
    if task_type in ("CPU", "CPU+NET", "REALTIME"):
        # usa la risorsa SimPy definita nella classe EdgeServer
        with selected_server.cpu_dev.request(priority=task_priority) as req_cpu:
            yield req_cpu
            time_in_queue = env.now - arrival_time_task_queue

            # esecuzione CPU
            yield env.timeout(estimated_execution_time)

            # Consumo energetico CPU (usa C_sen da config)
            C_sen = config.get("C_sen", 1e9)
            e_coeff = config.get("energy_coefficient", 5e-26)
            eps_cpu = selected_server.compute_execution_energy(estimated_execution_time, C_sen, e=e_coeff)
            selected_server.energy -= eps_cpu

            print(f"[{env.now:.2f}] [Task {task_id}] CPU done on {selected_server.name} | "
                  f"E_CPU={eps_cpu:.6f} J | Remaining={selected_server.energy:.2f} J")

    # === Network Queue (simpy PriorityResource) ===
    if task_type in ("CPU+NET", "NET"):
        with selected_server.net_dev.request(priority=task_priority) as req_net:
            yield req_net
            # --- UNITÀ: required_ram/required_disk sono in MB (config),
            #     available_bandwidth è in MB/s (config).
            # Converto esplicitamente in bytes e bytes/s per coerenza.
            bw_MBps = config.get("available_bandwidth", {}).get("min", 0)  # MB/s
            bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0  # bytes/s
            data_MB = (required_ram + required_disk)  # MB
            data_bytes = data_MB * (1024 ** 2)  # bytes

            net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
            yield env.timeout(net_time)

            # consumo energia rete (Ptrasm dal config)
            eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))
            selected_server.energy -= eps_net

            print(f"[{env.now:.2f}] [Task {task_id}] NET done on {selected_server.name} | "
                  f"E_NET={eps_net:.6f} J | Remaining={selected_server.energy:.2f} J")

    end_time = env.now
    execution_time = end_time - start_time
    service_time = execution_time + transfer_time
    # se il task è entrato nella coda prima di essere servito, time_in_queue lo abbiamo calcolato; altrimenti 0
    try:
        time_in_queue = time_in_queue
    except UnboundLocalError:
        time_in_queue = 0.0

    # Controllo lunghezza code come somma delle code SimPy (liste .queue)
    qlen = len(selected_server.cpu_dev.queue) + len(selected_server.net_dev.queue)

    # Registra completamento (nota: task_priority originale lo passiamo come stringa)
    task_p_label = "high" if task_priority == 1 else "low"
    selected_server.task_completed(
        task_id, task_p_label, arrival_time_system, arrival_time_task_queue,
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
    """
    Search for the most suitable server for task assignment, considering CPU/NET queues, deadlines and energy.
    """

    global hop
    estimated_execution_time = estimate_execution_time()

    neighbors_at_distance_one = server_selected.get_neighbors()
    # include server_selected per possibilità di esecuzione locale
    neighbors_at_distance_one.append(server_selected)

    server_metrics = []
    transfer_time = 0.0

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)  # expected MB/s

        # Stima tempo trasferimento (nota: non convertiamo qui per EPS_NET; solo tempo)
        if bandwidth_to_server is not None and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        else:
            transfer_time = 0.0

        # Aggiorna utilità (la funzione interna calcola Wcpu/Wnet usando le queue attuali)
        neighbor.UpdateUtilityValue(env, estimated_execution_time, transfer_time,
                                    restart_time, download_time, neighbor, task_priority)

        # Calcolo attesa nelle code (W_cpu e W_net sono metodi di EdgeServer)
        if task_type == "CPU":
            waiting_time_adjusted = neighbor.W_cpu(env.now)
        elif task_type == "NET":
            waiting_time_adjusted = neighbor.W_net(env.now)
        else:  # CPU+NET o REALTIME
            waiting_time_adjusted = neighbor.W_cpu(env.now) + neighbor.W_net(env.now)

        expected_completion_time = estimated_execution_time + transfer_time + waiting_time_adjusted

        server_metrics.append({
            'server': neighbor,
            'utility_value': neighbor.utility_value,
            'estimated_total_time': estimated_execution_time + transfer_time,
            'transfer_time': transfer_time,
            'queue_length': len(neighbor.cpu_dev.queue) + len(neighbor.net_dev.queue),
            'waiting_time': waiting_time_adjusted,
            'orbitalSunset': neighbor.orbitalSunset,
            'expected_completion_time': expected_completion_time
        })

    # Filtra server non validi (sunset e tempo stimato)
    server_metrics = [m for m in server_metrics
                      if m['orbitalSunset'] not in (None, 0)
                      and m['expected_completion_time'] < m['orbitalSunset']]

    # Ordinamenti
    sorted_servers = sorted(server_metrics, key=lambda x: x['utility_value'])
    if config.get("SearchNode", "") == "ERT/Sunset":
        sorted_servers = sorted(server_metrics,
                                key=lambda x: (x['estimated_total_time'] / x['orbitalSunset'],
                                               -x['orbitalSunset']))

    Tmax_high -= 2 * Tmax_latency

    if not sorted_servers:
        print(f"[Task {task_id}] Nessun server valido trovato.")
        return

    # Seleziono il miglior server
    chosen = sorted_servers.pop(0)
    server = chosen['server']

    # Aggiorna contatori
    initial_server_counter[server_selected.name] += 1
    if server != server_selected:
        different_server_counter[server_selected.name] += 1
        other_server_counter[server.name] += 1
        hop += 1

        # Calcolo E_NET per l'inoltro effettivo (qui converto MB -> bytes)
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
    # original_TaskPriority lo passiamo come task_priority se non abbiamo altro
    yield from TaskAssignment(env, server, task_id, required_ram, required_disk,
                              task_priority, arrival_time_system, hop,
                              transfer_time, task_priority,
                              initial_server_counter, different_server_counter, other_server_counter,
                              estimated_execution_time, server.utility_value, task_type=task_type)


def LocalScheduler(env, task_id, required_ram, required_disk, server, image_size, Volume_size, restart_time,
                   download_time, task_priority, arrival_time_system, initial_server_counter, different_server_counter, other_server_counter):
    # print('Local Scheduler')
    global hop  # Indica che la variabile hop è globale e non locale
    hop += 1  # Incrementa hop ogni volta che la funzione viene richiamata

    Tmax_latency = int(0)
    yield from SearchNode(env, server, task_id, required_ram, required_disk, image_size, Volume_size,
                              restart_time, download_time, task_priority, arrival_time_system, Tmax_H,
                               Tmax_latency, initial_server_counter, different_server_counter, other_server_counter)


def task(env, task_id, server, task_priority, initial_server_counter, different_server_counter, other_server_counter):
    #required_cpu = random.choice([config["required_cpu"]["min"], config["required_cpu"]["max"]])  # CPU richiesta dal task
    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"][
        "max"])  # RAM richiesta dal task #######cercare quali distributioni caratterizzano tipicamente la richiesta di RAM
    required_disk = random.randint(config["required_disk"]["min"],
                                   config["required_disk"]["max"])  # Spazio su disco richiesto dal task
    image_size = random.uniform(config["image_size"]["min"], config["image_size"][
        "max"])  # Genera casualmente la dimensione dell'immagine con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container
    Volume_size = random.uniform(config["Volume_size"]["min"], config["Volume_size"][
        "max"])  # Genera casualmente la dimensione dell'Volume con media di 1 GB ###cercare quali distributioni caratterizzano tipicamente la dimensione delle immagini dei container

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