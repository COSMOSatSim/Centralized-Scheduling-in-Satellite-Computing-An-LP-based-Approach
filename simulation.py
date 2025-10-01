import json5
import random
import experiments
import globals
from Task import Task, assign_resolution

hop = 0  # Inizializza la variabile hop a zero

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

def TaskAssignment(env, selected_server, task_id, required_ram, required_disk, image_size,
                   arrival_time_system, num_hops, transfer_time,
                   estimated_execution_time, task_type):
    """
    Assign a task to a selected server and process it through CPU and/or Network queues.
    Uses SimPy resources selected_server.cpu_dev and selected_server.net_dev (Resource).
    """

    # Leggi il flag di configurazione
    ENABLE_MONITORING = config.get("enable_queue_monitoring", False)

    category, resolution = assign_resolution(required_ram, required_disk)
    task_OBS = Task(task_id, selected_server.name, 'OBS', env.now, category, resolution)
    bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
    bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps else 0.0

    # Inizializza gli attributi solo se il monitoraggio è attivo
    if ENABLE_MONITORING:
        task_OBS.d_cpu = estimated_execution_time
        task_OBS.d_net = (image_size * (1024**2)) / bw_Bps if bw_Bps > 0 else 0.0 # Usiamo la dimensione del dato come richiesta NET
        task_OBS.deadline = arrival_time_system + Tmax_H

    # L'energia del trasferimento viene sottratta e verificata in SearchNode
    yield env.timeout(transfer_time)
    arrival_time_task_queue = env.now

    eps_cpu, eps_net = 0.0, 0.0
    start_time = env.now
    time_in_queue = 0.0

    # Logica di routing basata sul tipo di task
    if task_type in ("Generic_Service", "CPU_Intensive"):
        C_sen = config.get("C_sen", 1e9)
        e_coeff = config.get("energy_coefficient", 5e-26)
        eps_cpu = selected_server.compute_execution_energy(estimated_execution_time, C_sen, e=e_coeff)

        if selected_server.energy - selected_server.energy_reserved < eps_cpu:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for CPU")
            return
        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps else 0.0

        Wc = selected_server.W_cpu(estimated_execution_time)
        d_cpu = estimated_execution_time
        d_net = (image_size * (1024 ** 2)) / bw_Bps if bw_Bps > 0 else 0.0
        R = Wc + d_cpu + d_net
        D_r = Tmax_H
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return

        selected_server.energy_reserved += eps_cpu

        with selected_server.cpu_dev.request() as req_cpu:
            if ENABLE_MONITORING:
                    req_cpu.task_data = task_OBS
            yield req_cpu
            time_in_queue = env.now - arrival_time_task_queue
            yield env.timeout(estimated_execution_time)

            selected_server.energy -= eps_cpu
            BANDWIDTH_TO_GU_BPS = config.get("Bandwidth_to_GU_Bps", 100000)
            file_size_bytes = image_size * (1024 ** 2)
            delay_to_transfer = file_size_bytes / BANDWIDTH_TO_GU_BPS
            yield env.timeout(delay_to_transfer)
        selected_server.energy_reserved -= eps_cpu

    elif task_type in ("CPU_and_Data_Intensive"):
        C_sen = config.get("C_sen", 1e9)
        e_coeff = config.get("energy_coefficient", 5e-26)
        eps_cpu = selected_server.compute_execution_energy(estimated_execution_time, C_sen, e=e_coeff)

        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
        data_MB = image_size
        data_bytes = data_MB * (1024 ** 2)
        eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

        if selected_server.energy - selected_server.energy_reserved < (eps_cpu + eps_net):
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system,
                                                 "Insufficient Energy for CPU+NET")
            return
        # Qui d_cpu e d_net sono i tempi di servizio per il task R
        d_cpu = estimated_execution_time
        d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
        Wc = selected_server.W_cpu(d_cpu)
        Wn = selected_server.W_net(d_net)
        R = Wc + d_cpu + Wn + d_net
        D_r = Tmax_H
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return
        selected_server.energy_reserved += (eps_cpu + eps_net)

        with selected_server.cpu_dev.request() as req_cpu:
            if ENABLE_MONITORING:
                    req_cpu.task_data = task_OBS
            yield req_cpu
            Wc = env.now - arrival_time_task_queue
            yield env.timeout(estimated_execution_time)
            selected_server.energy -= eps_cpu

            with selected_server.net_dev.request() as req_net:
                if ENABLE_MONITORING:
                        req_net.task_data = task_OBS
                yield req_net
                Wn = env.now - arrival_time_task_queue

                net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
                yield env.timeout(net_time)
                selected_server.energy -= eps_net

                time_in_queue = Wc + Wn
        selected_server.energy_reserved -= (eps_cpu + eps_net)

    elif task_type == "Batch":
        print('Arrivato task BATCH')
        # Solo coda Network
        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
        data_MB = image_size
        data_bytes = data_MB * (1024 ** 2)
        eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

        if selected_server.energy - selected_server.energy_reserved < eps_net:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for NET")
            return
        d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
        Wn = selected_server.W_net(d_net)
        R = Wn + d_net
        D_r = Tmax_H
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return
        selected_server.energy_reserved += eps_net

        with selected_server.net_dev.request() as req_net:
            if ENABLE_MONITORING:
                    req_net.task_data = task_OBS
            yield req_net
            time_in_queue = env.now - arrival_time_task_queue

            net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
            yield env.timeout(net_time)
            selected_server.energy -= eps_net
        selected_server.energy_reserved -= eps_net

    end_time = env.now
    execution_time = end_time - start_time
    service_time = execution_time + transfer_time

    print(f"Task {task_id} Routing Start")
    selected_server.tasks.append(task_OBS)
    globals.gbl_tasks.append(task_OBS)

    if selected_server.elev_angle < config["Phi_max"] - config["Phi_buffer"]:
        task_OBS.label = 'SEN_OUT_OF_BUFF'
        print(f"{selected_server} {selected_server.elev_angle}° {task_OBS.id} set as {task_OBS.label}")

    qlen = len(selected_server.cpu_dev.queue) + len(selected_server.net_dev.queue)

    # Passa il tipo di task e i valori energetici
    selected_server.task_completed(
        task_id, task_type, arrival_time_system, arrival_time_task_queue,
        start_time, end_time, execution_time, service_time, time_in_queue,
        selected_server.name, num_hops, qlen,
         estimated_execution_time, transfer_time,
         TMAX_exceeded=False, exec_after_set=False,
        eps_cpu=eps_cpu, eps_net=eps_net
    )
Tmax_H = config["Tmax_H"]

def estimate_execution_time():
    # Valori presi dal file di configurazione (già in secondi)
    mean_seconds = config["CPU_timeout"]["mean"]
    min_seconds = config["CPU_timeout"]["min"]
    max_seconds = config["CPU_timeout"]["max"]

    estimated_time = experiments.truncated_exponential(mean=mean_seconds, lower=min_seconds, upper=max_seconds)
    #print(f"Tempo di esecuzione stimato: {estimated_time:.2f} secondi")
    return estimated_time


def SearchNode(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
                arrival_time_system,
                initial_server_counter, different_server_counter, other_server_counter,
               task_type):

    global hop
    estimated_execution_time = estimate_execution_time()
    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)
    bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
    bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps else 0.0
    data_bytes = (image_size + Volume_size) * (1024 ** 2)
    d_net_predicted = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')
    max_energy = config.get("initial_energy", 10000.0)

    server_metrics = []

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server is not None and latency_to_server is not None:
            transfer_time = ((image_size + Volume_size) / bandwidth_to_server) + latency_to_server
        else:
            transfer_time = 0.0

        # Calcola il punteggio di selezione in base al tipo di task
        selection_score = neighbor.get_selection_score(
            task_type,
            d_cpu=estimated_execution_time,
            d_net=d_net_predicted,
            energy_budget_max=max_energy
        )

        server_metrics.append({
            'server': neighbor,
            'selection_score': selection_score,  # Usa il nuovo punteggio di selezione
            'transfer_time': transfer_time,
            'orbitalSunset': neighbor.orbitalSunset,
        })

    # Filtra i server non validi
    server_metrics = [m for m in server_metrics
                      if m['orbitalSunset'] not in (None, 0)]

    if not server_metrics:
        print(f"[Task {task_id}] Nessun server valido trovato.")
        return

    # Ordina i server in base al nuovo punteggio di selezione, in ordine decrescente
    sorted_servers = sorted(server_metrics, key=lambda x: x['selection_score'], reverse=True)

    chosen = sorted_servers.pop(0)
    server = chosen['server']
    transfer_time = chosen['transfer_time']  # Ottieni il transfer_time dal dizionario

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
    task_data = {
        "task_id": task_id,
        "arrival_time": arrival_time_system,
        "type": task_type,
        "ram": required_ram,
        "disk": required_disk,
        "image_size": image_size,
        "exec_time": estimated_execution_time,
        "transfer_time": transfer_time,
        "num_hops": hop
    }
    globals.gbl_generated_tasks_data.append(task_data)
    # Chiamo TaskAssignment sul server scelto
    yield from TaskAssignment(env, server, task_id, required_ram, required_disk,image_size,
                               arrival_time_system, hop, transfer_time,
                              estimated_execution_time, task_type)

def task(env, task_id, server, initial_server_counter, different_server_counter, other_server_counter, task_data):
    global hop
    hop = 0
    Volume_size = 0.0
    arrival_time_system = env.now

    required_ram = task_data['required_ram']
    required_disk = task_data['required_disk']
    task_type = task_data['type']
    image_size = task_data['image_size']

    print(f"---> Task {task_id} (Type: {task_type}) arriva in {arrival_time_system:.2f}")

    yield from SearchNode(
        env,
        server,
        task_id,
        required_ram,
        required_disk,
        image_size,
        Volume_size,
        arrival_time_system,
        initial_server_counter,
        different_server_counter,
        other_server_counter,
        task_type
    )

def generate_tasks(env, initial_server_counter, different_server_counter, other_server_counter):
    global arrival_time

    print('Genero i task')

    task_id = 1
    max_energy = config.get("initial_energy", 10000.0)
    while True:
        # Read the distribution type from the configuration
        distribution_type = config["generate_tasks"]["distribution"]

        # Get the corresponding function based on the distribution type
        distribution_function = getattr(experiments, distribution_type)

        # Check if the function exists
        if distribution_function is not None and callable(distribution_function):
            arrival_time = distribution_function('Task')  # Inter arrival time, tempo tra l'arrivo di 2 task.
        else:
            raise ValueError("Unrecognized distribution type")

        yield env.timeout(arrival_time)

        # Stima dei parametri necessari per la selezione (richiama task per ottenere type e size)
        temp_task_data = task_type_and_size_generator()  # Nuova funzione da creare (vedi sotto)

        # Recupera i dati necessari per la selezione:
        task_type = temp_task_data['type']
        estimated_execution_time = estimate_execution_time()
        bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
        bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps else 0.0
        data_bytes = temp_task_data['image_size'] * (1024 ** 2)
        d_net_predicted = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')

        best_server = None
        best_score = float('-inf')  # Massimizzazione dello score

        for server in globals.global_access_point:
            # Calcola score passando le domande stimate (per tener conto anche di d_cpu/d_net)
            score = server.get_selection_score(
                task_type,
                d_cpu=estimated_execution_time,
                d_net=d_net_predicted,
                energy_budget_max=max_energy
            )
            if score > best_score:
                best_score = score
                best_server = server

        if best_server is None:
            print(f"[Task {task_id}] Nessun server scelto in base all'euristica.")
            task_id += 1
            continue

        temp_task_data['estimated_execution_time'] = estimated_execution_time
        # Il resto dei dati del task sono contenuti in task_type_and_size_generator
        env.process(task(env, task_id, best_server,
                         initial_server_counter, different_server_counter, other_server_counter,
                         temp_task_data))  # Passa i dati del task

        task_id += 1

def task_type_and_size_generator():
    """Genera i parametri del task senza avviarlo, utile per la pre-selezione."""

    required_ram = random.randint(config["required_ram"]["min"], config["required_ram"]["max"])
    required_disk = random.randint(config["required_disk"]["min"], config["required_disk"]["max"])

    beta_gen = config["beta"]["gen"]
    beta_CPUI = config["beta"]["CPUI"]
    beta_CPUI_DataI = config["beta"]["CPUI_DataI"]

    alphas = config.get("alpha", {"M", "H", "VH"})
    gammas = config.get("gamma", {"H", "VH"})

    # --- Selezione tipo di task ---
    r = random.random()
    if r < beta_gen:
        task_type = "Generic_Service"
        image_size = random.uniform(0.01, 0.088)  # 10KB–88KB

    elif r < beta_gen + beta_CPUI:
        task_type = "CPU_Intensive"
        image_size = random.uniform(0.01, 0.088)

    elif r < beta_gen + beta_CPUI + beta_CPUI_DataI:
        task_type = "CPU_and_Data_Intensive"
        r2 = random.random()
        if r2 < alphas["M"]:
            image_size = random.uniform(0.022, 2.2)  # 22KB–2.2MB
        elif r2 < alphas["M"] + alphas["H"]:
            image_size = random.uniform(2.2, 24.2)  # 2.2MB–24.2MB
        else:
            image_size = random.uniform(132.5, 500)  # 132.5MB–500MB
    else:
        task_type = "Batch"
        r3 = random.random()
        if r3 < gammas["H"]:
            image_size = random.uniform(2.2, 24.2)  # High
        else:
            image_size = random.uniform(132.5, 500)  # Very High

    return {
        'type': task_type,
        'image_size': image_size,
        'required_ram': required_ram,
        'required_disk': required_disk
    }