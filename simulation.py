import json5
import experiments
import globals
from Task import Task
from sec_ilp_snapshot_v3 import solve_on_Ek, Snapshot, SENState, QueueTask, alpha_from_physics


hop = 0  # Inizializza la variabile hop a zero

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

try:
    with open('img_resolution.json5') as res_file:
        resolution_config = json5.load(res_file)["TASK_GENERATOR_PARAMS"]
except FileNotFoundError:
    print("ERRORE: Impossibile trovare 'img_resolution.json5'. Assicurati che il file esista.")
    resolution_config = None


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


def _build_snapshot_Ek(env, center_server, candidate_servers, current_task_id, d_cpu_req, d_net_MB_req, deadline_req, config):
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


def SearchNode(env, server_selected, task_id, required_ram, required_disk, image_size, Volume_size,
               arrival_time_system,
               initial_server_counter, different_server_counter, other_server_counter,
               task_type, max_energy, d_cpu, deadline):
    """
    Se config['SearchNode'] == 'ILP' usa il tuo modello per scegliere il server su Ek={k}+neighbors[k],
    altrimenti usa la selezione euristica esistente.
    """
    global hop

    # --- Costruisci Ek (self + vicini 1-hop) ---
    neighbors_at_distance_one = list(server_selected.get_neighbors())
    if server_selected not in neighbors_at_distance_one:
        neighbors_at_distance_one.append(server_selected)

    # Banda e dati "di base" per stime e per energia di inoltro
    bw_Bps_global, data_bytes_global = network_metrics(config, image_size, Volume_size_MB=Volume_size)
    d_net_predicted = (data_bytes_global / bw_Bps_global) if bw_Bps_global > 0 else float('inf')

    # =========================
    # BRANCH: ILP
    # =========================
    if str(config.get("SearchNode", "")).upper() == "ILP":
        # d_net per l'ILP è in MB (non in secondi)
        d_net_MB_req = float(image_size + (Volume_size or 0.0))
        
        # DEBUG: segnala ingresso nel branch ILP
        print(f"[{env.now:.2f}] [Task {task_id}] Entering ILP branch")

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

        # --- Coefficienti fisici dal config ---
        P_net = float(config.get("Ptrasm", 1.0))  # W = J/s
        bw_MBps_min = float(config.get("available_bandwidth", {}).get("min", 2150.0))  # MB/s
        bw_Bps = bw_MBps_min * (1024 ** 2)  # converto in Byte/s

        C_sen = float(config.get("C_sen", 1e7))
        e_coef = float(config.get("energy_coefficient", 5e-26))

        # Calcolo fisico tramite funzione comune
        alpha_cpu, alpha_net_J_per_byte = alpha_from_physics(C_sen, e_coef, P_net, bw_Bps)

        # Conversione: da J/byte a J/MB per l’ILP
        alpha_net = alpha_net_J_per_byte * (1024 ** 2)

        # Pesi dal config
        w_e = float(config.get("ilp_weights", {}).get("w_e", 0.5))
        w_R = float(config.get("ilp_weights", {}).get("w_R", 0.5))
        default_bw_MBps = bw_MBps_min


        def _extract_chosen_server(ilp_res, task_id):
            tid = str(task_id)

            # Caso dizionario
            if isinstance(ilp_res, dict):
                a = ilp_res.get("assignments")
                # assignments come LISTA di dict
                if isinstance(a, list):
                    # cerca per task id
                    for item in a:
                        if str(item.get("task") or item.get("task_id") or item.get("id")) == tid:
                            sen = item.get("sen") or item.get("server")
                            if sen: 
                                return str(sen)
                    # edge case: se c'è un solo assignment, prendilo
                    if len(a) == 1 and isinstance(a[0], dict):
                        sen = a[0].get("sen") or a[0].get("server")
                        if sen:
                            return str(sen)
                # (compat) assignments come dict {tid: sen}
                if isinstance(a, dict):
                    v = a.get(tid)
                    if v is not None:
                        return str(v)

                # prova altre chiavi note ricorsivamente
                for key in ("solution", "assignments_list", "result", "x"):
                    if key in ilp_res:
                        v = _extract_chosen_server(ilp_res[key], task_id)
                        if v:
                            return v

            # Caso lista (coppie o dict)
            if isinstance(ilp_res, list):
                for item in ilp_res:
                    if isinstance(item, (tuple, list)) and len(item) >= 2 and str(item[0]) == tid:
                        return str(item[1])
                    if isinstance(item, dict):
                        itid = str(item.get("task_id") or item.get("task") or item.get("id") or "")
                        if itid == tid:
                            sen = item.get("sen") or item.get("server") or item.get("assignment") or item.get("value")
                            if sen:
                                return str(sen)
                if len(ilp_res) == 1 and isinstance(ilp_res[0], str):
                    return ilp_res[0]

            # Caso stringa
            if isinstance(ilp_res, str):
                return ilp_res

            return None



        # ====== QUI CHIAMI IL SOLVER ======
        ilp_res = solve_on_Ek(
            snapshot=snap,
            k=server_selected.name,
            picked_tasks=[str(task_id)],
            w_energy=w_e,
            w_time=w_R,
            alpha_cpu=alpha_cpu,
            alpha_net=alpha_net,                 # J/MB
            solver_name="AUTO",
            use_node_Rmax_norm=False,
            default_net_bw_MBps=default_bw_MBps, # MB/s
            debug=False,
            tasks_from_prof=False
        )

        # DEBUG (utile per capire subito il formato reale)
        print(f"[ILP] res_type={type(ilp_res).__name__} value_preview={str(ilp_res)[:160]}")

        # Normalizza: estrai il server scelto per questo task
        chosen_server_name = _extract_chosen_server(ilp_res, task_id)



        if chosen_server_name:
            
            # DEBUG: segnala il server scelto dall'ILP
            print(f"[{env.now:.2f}] [Task {task_id}] ILP chose server: {chosen_server_name}")
            
            # Oggetto EdgeServer del prescelto
            server = next((s for s in neighbors_at_distance_one if s.name == chosen_server_name), server_selected)
            # Transfer time stimato sul link selezionato (se disponibile), altrimenti globale
            lat = server_selected.get_latency(server)
            bw_MBps_link = server_selected.get_bandwidth(server)
            if (lat is not None) and (bw_MBps_link is not None):
                transfer_time = ((image_size + Volume_size) * (1024 ** 2) / (bw_MBps_link * (1024 ** 2))) + lat
                bw_Bps_for_energy = bw_MBps_link * (1024 ** 2)
                data_bytes_for_energy = (image_size + Volume_size) * (1024 ** 2)
            else:
                transfer_time = 0.0
                bw_Bps_for_energy = bw_Bps_global
                data_bytes_for_energy = data_bytes_global

            # Aggiorna contatori + energia di routing se inoltri
            initial_server_counter[server_selected.name] += 1
            if server is not server_selected:
                different_server_counter[server_selected.name] += 1
                other_server_counter[server.name] += 1
                hop += 1

                # Energia di inoltro (usa link specifico se disponibile, altrimenti globale)
                Ptrasm = config.get("Ptrasm", 1.0)
                eps_net = server_selected.compute_routing_energy(data_bytes_for_energy, bw_Bps_for_energy, Ptrasm) if bw_Bps_for_energy > 0 else 0.0
                server_selected.energy -= eps_net
                print(f"[{env.now:.2f}] [Task {task_id}] ILP Routed {server_selected.name} -> {server.name} | "
                      f"E_NET={eps_net:.6f} J | Remaining={server_selected.energy:.2f} J")
            else:
                # Nessun inoltro
                pass

            # Log per runner/grafici
            globals.gbl_generated_tasks_data.append({
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
            })

            # Vai all'assegnazione vera e propria
            yield from TaskAssignment(env, server, task_id, image_size,
                                      arrival_time_system, hop, transfer_time,
                                      task_type, d_cpu, deadline)
            return
        else:
            print(f"[{env.now:.2f}] [Task {task_id}] ILP infeasible/none → fallback euristico.")

    # =========================
    # BRANCH: EURISTICA (fallback o policy ≠ ILP)
    # =========================
    
    else: 
        # DEBUG: segnala ingresso nel branch euristico (fallback o policy diversa da ILP)
        print(f"[{env.now:.2f}] [Task {task_id}] Entering HEURISTIC branch")
        
        server_metrics = []
        for neighbor in neighbors_at_distance_one:
            latency_to_server = server_selected.get_latency(neighbor)
            bandwidth_to_server = server_selected.get_bandwidth(neighbor)

            if bandwidth_to_server is not None and latency_to_server is not None:
                bandwidth_to_server_Bps = bandwidth_to_server * (1024 ** 2)
                transfer_time = ((image_size + Volume_size) * (1024 ** 2) / bandwidth_to_server_Bps) + latency_to_server
            else:
                transfer_time = 0.0  # non possiamo stimarlo

            selection_score = neighbor.get_selection_score(
                task_type,
                d_cpu=d_cpu,
                d_net=d_net_predicted,
                D_r=deadline,
                energy_budget_max=max_energy,
                file_size_bytes=data_bytes_global,
                bandwidth_Bps=bw_Bps_global
            )

            server_metrics.append({
                'server': neighbor,
                'selection_score': selection_score,
                'transfer_time': transfer_time,
                'orbitalSunset': neighbor.orbitalSunset,
            })

        # Filtra i server non validi
        server_metrics = [m for m in server_metrics if m['orbitalSunset'] not in (None, 0)]
        if not server_metrics:
            print(f"[Task {task_id}] Nessun server valido trovato (euristica).")
            return

        # Ordina per score decrescente
        chosen_info = sorted(server_metrics, key=lambda x: x['selection_score'], reverse=True)[0]
        server = chosen_info['server']
        transfer_time = chosen_info['transfer_time']

        # Aggiorna contatori ed energia inoltro (se serve)
        initial_server_counter[server_selected.name] += 1
        if server != server_selected:
            different_server_counter[server_selected.name] += 1
            other_server_counter[server.name] += 1
            hop += 1

            # energia routing (link specifico se disponibile, altrimenti globale)
            bw_MBps_link = server_selected.get_bandwidth(server)
            if bw_MBps_link is not None:
                bw_Bps_link = bw_MBps_link * (1024 ** 2)
                data_bytes_link = (image_size + Volume_size) * (1024 ** 2)
                bw_for_energy = bw_Bps_link
                data_for_energy = data_bytes_link
            else:
                bw_for_energy = bw_Bps_global
                data_for_energy = data_bytes_global

            Ptrasm = config.get("Ptrasm", 1.0)
            eps_net = server_selected.compute_routing_energy(data_for_energy, bw_for_energy, Ptrasm) if bw_for_energy > 0 else 0.0
            server_selected.energy -= eps_net

            print(f"[{env.now:.2f}] [Task {task_id}] Routed {server_selected.name} -> {server.name} | "
                f"E_NET={eps_net:.6f} J | Remaining={server_selected.energy:.2f} J")

        # Log per runner/grafici
        globals.gbl_generated_tasks_data.append({
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
        })

        # Esegue l'assegnazione
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
