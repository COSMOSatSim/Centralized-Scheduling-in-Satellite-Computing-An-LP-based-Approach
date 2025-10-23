import globals
import json5
import experiments
from Task import Task

hop = 0  # Inizializza la variabile hop a zero

config = globals.config
resolution_config = globals.resolution_config


def network_metrics(config, image_size_MB, Volume_size_MB=0.0):
    """
    Calcola la larghezza di banda disponibile (in Bps) e la dimensione totale dei dati (in Byte).

    Args:
        config (dict): La configurazione globale.
        image_size_MB (float): Dimensione dell'immagine in MB.
        Volume_size_MB (float, optional): Dimensione aggiuntiva del volume in MB. Default a 0.0.

    Returns:
        tuple: (bw_Bps, data_bytes)
    """
    bw_MBps = config.get("available_bandwidth", {}).get("min", 0)
    # Converti la banda da MBps a Bps  (1 MB = 1024**2 byte)
    bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0

    # Calcola la dimensione totale dei dati in MB e poi in Byte
    total_data_MB = image_size_MB + Volume_size_MB
    data_bytes = total_data_MB * (1024 ** 2)

    return bw_Bps, data_bytes

def TaskAssignment(env, selected_server, task_id, image_size,
                   arrival_time_system, num_hops, transfer_time,
                   task_type, d_cpu, deadline):
    """
    Processo SimPy che assegna un task al server selezionato e simula:
      - attesa nella coda CPU (cpu_dev)
      - esecuzione CPU (yield timeout)
      - eventuale trasferimento su coda NET (net_dev)
      - downlink verso Ground Unit per alcuni task (delay_to_transfer)

    Parametri principali:
      - env: ambiente SimPy
      - selected_server: oggetto server che espone metodi e risorse (W_cpu, W_net, cpu_dev, net_dev, ecc.)
      - image_size: dimensione immagine in MB
      - transfer_time: tempo di trasferimento dal nodo sorgente a questo server (già calcolato)
    """

    # Leggi il flag di configurazione
    ENABLE_MONITORING = config.get("enable_queue_monitoring", False)

    task_OBS = Task(task_id, selected_server.name, 'OBS', env.now, task_type, image_size)
    bw_Bps, data_bytes = network_metrics(config, image_size)

    # Inizializza gli attributi solo se il monitoraggio è attivo
    if ENABLE_MONITORING:
        task_OBS.d_cpu = d_cpu
        task_OBS.d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
        task_OBS.deadline = arrival_time_system + deadline
        task_OBS.image_size_MB = image_size  # Salva la dimensione dell'immagine (in MB)

    # L'energia del trasferimento viene sottratta e verificata in SearchNode
    yield env.timeout(transfer_time)
    arrival_time_task_queue = env.now

    eps_cpu, eps_net, time_in_queue = 0.0, 0.0, 0.0 # energia stimata CPU / NET che useremo per riserve e sottrazioni
    start_time = env.now  # timestamp di inizio del processo
    #D_r = (1 + deadline) * d_cpu  # deadline massima  (1 + DeadLine )extimatedexecutiontime
    D_r = deadline # deadline massima  (1 + DeadLine )extimatedexecutiontime

    d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
    C_sen = config.get("C_sen", 1e9)  # parametro costante per il modello energetico CPU
    e_coeff = config.get("energy_coefficient", 5e-26)  # coefficiente energetico (esempio numerico)
    eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))
    net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
    # Wn e Wc sono latenze di attesa stimate nelle code (metodi del server)
    Wn = selected_server.W_net()
    Wc = selected_server.W_cpu()

    # Logica di routing basata sul tipo di task
    if task_type in ("Generic_Service", "CPU_Intensive"):
        # energia richiesta per eseguire il task sul server
        eps_cpu = selected_server.compute_execution_energy(d_cpu, C_sen, e=e_coeff)
        # controllo se il server ha energia disponibile (tenendo conto delle riserve)
        if selected_server.energy - selected_server.energy_reserved < eps_cpu:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for CPU")
            return
        # controllo se il server ha energia disponibile (tenendo conto delle riserve)
        R = Wc + d_cpu + d_net
        if R > D_r:
            # se la stima supera la deadline configurata, rifiuta il task
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return
        # riservo energia per evitare race condition con altri task
        selected_server.energy_reserved += eps_cpu
        # richiedo la risorsa CPU (SimPy Resource) - il server tiene una coda interna
        with selected_server.cpu_dev.request() as req_cpu:
            if ENABLE_MONITORING:
                    req_cpu.task_data = task_OBS
            yield req_cpu
            # quando ottengo la CPU, registro il tempo passato in coda
            time_in_queue = env.now - arrival_time_task_queue
            selected_server.cpu_busy_until = env.now + d_cpu

            yield env.timeout(d_cpu)
            selected_server.cpu_busy_until = env.now  # reset quando il task finisce
            # sottraggo l'energia CPU effettivamente consumata
            selected_server.energy -= eps_cpu

            # -------------------------
            # Downlink verso Ground User: si assume che l'output abbia dimensione = image_size
            # -------------------------
            BANDWIDTH_TO_GU_BPS = config.get("Bandwidth_to_GU_Bps", 100000)  # ATTENZIONE: unità devono essere B/s
            file_size_bytes = image_size * (1024 ** 2)  # conversione MB -> byte
            delay_to_transfer = file_size_bytes / BANDWIDTH_TO_GU_BPS  # tempo di trasmissione verso GU

        yield env.timeout(delay_to_transfer)
        selected_server.energy_reserved -= eps_cpu

    elif task_type in ("CPU_and_Data_Intensive"):

        eps_cpu = selected_server.compute_execution_energy(d_cpu, C_sen, e=e_coeff)
        if selected_server.energy - selected_server.energy_reserved < (eps_cpu + eps_net):
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system,
                                                 "Insufficient Energy for CPU+NET")
            return
        # Qui d_cpu e d_net sono i tempi di servizio per il task R
        R = Wc + d_cpu + Wn + d_net
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return
        selected_server.energy_reserved += (eps_cpu + eps_net)

        with selected_server.cpu_dev.request() as req_cpu:
            if ENABLE_MONITORING:
                    req_cpu.task_data = task_OBS
            yield req_cpu
            Wc = env.now - arrival_time_task_queue
            selected_server.cpu_busy_until = env.now + d_cpu
            yield env.timeout(d_cpu)
            selected_server.cpu_busy_until = env.now  # reset quando il task finisce
            selected_server.energy -= eps_cpu

            with selected_server.net_dev.request() as req_net:
                if ENABLE_MONITORING:
                        req_net.task_data = task_OBS
                yield req_net
                Wn = env.now - arrival_time_task_queue
                selected_server.net_busy_until = env.now + net_time
                yield env.timeout(net_time)
                selected_server.net_busy_until = env.now
                selected_server.energy -= eps_net
                time_in_queue = Wc + Wn
        selected_server.energy_reserved -= (eps_cpu + eps_net)

    elif task_type == "Batch":
        print('Arrivato task BATCH')
        # Solo coda Network
        if selected_server.energy - selected_server.energy_reserved < eps_net:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Insufficient Energy for NET")
            return
        R = Wn + d_net
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, "Deadline Exceeded")
            return
        selected_server.energy_reserved += eps_net
        with selected_server.net_dev.request() as req_net:
            if ENABLE_MONITORING:
                    req_net.task_data = task_OBS
            yield req_net
            time_in_queue = env.now - arrival_time_task_queue
            selected_server.net_busy_until = env.now + net_time
            yield env.timeout(net_time)
            selected_server.net_busy_until = env.now
            selected_server.energy -= eps_net
        selected_server.energy_reserved -= eps_net

    end_time = env.now
    execution_time = end_time - start_time
    service_time = execution_time + transfer_time

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
         d_cpu, transfer_time,
         DeadLine=False, exec_after_set=False,
        eps_cpu=eps_cpu, eps_net=eps_net
    )
    print(f"Task {task_id} Routing Start")

def cpu_demand(task_type):
    """
    Ritorna d_cpu (secondi) in base al tipo task:
      - Generic_Service: distribution 'gen' (mean ~ 0.01-0.1 s)
      - CPU_Intensive / CPU_and_Data_Intensive: distribution 'cpui' (mean ~ 0.1-1 s)
      - Batch: 0.0 (non usa la CPU)
    Usa experiments.truncated_exponential già presente nel progetto.
    """
    if task_type == "Generic_Service":
        params = config["CPU_timeout"].get("gen", config["CPU_timeout"]["default"])
    elif task_type in ("CPU_Intensive", "CPU_and_Data_Intensive"):
        params = config["CPU_timeout"].get("cpui", config["CPU_timeout"]["default"])
    else:
        return 0.0

    mean_seconds = params["mean"]
    return experiments.truncated_exponential_unbounded(mean_seconds)


def SearchNode(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
               arrival_time_system,
               initial_server_counter, different_server_counter, other_server_counter,
               task_type, max_energy, d_cpu, deadline):
    global hop

    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    # calcola bw e data_bytes per predire d_net
    bw_Bps, data_bytes = network_metrics(config, image_size)
    d_net_predicted = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')

    server_metrics = []

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        if bandwidth_to_server is not None and latency_to_server is not None:
            bandwidth_to_server_Bps = bandwidth_to_server * (1024 ** 2)
            transfer_time = ((image_size + Volume_size) * (1024 ** 2) / bandwidth_to_server_Bps) + latency_to_server
            # tempo di servizio rete stimato per il file su quel link (secondi)
            if bandwidth_to_server_Bps > 0:
                d_net_on_link = (image_size + Volume_size) * (1024 ** 2) / bandwidth_to_server_Bps
            else:
                d_net_on_link = float('inf')
        else:
            transfer_time = 0.0
            d_net_on_link = float('inf')

        # calcola lo score passando d_cpu, d_net_predicted, deadline relativo e dati utili
        selection_score = neighbor.get_selection_score(
            task_type,
            d_cpu=d_cpu,
            d_net=d_net_predicted,
            D_r=deadline,
            energy_budget_max=max_energy,
            file_size_bytes=data_bytes,
            bandwidth_Bps=bw_Bps
        )
        # stima tempo di attesa in coda sul neighbor:
        # prova a usare metodi esistenti (W_cpu, W_net) o fallback a attributi pubblici
        try:
            waiting_cpu = neighbor.W_cpu()
        except Exception:
            waiting_cpu = getattr(neighbor, "waiting_time", 0.0)

        try:
            waiting_net = neighbor.W_net()
        except Exception:
            waiting_net = 0.0

        # tempo totale stimato per completare il task su questo neighbor:
        # attesa in coda (cpu e net) + esecuzione CPU + trasmissione dati sul link + eventuale latenza trasferimento
        # d_cpu è l'esecuzione stimata (passata alla funzione)
        estimated_execution_time = d_cpu
        estimated_net_time = d_net_on_link  # tempo di trasmissione previsto sul link al neighbor
        waiting_time_adjusted = waiting_cpu + waiting_net

        expected_completion_time = waiting_time_adjusted + estimated_execution_time + estimated_net_time + transfer_time

        server_metrics.append({
            'server': neighbor,
            'selection_score': selection_score,
            'transfer_time': transfer_time,
            'orbitalSunset': neighbor.orbitalSunset,
            'Sunset': neighbor.elev_angle,
            'expected_completion_time': expected_completion_time
        })

    # Filtra i server non validi
    server_metrics = [m for m in server_metrics
                      if m['orbitalSunset'] not in (None, 0)]

    if not server_metrics:
        print(f"[Task {task_id}] Nessun server valido trovato.")
        return

    # Ordina i server in base al nuovo punteggio di selezione, in ordine decrescente
    sorted_servers = sorted(server_metrics, key=lambda x: x['selection_score'], reverse=True)

    distribution = config.get("request_distribution", {}).get("distribution", "")
    if distribution in ("DTS-base", "DTS-AP optimal"):
        print('Versione originale: DTS-TMAX')
        # filtriamo i dizionari che rispettano la deadline
        server_metrics_sorted = [m for m in sorted_servers if m['expected_completion_time'] < deadline]
    else:
        print('versione mod: OrbitAware')
        server_metrics_sorted = [
            m for m in sorted_servers
            if m['expected_completion_time'] < deadline
               and m['expected_completion_time'] < m['orbitalSunset']
               and m['orbitalSunset'] not in (0, None)
        ]

    if not server_metrics_sorted:
        print(f"[Task {task_id}] Nessun server rimasto dopo i filtri (deadline/sunset).")
        return

    # scegli il primo dizionario (metriche) e ricava server/transfer_time da lì
    chosen_metric = server_metrics_sorted.pop(0)
    server = chosen_metric['server']
    transfer_time = chosen_metric.get('transfer_time', 0.0)  # tempo di trasmissione stimato per andare al server scelto

    # Aggiorna contatori
    initial_server_counter[server_selected.name] += 1
    if server != server_selected:
        different_server_counter[server_selected.name] += 1
        other_server_counter[server.name] += 1
        hop += 1

        # se ho inoltrato ad un altro server, calcolo l'energia di routing e la sottraggo al nodo mittente
        bw_MBps = server_selected.get_bandwidth(server)
        if bw_MBps is None:
            bw_Bps, data_bytes = network_metrics(config, image_size)
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
        "exec_time": d_cpu,
        "transfer_time": transfer_time,
        "num_hops": hop,
        "execution_server": server.name
    }
    globals.gbl_generated_tasks_data.append(task_data)
    # Chiamo TaskAssignment sul server scelto
    yield from TaskAssignment(env, server, task_id, image_size,
                               arrival_time_system, hop, transfer_time,
                               task_type, d_cpu, deadline)

def task(env, task_id, server, initial_server_counter, different_server_counter, other_server_counter, task_data, max_energy):
    global hop
    hop = 0
    Volume_size = 0.0
    arrival_time_system = env.now

    # estrai d_cpu e deadline già calcolati in generate_tasks
    d_cpu = task_data.get('d_cpu')  # fallback
    deadline = task_data.get('deadline', config.get("DeadLine", 400))  # relative deadline in seconds

    required_ram = task_data['required_ram']
    required_disk = task_data['required_disk']
    task_type = task_data['type']
    image_size = task_data['image_size']

    print(f"---> Task {task_id} (Type: {task_type}) arriva in {arrival_time_system:.2f}")

    yield from SearchNode(
        env, server,
        task_id,
        required_ram,
        required_disk,
        image_size,
        Volume_size,
        arrival_time_system, initial_server_counter, different_server_counter, other_server_counter,
        task_type, max_energy, d_cpu, deadline
    )

def generate_tasks(env, initial_server_counter, different_server_counter, other_server_counter):
    global arrival_time
    print('Genero i task')

    task_id = 1
    while True:
        # prendo energia massima disponibile tra i nodi (servirà nella selezione)
        max_energy = max(server.energy for server in globals.global_access_point)
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
        temp_task_data = task_type_and_size_generator()

        d_cpu = temp_task_data['d_cpu']
        # stima per la preselezione: calcola d_net_predicted in secondi
        bw_Bps, data_bytes = network_metrics(config, temp_task_data['image_size'])
        d_net_predicted = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')

        # imposta deadline: D_r = (1 + delta_D) * (d_cpu + d_net)
        ##delta_D = config.get("delta_D", 0.2)  # default 20% slack
        deadline = config.get("DeadLine")
        D_r = (1.0 + deadline) * (d_cpu + d_net_predicted)
        temp_task_data['deadline'] = D_r

        # stima d_cpu già in temp_task_data;
        # Ora pre-seleziona server usando i parametri d_cpu e d_net_predicted
        best_server = None
        best_score = float('-inf')
        for server in globals.global_access_point:
            score = server.get_selection_score(
                temp_task_data['type'],
                d_cpu=d_cpu,
                d_net=d_net_predicted,
                D_r=D_r,
                energy_budget_max=max_energy,
                file_size_bytes=data_bytes,
                bandwidth_Bps=bw_Bps
            )
            if score > best_score:
                best_score = score
                best_server = server

        if best_server is None:
            print(f"[Task {task_id}] Nessun server scelto in base all'euristica.")
            task_id += 1
            continue

        # Il resto dei dati del task sono contenuti in task_type_and_size_generator
        env.process(task(env, task_id, best_server,
                         initial_server_counter, different_server_counter, other_server_counter,
                         temp_task_data, max_energy))  # Passa i dati del task

        task_id += 1


def task_type_and_size_generator():
    """Genera i parametri del task senza avviarlo, utile per la pre-selezione."""

    # Assicurati che la configurazione sia stata caricata
    if not resolution_config:
        raise RuntimeError("Configurazione risoluzione task non caricata correttamente.")

    # Ram e Disk (questi restano nel config principale)
    required_ram = globals.rnd.randint(config["required_ram"]["min"], config["required_ram"]["max"])
    required_disk = globals.rnd.randint(config["required_disk"]["min"], config["required_disk"]["max"])

    # Carica i parametri dal file di risoluzione
    betas = resolution_config["beta_probabilities"]
    ranges = resolution_config["size_ranges_MB"]
    cpu_data_params = ranges["CPU_DATA_INTENSIVE"]
    batch_params = ranges["BATCH_TASK"]

    # --- Selezione tipo di task ---
    r = globals.rnd.random()

    if r < betas["Generic_Service"]:
        task_type = "Generic_Service"
        image_size = globals.rnd.uniform(*ranges["GENERIC_CPU_RANGE"])

    elif r < betas["Generic_Service"] + betas["CPU_Intensive"]:
        task_type = "CPU_Intensive"
        image_size = globals.rnd.uniform(*ranges["GENERIC_CPU_RANGE"])

    elif r < betas["Generic_Service"] + betas["CPU_Intensive"] + betas["CPU_and_Data_Intensive"]:
        task_type = "CPU_and_Data_Intensive"
        r2 = globals.rnd.random()

        # Uso dei pesi di alpha per le risoluzioni (M, H, VH)
        if r2 < cpu_data_params["alpha_M_weight"]:
            image_size = globals.rnd.uniform(*cpu_data_params["M_range"])
        elif r2 < cpu_data_params["alpha_M_weight"] + cpu_data_params["alpha_H_weight"]:
            image_size = globals.rnd.uniform(*cpu_data_params["H_range"])
        else:
            image_size = globals.rnd.uniform(*cpu_data_params["VH_range"])

    else:
        task_type = "Batch"
        r3 = globals.rnd.random()
        # Uso dei pesi di gamma per le risoluzioni (H, VH)
        if r3 < batch_params["gamma_H_weight"]:
            image_size = globals.rnd.uniform(*batch_params["H_range"])
        else:
            image_size = globals.rnd.uniform(*batch_params["VH_range"])

    d_cpu = cpu_demand(task_type)

    return {
        'type': task_type,
        'image_size': image_size,
        'required_ram': required_ram,
        'required_disk': required_disk,
        'd_cpu': d_cpu
    }

def enqueue_batch_in_net(env, server_obj, task_id, image_size_MB, arrival_time_system, deadline_relative):
    """
    Metti un task BATCH direttamente nella coda NET del server
    (batch già nella network-queue quando il SEN entra nella dome).
    Questo processo effettua: net_dev.request() -> rimane in coda -> quando servito esegue la trasmissione.
    """
    # Crea oggetto Task per monitoring / export_state
    task_OBS = Task(task_id, server_obj.name, 'OBS', arrival_time_system, "Batch", image_size_MB)

    # metriche di rete (predizione d_net in secondi)
    bw_Bps, data_bytes = network_metrics(config, image_size_MB)
    task_OBS.d_net = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')
    task_OBS.deadline = arrival_time_system + deadline_relative
    task_OBS.image_size_MB = image_size_MB

    # crea la richiesta: questo inserisce l'elemento in server_obj.net_dev.queue
    req = server_obj.net_dev.request()
    req.task_data = task_OBS  # utile per export_state / monitoring

    # debug/log
    print(f"[{env.now:.3f}] ENQUEUE BATCH id={task_id} on {server_obj.name} "
          f"image_MB={image_size_MB:.2f} queue_len={len(server_obj.net_dev.queue)+1}")

    # il processo rimane bloccato finché la risorsa NET non lo serve
    yield req

    # quando viene servito, simuliamo la trasmissione sulla risorsa NET
    if bw_Bps > 0:
        net_time = data_bytes / bw_Bps
    else:
        net_time = float('inf')

    server_obj.net_busy_until = env.now + net_time
    yield env.timeout(net_time)

    # Calcola il tempo di coda
    start_service_time = env.now - net_time
    time_in_queue_batch = start_service_time - arrival_time_system  # Tempo di attesa nella net queue

    server_obj.net_busy_until = env.now

    # sottrai energia di trasmissione
    eps_net = server_obj.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

    # registra il completamento (usa task_completed come negli altri rami)
    server_obj.task_completed(
        task_id, "Batch", arrival_time_system, arrival_time_system,
        start_service_time, env.now, net_time, net_time, time_in_queue_batch,  # <-- USA time_in_queue_batch
        server_obj.name, 0, len(server_obj.net_dev.queue),
        estimated_execution_time=0.0, transfer_time=0.0,
        DeadLine=False, exec_after_set=False,
        eps_cpu=0.0, eps_net=eps_net
    )
    server_obj.energy -= eps_net

    try:
        completed_tuple = (
            task_id,  # tid
            "Batch",  # task_type
            arrival_time_system,  # arr_sys
            arrival_time_system,  # arr_q (qui uguale)
            env.now - net_time,  # start_time
            env.now,  # end_time
            net_time,  # execution_time (NET)
            net_time,  # service_time
            0.0,  # time in queue (usiamo 0 visto che era subito nella net queue)
            server_obj.name,  # sel_srv (o chi ha eseguito)
            0,  # hops
            len(server_obj.net_dev.queue),  # qlen
            0.0,  # est_e
            0.0,  # trf
            False,  # DeadLine
            False,  # exec_set
            0.0,  # eps_cpu
            eps_net,  # eps_net
            eps_net,  # eps_tot (cpu+net)
            server_obj.energy  # remaining_energy
        )
        globals.gbl_batch_completed.append(completed_tuple)
    except Exception as e:
        print(f"ERROR saving batch completion to global list: {e}")

    print(f"[{env.now:.3f}] BATCH id={task_id} served on {server_obj.name} net_time={net_time:.3f} eps_net={eps_net:.6f}")
