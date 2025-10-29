import globals
import experiments
from Task import Task
from sec_ilp_snapshot_v3 import solve_on_Ek, Snapshot, SENState, QueueTask, alpha_from_physics, solve_on_Ek_hierarchical

hop = 0  # Inizializza la variabile hop a zero

config = globals.config
resolution_config = globals.resolution_config

C_sen = config.get("C_sen", 1e9)  # parametro costante per il modello energetico CPU
bw_MBps = float(config.get("available_bandwidth", {}).get("min", 2150.0))
bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
e_coeff = config.get("energy_coefficient", 5e-26)  # coefficiente energetico (esempio numerico)

def network_metrics(image_size_MB, Volume_size_MB=0.0):
    """
    Calcola la larghezza di banda disponibile (in Bps) e la dimensione totale dei dati (in Byte).

    Args:
        image_size_MB (float): Dimensione dell'immagine in MB.
        Volume_size_MB (float, optional): Dimensione aggiuntiva del volume in MB. Default a 0.0.

    Returns:
        tuple: (bw_Bps, data_bytes)
    """

    # Calcola la dimensione totale dei dati in MB e poi in Byte
    total_data_MB = image_size_MB + Volume_size_MB
    data_bytes = total_data_MB * (1024 ** 2)

    return bw_Bps, data_bytes


def TaskAssignment(env, selected_server, task_id, image_size,
                   arrival_time_system, num_hops, transfer_time,
                   task_type, d_cpu, D_r):
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
    ENABLE_MONITORING = config.get("enable_queue_monitoring", False)

    task_OBS = Task(task_id, selected_server.name, 'OBS', env.now, task_type, image_size)
    bw_Bps, data_bytes = network_metrics(image_size)

    # Inizializza gli attributi solo se il monitoraggio è attivo
    if ENABLE_MONITORING:
        task_OBS.d_cpu = d_cpu
        task_OBS.d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0
        task_OBS.deadline = arrival_time_system + D_r
        task_OBS.image_size_MB = image_size

    # aspetta il trasferimento iniziale verso il selected_server
    yield env.timeout(transfer_time)
    arrival_time_task_queue = env.now

    # helper per contare utenti + queue. calcola il numero totale di task associati a una risorsa in un preciso istante, sommando sia i task in servizio sia quelli in coda
    def _res_len_with_users(res):
        # numero di task che stanno attualmente utilizzando la risorsa (res.users)
        users_len = len(getattr(res, "users", []))
        # numero di task che sono attualmente in attesa nella coda (res.queue)
        queue_len = len(getattr(res, "queue", []))
        return users_len + queue_len

    # inizializza variabili di coda per reporting
    qlen_on_enqueue_cpu = None
    qlen_on_enqueue_net = None

    eps_cpu, eps_net, time_in_queue = 0.0, 0.0, 0.0  # energia stimata CPU / NET che useremo per riserve e sottrazioni
    start_time = env.now

    d_net = data_bytes / bw_Bps if bw_Bps > 0 else 0.0

    eps_net = selected_server.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))
    net_time = data_bytes / bw_Bps if bw_Bps > 0 else 0.0

    # stime di attesa (metodi del server; se non esistono, fallback a 0). Wn e Wc sono latenze di attesa stimate nelle code (metodi del server)
    try:
        Wn = selected_server.W_net()
    except Exception:
        Wn = getattr(selected_server, "W_net", lambda: 0.0)()

    try:
        Wc = selected_server.W_cpu()
    except Exception:
        Wc = getattr(selected_server, "W_cpu", lambda: 0.0)()

    # ---------------------------
    # Branch: Generic / CPU_Intensive (solo CPU)
    # ---------------------------
    if task_type in ("Generic_Service", "CPU_Intensive"):
        # energia richiesta per eseguire il task sul server
        eps_cpu = selected_server.compute_execution_energy(d_cpu, C_sen, e=e_coeff)
        # controllo se il server ha energia disponibile (tenendo conto delle riserve)
        if selected_server.energy - selected_server.energy_reserved < eps_cpu:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size, "Insufficient Energy for CPU")
            return
        # controllo se il server ha energia disponibile (tenendo conto delle riserve)
        R = Wc + d_cpu + d_net
        print('valore di R confreontato con deadline', R, 'deadline', D_r)
        if R > D_r:
            # se la stima supera la deadline configurata, rifiuta il task
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size, "Deadline Exceeded")
            return
            # riservo energia per evitare race condition con altri task
        selected_server.energy_reserved += eps_cpu

        # richiedo la risorsa CPU (SimPy Resource) - il server tiene una coda interna
        req_cpu = selected_server.cpu_dev.request()
        qlen_on_enqueue_cpu = _res_len_with_users(selected_server.cpu_dev)
        if ENABLE_MONITORING:
            req_cpu.task_data = task_OBS
            print(
                f"[{env.now:.3f}] Task {task_id} enqueued on CPU {selected_server.name} qlen_enqueue={qlen_on_enqueue_cpu}")

        # attendi servizio CPU
        yield req_cpu
        # quando ottengo la CPU, registro il tempo passato in coda
        time_in_queue = env.now - arrival_time_task_queue
        selected_server.cpu_busy_until = env.now + d_cpu

        # esecuzione CPU
        yield env.timeout(d_cpu)
        selected_server.cpu_busy_until = env.now  # reset quando il task finisce
        # sottraggo l'energia CPU effettivamente consumata
        selected_server.energy -= eps_cpu
        selected_server.cpu_dev.release(req_cpu)

        # -------------------------
        # Downlink verso Ground User: si assume che l'output abbia dimensione = image_size
        # -------------------------
        BANDWIDTH_TO_GU_BPS = config.get("Bandwidth_to_GU_Bps", 100000)  # ATTENZIONE: unità devono essere B/s
        file_size_bytes = image_size * (1024 ** 2)  # conversione MB -> byte
        delay_to_transfer = file_size_bytes / BANDWIDTH_TO_GU_BPS  # tempo di trasmissione verso GU

        # rilascio riserva dopo tutte le operazioni che dipendono dalla CPU
        yield env.timeout(delay_to_transfer)
        selected_server.energy_reserved -= eps_cpu

    # ---------------------------
    # Branch: CPU_and_Data_Intensive (CPU + NET)
    # ---------------------------
    elif task_type in ("CPU_and_Data_Intensive"):
        eps_cpu = selected_server.compute_execution_energy(d_cpu, C_sen, e=e_coeff)

        if selected_server.energy - selected_server.energy_reserved < (eps_cpu + eps_net):
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size,
                                                 "Insufficient Energy for CPU+NET")
            return
        # Qui d_cpu e d_net sono i tempi di servizio per il task R
        R = Wc + d_cpu + Wn + d_net
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size, "Deadline Exceeded")
            return

        # riservo energia totale (CPU + NET)
        selected_server.energy_reserved += (eps_cpu + eps_net)

        # enqueue sulla CPU
        req_cpu = selected_server.cpu_dev.request()
        qlen_on_enqueue_cpu = _res_len_with_users(selected_server.cpu_dev)
        if ENABLE_MONITORING:
            req_cpu.task_data = task_OBS
        print(
            f"[{env.now:.3f}] Task {task_id} enqueued on CPU {selected_server.name} qlen_enqueue={qlen_on_enqueue_cpu}")

        # attendi la CPU
        yield req_cpu

        Wc = env.now - arrival_time_task_queue
        selected_server.cpu_busy_until = env.now + d_cpu

        # esecuzione CPU
        yield env.timeout(d_cpu)
        selected_server.cpu_busy_until = env.now
        selected_server.energy -= eps_cpu
        selected_server.cpu_dev.release(req_cpu)

        cpu_service_end = env.now

        # ora enqueue sulla NET (se richiesto)
        req_net = selected_server.net_dev.request()
        qlen_on_enqueue_net = _res_len_with_users(selected_server.net_dev)
        if ENABLE_MONITORING:
            req_net.task_data = task_OBS
        print(
            f"[{env.now:.3f}] Task {task_id} enqueued on NET {selected_server.name} qlen_enqueue_net={qlen_on_enqueue_net}")

        yield req_net

        Wn = env.now - cpu_service_end
        if Wn < 0:
            Wn = 0.0

        selected_server.net_busy_until = env.now + net_time

        yield env.timeout(net_time)
        selected_server.net_busy_until = env.now
        selected_server.energy -= eps_net
        selected_server.net_dev.release(req_net)

        time_in_queue = Wc + Wn
        selected_server.energy_reserved -= (eps_cpu + eps_net)

    # ---------------------------
    # Branch: Batch (solo NET)
    # ---------------------------
    elif task_type == "Batch":
        # Solo coda Network
        if selected_server.energy - selected_server.energy_reserved < eps_net:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size, "Insufficient Energy for NET")
            return

        R = Wn + d_net
        if R > D_r:
            selected_server.record_rejected_task(task_id, task_type, arrival_time_system, image_size, "Deadline Exceeded")
            return

        selected_server.energy_reserved += eps_net

        req_net = selected_server.net_dev.request()
        qlen_on_enqueue_net = _res_len_with_users(selected_server.net_dev)
        if ENABLE_MONITORING:
            req_net.task_data = task_OBS
        print(
            f"[{env.now:.3f}] Batch {task_id} enqueued on NET {selected_server.name} qlen_enqueue_net={qlen_on_enqueue_net}")

        yield req_net
        time_in_queue = env.now - arrival_time_task_queue
        selected_server.net_busy_until = env.now + net_time

        yield env.timeout(net_time)
        selected_server.net_busy_until = env.now
        selected_server.energy -= eps_net
        selected_server.energy_reserved -= eps_net
        selected_server.net_dev.release(req_net)

    # Fine dei branch: calcola metriche finali e registra il completamento
    end_time = env.now
    execution_time = end_time - start_time
    service_time = execution_time + transfer_time + time_in_queue

    selected_server.tasks.append(task_OBS)
    globals.gbl_tasks.append(task_OBS)

    if selected_server.elev_angle < config["Phi_max"] - config["Phi_buffer"]:
        task_OBS.label = 'SEN_OUT_OF_BUFF'
        if ENABLE_MONITORING:
            print(f"{selected_server} {selected_server.elev_angle}° {task_OBS.id} set as {task_OBS.label}")

    # fallback per qlen: usa i valori di enqueue catturati, altrimenti misura lo stato attuale
    cpu_q = qlen_on_enqueue_cpu if qlen_on_enqueue_cpu is not None else _res_len_with_users(selected_server.cpu_dev)
    net_q = qlen_on_enqueue_net if qlen_on_enqueue_net is not None else _res_len_with_users(selected_server.net_dev)
    qlen = cpu_q + net_q

    # Passa il tipo di task e i valori energetici
    selected_server.task_completed(
        task_id, task_type, arrival_time_system, arrival_time_task_queue,
        start_time, end_time, execution_time, service_time, time_in_queue,
        selected_server.name, num_hops, qlen, transfer_time,
        image_size, DeadLine=False, exec_after_set=False,
        eps_cpu=eps_cpu, eps_net=eps_net
    )

    if ENABLE_MONITORING:
        print(
            f"[{env.now:.3f}] Task {task_id} served on {selected_server.name} qlen_enqueue_cpu={qlen_on_enqueue_cpu} qlen_enqueue_net={qlen_on_enqueue_net} time_in_queue={time_in_queue:.3f}")


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


# ---------------------------------------------------------------------------
# FUNZIONI HELPER PER ILP
# ---------------------------------------------------------------------------

def _merge_queues_for_ilp(sat_state: dict):
    """
    Unisce waiting+service per CPU/NET e mappa i task nel formato atteso dall'ILP.
    - CPU: usa 'demand' -> d_cpu (s)
    - NET: usa image_size_MB come d_net (MB) quando disponibile; come fallback usa 'demand' (MB)
    Ritorna: (cpu_queue, net_queue)
    """
    cpu_q = []
    net_q = []

    # CPU
    for key in ("queue_cpu_waiting", "queue_cpu_service"):
        for t in sat_state.get(key, []):
            cpu_q.append(QueueTask(
                task_id=str(t.get("task_id")),
                d_cpu=float(t.get("demand", 0.0) or 0.0),
                d_net=0.0,  # non usato per la coda CPU
                D=float(t.get("deadline", 300.0) or 300.0)
            ))

    # NET
    for key in ("queue_net_waiting", "queue_net_service"):
        for t in sat_state.get(key, []):
            d_net_MB = t.get("image_size_MB", None)
            if d_net_MB is None or d_net_MB == 'N/A':
                # fallback: prendi 'demand' come MB
                d_net_MB = float(t.get("demand", 0.0) or 0.0)
            net_q.append(QueueTask(
                task_id=str(t.get("task_id")),
                d_cpu=0.0,
                d_net=float(d_net_MB),
                D=float(t.get("deadline", 300.0) or 300.0)
            ))

    return cpu_q, net_q


def _build_snapshot_Ek(env, center_server, candidate_servers, current_task_id, d_cpu_req, d_net_MB_req, deadline_req,
                       config):
    """
    Costruisce un oggetto Snapshot minimale per solve_on_Ek su Ek={k}+neighbors[k].
    - d_net del *task corrente* è espresso in MB (l'ILP lo converte in secondi con la banda).
    - B = energia corrente; B_max = initial_energy (fallback dal config).
    """
    sen_map = {}
    neighbors_map = {}
    listening = []

    # costruisci mappe SEN e vicinato
    for srv in candidate_servers:
        st = srv.export_state(env)  # richiede enable_queue_monitoring=true
        B = float(st.get("energy_budget_J", getattr(srv, "energy", 0.0)))
        B_max = float(config.get("initial_energy", B if B > 0 else 1.0))

        cpu_q, net_q = _merge_queues_for_ilp(st)

        # NOTA: l'ILP usa default_net_bw_MBps, quindi non è obbligatorio impostare s.net_bw_MBps
        # ma se vuoi puoi passare un valore medio per nodo come attributo add-on:
        s_state = SENState(
            B=B,
            B_max=B_max,
            Rmax_norm=1.0,
            cpu_queue=cpu_q,
            net_queue=net_q,
            in_service_cpu=None,
            in_service_net=None,
            net_bw_bps=None  # lasciamo None -> userà default_net_bw_MBps
        )
        sen_map[srv.name] = s_state

        # vicini: basta la lista dei nomi
        neigh_names = []
        for n in srv.get_neighbors():
            neigh_names.append(n.name)
        neighbors_map[srv.name] = neigh_names

        # listening dome (se serve per policy): lo prendiamo dallo state
        if st.get("in_listening_dome", False):
            listening.append(srv.name)

    # richieste: SOLO il task corrente
    req = QueueTask(
        task_id=str(current_task_id),
        d_cpu=float(d_cpu_req),
        d_net=float(d_net_MB_req),  # MB!
        D=float(deadline_req)
    )

    snap = Snapshot(
        time=float(env.now),
        listening_dome=listening,
        neighbors=neighbors_map,
        sen=sen_map,
        requests=[req],
        pre_R={},  # niente precomputation
        pre_E={}
    )
    return snap


def _calculate_heuristic_metrics(neighbors_at_distance_one, server_selected,
                                 image_size, Volume_size, task_type, d_cpu, deadline, max_energy,
                                 d_net_predicted, data_bytes_global, bw_Bps_global):
    """
    Calcola le metriche euristiche per tutti i server candidati.
    Questo è il ciclo 'for neighbor...' estratto.
    """
    server_metrics = []

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        total_data_MB = image_size + Volume_size
        total_data_bytes = total_data_MB * (1024 ** 2)

        if bandwidth_to_server is not None and latency_to_server is not None and bandwidth_to_server > 0:
            bandwidth_to_server_Bps = bandwidth_to_server * (1024 ** 2)
            transfer_time = (total_data_bytes / bandwidth_to_server_Bps) + latency_to_server
            d_net_on_link = total_data_bytes / bandwidth_to_server_Bps
        else:
            transfer_time = 0.0
            d_net_on_link = float('inf')

        # calcola lo score
        selection_score = neighbor.get_selection_score(
            task_type,
            d_cpu=d_cpu,
            d_net=d_net_predicted,
            D_r=deadline,
            energy_budget_max=max_energy,
            file_size_bytes=data_bytes_global,
            bandwidth_Bps=bw_Bps_global
        )

        # stima tempo di attesa in coda sul neighbor
        try:
            waiting_cpu = neighbor.W_cpu()
        except Exception:
            waiting_cpu = getattr(neighbor, "waiting_time", 0.0)
        try:
            waiting_net = neighbor.W_net()
        except Exception:
            waiting_net = 0.0

        waiting_time_adjusted = waiting_cpu + waiting_net
        estimated_execution_time = d_cpu
        estimated_net_time = d_net_on_link

        expected_completion_time = waiting_time_adjusted + estimated_execution_time + estimated_net_time + transfer_time

        server_metrics.append({
            'server': neighbor,
            'selection_score': selection_score,
            'transfer_time': transfer_time,
            'orbitalSunset': neighbor.orbitalSunset,
            'Sunset': neighbor.elev_angle,  # Mantenuto da v1
            'expected_completion_time': expected_completion_time
        })

    return server_metrics


def _filter_and_select_best_server(server_metrics, deadline, task_id, task_type,
                                   arrival_time_system, image_size, server_selected, config):
    """
    Filtra la lista di metriche (sunset, deadline) e seleziona il server migliore.
    """

    # 1. Filtra i server non validi (orbitalSunset)
    server_metrics_filtered = [m for m in server_metrics
                               if m['orbitalSunset'] not in (None, 0)]

    reason = "No suitable server found after deadline/sunset filters"
    if not server_metrics_filtered:
        print(f"[Task {task_id}] Nessun server valido trovato (filtro orbitalSunset).")
        server_selected.record_rejected_task(
            task_id, task_type, arrival_time_system, image_size, 'Invalid orbitalSunset'
        )
        return None, reason  # Ritorna None se fallisce

    # 2. Ordina i server in base allo score
    sorted_servers = sorted(server_metrics_filtered, key=lambda x: x['selection_score'], reverse=True)

    # 3. Applica il blocco di filtro (DTS-base vs OrbitAware)
    distribution = config.get("request_distribution", {}).get("distribution", "")
    if distribution in ("DTS-base", "DTS-AP optimal"):
        print(f'[{task_id}] Filtro euristico: DTS-TMAX')
        # filtriamo i dizionari che rispettano la deadline
        server_metrics_sorted = [m for m in sorted_servers if m['expected_completion_time'] < deadline]
    else:
        print(f'[{task_id}] Filtro euristico: OrbitAware')
        server_metrics_sorted = [
            m for m in sorted_servers
            if m['expected_completion_time'] < deadline
               and m['expected_completion_time'] < m['orbitalSunset']
        ]

    # 4. Controlla se sono rimasti server
    if not server_metrics_sorted:
        print(f"[Task {task_id}] Nessun server rimasto dopo i filtri (deadline/sunset).")
        server_selected.record_rejected_task(
            task_id, task_type, arrival_time_system, image_size, reason
        )
        return None, reason  # Ritorna None se fallisce

    # 5. Scegli il migliore
    chosen_metric = server_metrics_sorted.pop(0)
    return chosen_metric, None  # Ritorna la metrica scelta


def _finalize_and_assign_task(env, server_selected, server, task_id,
                              image_size, Volume_size, arrival_time_system,
                              transfer_time, task_type, d_cpu, deadline,
                              required_ram, required_disk,
                              initial_server_counter, different_server_counter, other_server_counter):
    """
    Blocco finale: aggiorna contatori, calcola energia di routing,
    registra i dati globali e chiama TaskAssignment.
    """
    global hop

    # Aggiorna contatori
    initial_server_counter[server_selected.name] += 1

    data_bytes_global = (image_size + Volume_size) * (1024 ** 2)
    bw_Bps_global = bw_Bps

    if server != server_selected:
        different_server_counter[server_selected.name] += 1
        other_server_counter[server.name] += 1
        hop += 1

        # Calcola l'energia di routing e la sottrae al nodo mittente
        # Usa il link specifico se disponibile, altrimenti il globale
        bw_MBps_link = server_selected.get_bandwidth(server)

        if bw_MBps_link is not None and bw_MBps_link > 0:
            bw_Bps_for_energy = bw_MBps_link * (1024 ** 2)
            data_bytes_for_energy = data_bytes_global
        else:
            bw_Bps_for_energy = bw_Bps_global if bw_Bps_global > 0 else 0
            data_bytes_for_energy = data_bytes_global

        if bw_Bps_for_energy > 0:
            Ptrasm = config.get("Ptrasm", 1.0)
            eps_net = server_selected.compute_routing_energy(data_bytes_for_energy, bw_Bps_for_energy, Ptrasm)
        else:
            eps_net = 0.0

        server_selected.energy -= eps_net
        print(f"[{env.now:.2f}] [Task {task_id}] Routed {server_selected.name} -> {server.name} | "
              f"E_NET={eps_net:.6f} J | Remaining={server_selected.energy:.2f} J")

    # Log per runner/grafici
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


# ---------------------------------------------------------------------------
# VERSIONE 1: SearchNode
# ---------------------------------------------------------------------------

def SearchNode_Heuristic_v1(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
                            arrival_time_system,
                            initial_server_counter, different_server_counter, other_server_counter,
                            task_type, max_energy, d_cpu, deadline):
    # 1. Ottieni i vicini
    neighbors_at_distance_one = server_selected.get_neighbors()
    neighbors_at_distance_one.append(server_selected)

    # 2. Calcola metriche globali per l'euristica
    bw_Bps_global, data_bytes_global = network_metrics( image_size, Volume_size_MB=Volume_size)
    d_net_predicted = data_bytes_global / bw_Bps_global if bw_Bps_global > 0 else float('inf')

    # 3. Calcola metriche per ogni server
    server_metrics = _calculate_heuristic_metrics(
        neighbors_at_distance_one, server_selected,
        image_size, Volume_size, task_type, d_cpu, deadline, max_energy,
        d_net_predicted, data_bytes_global, bw_Bps_global
    )

    # 4. Filtra e seleziona il server migliore
    chosen_metric, reason = _filter_and_select_best_server(
        server_metrics, deadline, task_id, task_type,
        arrival_time_system, image_size, server_selected, config
    )

    if chosen_metric is None:
        return  # Task già rifiutato dentro la funzione helper

    # 5. Estrai i dati e finalizza
    server = chosen_metric['server']
    transfer_time = chosen_metric.get('transfer_time', 0.0)

    yield from _finalize_and_assign_task(
        env, server_selected, server, task_id,
        image_size, Volume_size, arrival_time_system,
        transfer_time, task_type, d_cpu, deadline,
        required_ram, required_disk,
        initial_server_counter, different_server_counter, other_server_counter
    )


# ---------------------------------------------------------------------------
# VERSIONE 2: SearchNode IPL
# ---------------------------------------------------------------------------

def SearchNode_ILP_Hybrid_v2(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
                             arrival_time_system,
                             initial_server_counter, different_server_counter, other_server_counter,
                             task_type, max_energy, d_cpu, deadline):
    """
    Wrapper: Prova ILP se configurato in config["SearchNode"].
    Altrimenti, o in caso di fallimento, esegue SearchNode_Heuristic_v1.
    """

    if str(config.get("SearchNode", "")).upper() == "ILP":

        # --- Inizio blocco ILP  ---
        print(f"[{env.now:.2f}] [Task {task_id}] Entering ILP branch (v2)")

        # 1. Ottieni i vicini (necessario per ILP)
        neighbors_at_distance_one = list(server_selected.get_neighbors())
        if server_selected not in neighbors_at_distance_one:
            neighbors_at_distance_one.append(server_selected)

        d_net_MB_req = float(image_size + (Volume_size or 0.0))

        # Snapshot locale e risoluzione
        snap = _build_snapshot_Ek(
            env=env,
            center_server=server_selected,
            candidate_servers=neighbors_at_distance_one,
            current_task_id=task_id,
            d_cpu_req=float(d_cpu),
            d_net_MB_req=float(d_net_MB_req),
            deadline_req=float(deadline),
            config=config
        )

        # --- Coefficienti fisici ---
        P_net = float(config.get("Ptrasm", 1.0))
        alpha_cpu, alpha_net_J_per_byte = alpha_from_physics(C_sen, e_coeff, P_net, bw_Bps)
        alpha_net = alpha_net_J_per_byte * (1024 ** 2)  # J/MB
        w_e = float(config.get("ilp_weights", {}).get("w_e", 0.5))
        w_R = float(config.get("ilp_weights", {}).get("w_R", 0.5))

        # --- Funzione interna per estrarre risultati ---
        def _extract_chosen_server(ilp_res, task_id):
            # ... (la tua logica di estrazione è corretta) ...
            tid = str(task_id)
            if isinstance(ilp_res, dict):
                a = ilp_res.get("assignments")
                if isinstance(a, list):
                    for item in a:
                        if str(item.get("task") or item.get("task_id") or item.get("id")) == tid:
                            sen = item.get("sen") or item.get("server")
                            if sen: return str(sen)
                    if len(a) == 1 and isinstance(a[0], dict):
                        sen = a[0].get("sen") or a[0].get("server")
                        if sen: return str(sen)
                if isinstance(a, dict):
                    v = a.get(tid)
                    if v is not None: return str(v)
                for key in ("solution", "assignments_list", "result", "x"):
                    if key in ilp_res:
                        v = _extract_chosen_server(ilp_res[key], task_id)
                        if v: return v
            if isinstance(ilp_res, list):
                for item in ilp_res:
                    if isinstance(item, (tuple, list)) and len(item) >= 2 and str(item[0]) == tid:
                        return str(item[1])
                    if isinstance(item, dict):
                        itid = str(item.get("task_id") or item.get("task") or item.get("id") or "")
                        if itid == tid:
                            sen = item.get("sen") or item.get("server") or item.get("assignment") or item.get("value")
                            if sen: return str(sen)
                if len(ilp_res) == 1 and isinstance(ilp_res[0], str):
                    return ilp_res[0]
            if isinstance(ilp_res, str):
                return ilp_res
            return None

        # ====== CHIAMATA AL SOLVER ======
        objective_mode = str(config.get("ilp_objective", "weighted")).lower()
        if objective_mode == "hierarchical":
            ilp_res = solve_on_Ek_hierarchical(
                snapshot=snap, k=server_selected.name, picked_tasks=[str(task_id)],
                primary=str(config.get("lexi_primary", "energy")).lower(),
                tol=float(config.get("lexi_tol", 0.10)),
                alpha_cpu=alpha_cpu, alpha_net=alpha_net,
                solver_name=str(config.get("ilp_solver", "AUTO")),
                default_net_bw_MBps=bw_MBps,
                debug=bool(config.get("ilp_debug", False)),
                tasks_from_prof=False
            )
        else:
            ilp_res = solve_on_Ek(
                snapshot=snap, k=server_selected.name, picked_tasks=[str(task_id)],
                w_energy=w_e, w_time=w_R,
                alpha_cpu=alpha_cpu, alpha_net=alpha_net,
                solver_name="AUTO", use_node_Rmax_norm=False,
                default_net_bw_MBps=bw_MBps,
                debug=False, tasks_from_prof=False
            )

        print(f"[ILP] res_type={type(ilp_res).__name__} value_preview={str(ilp_res)[:160]}")
        chosen_server_name = _extract_chosen_server(ilp_res, task_id)

        # --- Finalizzazione ILP (se ha successo) ---
        if chosen_server_name:
            print(f"[{env.now:.2f}] [Task {task_id}] ILP chose server: {chosen_server_name}")

            server = next((s for s in neighbors_at_distance_one if s.name == chosen_server_name), server_selected)

            lat = server_selected.get_latency(server)
            bw_MBps_link = server_selected.get_bandwidth(server)
            if (lat is not None) and (bw_MBps_link is not None) and bw_MBps_link > 0:
                transfer_time = ((image_size + Volume_size) * (1024 ** 2) / (bw_MBps_link * (1024 ** 2))) + lat
            else:
                transfer_time = 0.0  # Fallback

            # Usiamo l'helper di finalizzazione comune
            yield from _finalize_and_assign_task(
                env, server_selected, server, task_id,
                image_size, Volume_size, arrival_time_system,
                transfer_time, task_type, d_cpu, deadline,
                required_ram, required_disk,
                initial_server_counter, different_server_counter, other_server_counter
            )
            return  # Fine, ILP ha avuto successo

        else:
            print(f"[{env.now:.2f}] [Task {task_id}] ILP infeasible/none → fallback a euristica v1.")

    # =========================
    # BRANCH: EURISTICA (chiamata a v1)
    # Motivi per essere qui:
    # 1. config["SearchNode"] non era "ILP"
    # 2. config["SearchNode"] era "ILP" ma il solver ha fallito
    # =========================

    print(f"[{env.now:.2f}] [Task {task_id}] Entering HEURISTIC branch (v2) -> calling v1")

    # Passiamo tutti gli argomenti originali a v1, che è funzione euristica standard.
    yield from SearchNode_Heuristic_v1(
        env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
        arrival_time_system,
        initial_server_counter, different_server_counter, other_server_counter,
        task_type, max_energy, d_cpu, deadline
    )

# ---------------------------------------------------------------------------
# FUNZIONI CORE (task e generate_tasks)
# ---------------------------------------------------------------------------

def task(env, task_id, server, initial_server_counter, different_server_counter, other_server_counter, task_data,
         max_energy):
    global hop
    hop = 0
    Volume_size = 0.0
    arrival_time_system = env.now

    # estrai d_cpu e deadline già calcolati in generate_tasks
    d_cpu = task_data.get('d_cpu')
    deadline = task_data.get('deadline')

    required_ram = task_data['required_ram']
    required_disk = task_data['required_disk']
    task_type = task_data['type']
    image_size = task_data['image_size']

    print(f"---> Task {task_id} (Type: {task_type}) arriva in {arrival_time_system:.2f}")

    # --- LOGICA DI SMISTAMENTO (DISPATCHER) ---
    # Scegli quale versione di SearchNode usare in base al config
    # 'v1_heuristic'
    # 'v2_ilp_hybrid'
    policy = config.get("SearchNode", "ERT")

    search_node_args = (
        env, server,
        task_id,
        required_ram,
        required_disk,
        image_size,
        Volume_size,
        arrival_time_system, initial_server_counter, different_server_counter, other_server_counter,
        task_type, max_energy, d_cpu, deadline
    )

    if policy == "ILP":
        print(f"--- [{env.now:.2f}] Task {task_id} using SearchNode Policy: v2_ilp_hybrid ---")
        yield from SearchNode_ILP_Hybrid_v2(*search_node_args)
    else:  # Default a v1_heuristic
        if policy != "ERT":
            print(
                f"--- [{env.now:.2f}] Task {task_id} WARNING: Unknown policy '{policy}'. Defaulting to v1_heuristic ---")
        print(f"--- [{env.now:.2f}] Task {task_id} using SearchNode Policy: v1_heuristic ---")
        yield from SearchNode_Heuristic_v1(*search_node_args)


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

        # Ottieni delta_D (slack percentuale). Default 0.2 = 20%
        raw_delta = config.get("deadline", 0.2)

        # Normalizza: se 10 (int) -> interpretiamo come 10% -> 0.10
        try:
            delta_D = float(raw_delta)
            if delta_D >= 1.0:  # es. 10 -> 0.10, 100 -> 1.0
                delta_D = delta_D / 100.0
        except Exception:
            delta_D = 0.2

        # Safety clamp: assicuriamoci che delta_D sia nell'intervallo [0,1]
        if delta_D < 0.0:
            delta_D = 0.0
        elif delta_D > 1.0:
            delta_D = 1.0

        # stima per la preselezione: calcola d_net_predicted in secondi
        bw_Bps, data_bytes = network_metrics( temp_task_data['image_size'])
        d_net_predicted = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')

        # imposta deadline: D_r = (1 + delta_D) * (d_cpu + d_net)
        D_r = (1.0 + delta_D) * (d_cpu + d_net_predicted)
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
    bw_Bps, data_bytes = network_metrics( image_size_MB)
    task_OBS.d_net = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')
    task_OBS.deadline = arrival_time_system + deadline_relative
    task_OBS.image_size_MB = image_size_MB

    # crea la richiesta: questo inserisce l'elemento in server_obj.net_dev.queue
    req = server_obj.net_dev.request()
    req.task_data = task_OBS  # utile per export_state / monitoring

    # debug/log
    print(f"[{env.now:.3f}] ENQUEUE BATCH id={task_id} on {server_obj.name} "
          f"image_MB={image_size_MB:.2f} queue_len={len(server_obj.net_dev.queue) + 1}")

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

    # Calcolo del tempo di servizio totale
    total_service_time = net_time + time_in_queue_batch

    # sottrai energia di trasmissione
    eps_net = server_obj.compute_routing_energy(data_bytes, bw_Bps, config.get("Ptrasm", 1.0))

    # registra il completamento (usa task_completed come negli altri rami)
    server_obj.task_completed(
        task_id, "Batch", arrival_time_system, arrival_time_system,
        start_service_time, env.now, net_time, total_service_time, time_in_queue_batch,
        server_obj.name, 0, len(server_obj.net_dev.queue),
        0.0, image_size_MB,
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
            total_service_time,  # service_time
            time_in_queue_batch,  # time in queue
            server_obj.name,  # sel_srv (o chi ha eseguito)
            0,  # hops
            len(server_obj.net_dev.queue),  # qlen
            0.0,  # trf
            image_size_MB,
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

    print(
        f"[{env.now:.3f}] BATCH id={task_id} served on {server_obj.name} net_time={net_time:.3f} eps_net={eps_net:.6f}")