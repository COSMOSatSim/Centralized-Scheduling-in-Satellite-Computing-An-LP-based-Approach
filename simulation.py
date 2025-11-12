import globals
import experiments
from Task import Task
from sec_ilp_snapshot_v3 import solve_on_Ek, Snapshot, SENState, QueueTask, alpha_from_physics, solve_on_Ek_hierarchical
import os
import csv
from collections import defaultdict


# --- STATO BUFFER BATCH ---
_batch_pending = []                # elementi in attesa di flush: dict per task
_batch_csv_path = None
_batch_header_written = False
_batch_seq = 0                     # progressivo dei flush
# CSV di decisione opzionale (utile per debug)
_batch_decisions_csv = None



hop = 0  # Inizializza la variabile hop a zero


# --- Tabu per retry (per-task) ---
_retry_tabu = defaultdict(set)   # task_id -> {server_name}


config = globals.config
resolution_config = globals.resolution_config

C_sen = config.get("C_sen", 1e9)  # parametro costante per il modello energetico CPU
bw_MBps = float(config.get("available_bandwidth", {}).get("min", 2150.0))
bw_Bps = bw_MBps * (1024 ** 2) if bw_MBps is not None else 0.0
e_coeff = config.get("energy_coefficient", 5e-26)  # coefficiente energetico (esempio numerico)

# ---------------------------------------------------------------------------
# HELPER PER DEBUG WHY-NOT
# ---------------------------------------------------------------------------

def _dbg_enabled():
    import globals
    try:
        return bool(globals.config.get("debug_assignment", True))
    except Exception:
        return True

def why_not(env, task_id, stage, reason, **kw):
    if not _dbg_enabled():
        return
    kv = " ".join(f"{k}={v}" for k,v in kw.items())
    print(f"[{env.now:.2f}] [WHY-NOT][{stage}] Task {task_id}: {reason}" + (f" | {kv}" if kv else ""))

class ReasonCollector:
    """Raccoglie motivi di scarto lungo tutti gli hop."""
    def __init__(self):
        self.count = defaultdict(int)
        self.samples = {}

    def add(self, reason, **kw):
        self.count[reason] += 1
        # conserva un solo sample per tipo
        if reason not in self.samples and kw:
            self.samples[reason] = kw

    def dump(self, env, task_id, header=""):
        if not _dbg_enabled():
            return
        if header:
            print(f"[{env.now:.2f}] [WHY-NOT][SUMMARY] Task {task_id}: {header}")
        if not self.count:
            print(f"[{env.now:.2f}] [WHY-NOT][SUMMARY] Task {task_id}: nessun motivo raccolto.")
            return
        print(f"[{env.now:.2f}] [WHY-NOT][SUMMARY] Task {task_id}: motivi (conteggi) ↓")
        for r, c in sorted(self.count.items(), key=lambda x: -x[1]):
            sample = self.samples.get(r, {})
            kv = " ".join(f"{k}={v}" for k,v in sample.items())
            print(f"  - {r}: {c}" + (f" | es.: {kv}" if kv else ""))

# ---------------------------------------------------------------------------

def _canon_name(name: str) -> str:
    if not name:
        return ""
    # togli suffissi tipo " [DTC]" e spazi extra
    n = name.strip()
    i = n.find(' [')
    if i >= 0:
        n = n[:i]
    return n

def _ap_index():
    # indice {canonical_name -> oggetto server}
    return { _canon_name(s.name): s for s in globals.global_access_point }


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
    Calcola le metriche per i server candidati.
    Aggiunge: stima energia E (CPU + NET), risposta R, energia libera B_free.
    """
    server_metrics = []

    # parametri energetici dal config
    C_sen = config.get("C_sen", 1e9)
    e_coeff = config.get("energy_coefficient", 5e-26)
    P_net = config.get("Ptrasm", 1.0)

    for neighbor in neighbors_at_distance_one:
        latency_to_server = server_selected.get_latency(neighbor)
        bandwidth_to_server = server_selected.get_bandwidth(neighbor)

        # Dati (uplink intra-SEN): usa la banda del link corrente->neighbor
        total_data_MB = (image_size + Volume_size)
        total_data_bytes = total_data_MB * (1024 ** 2)
        bw_link_Bps = max(1.0, float(bandwidth_to_server or 0.0))  # evita divisioni per zero
        transfer_time = total_data_bytes / bw_link_Bps

        # Tempo di attesa stimato su neighbor
        try:
            waiting_cpu = neighbor.W_cpu()
        except Exception:
            waiting_cpu = getattr(neighbor, "waiting_time", 0.0)
        try:
            waiting_net = neighbor.W_net()
        except Exception:
            waiting_net = 0.0

        # Tempo servizio lato NET locale (per task NET/batch considera solo rete)
        d_net_on_link = transfer_time

        if task_type in ("Generic_Service", "CPU_Intensive"):
            R = waiting_cpu + d_cpu + d_net_on_link  # cpu + hop netto
        elif task_type == "CPU_and_Data_Intensive":
            R = waiting_cpu + d_cpu + waiting_net + d_net_on_link
        else:
            # Batch / NET-only
            R = waiting_net + d_net_on_link

        # Stima energia
        E_cpu = neighbor.compute_execution_energy(d_cpu, C_sen, e=e_coeff) if d_cpu > 0 else 0.0
        E_net = neighbor.compute_routing_energy(total_data_bytes, bw_link_Bps, Ptrasm=P_net) if total_data_bytes > 0 else 0.0
        E = E_cpu + E_net

        # Energia disponibile (considera la riserva)
        B_free = max(0.0, float(neighbor.energy) - float(getattr(neighbor, "energy_reserved", 0.0)))

        # Sunset previsto per neighbor (se non disponibile, lascia None)
        try:
            orbitalSunset = neighbor.get_orbital_sunset()
        except Exception:
            orbitalSunset = None

        server_metrics.append({
            'server': neighbor,
            'transfer_time': transfer_time,
            'expected_completion_time': R,
            'waiting_cpu': waiting_cpu,
            'waiting_net': waiting_net,
            'd_net_on_link': d_net_on_link,
            'R': R,           # <-- nuovo
            'E': E,           # <-- nuovo
            'B_free': B_free, # <-- nuovo
            'orbitalSunset': orbitalSunset,
            'energy_cpu': E_cpu,
            'energy_net': E_net,
        })

    return server_metrics



def _filter_and_select_best_server(server_metrics, deadline, task_id, task_type,
                                   arrival_time_system, image_size, server_selected, config):
    """
    Applica:
      1) filtro orbitalSunset (se richiesto dalla distribuzione),
      2) filtro HARD: R <= deadline e E <= B_free,
      3) filtro tabu (server già tentati dal task),
      4) ranking normalizzato con pesi energia/tempo.
    """
    # 0) Filtra sunset se OrbitAware
    distribution = config.get("request_distribution", {}).get("distribution", "")
    if distribution in ("DTS-base", "DTS-AP optimal"):
        metrics = [m for m in server_metrics if m.get('orbitalSunset') not in (0, )]
    else:
        # orbit-aware: richiede sunset valido e che R finisca prima del tramonto
        metrics = [m for m in server_metrics
                   if m.get('orbitalSunset') not in (None, 0)]

    # 1) Filtro HARD (deadline + energia)
    feasible = []
    for m in metrics:
        R = m['R']
        E = m['E']
        B_free = m['B_free']
        if R <= deadline and E <= B_free:
            feasible.append(m)

    if not feasible:
        # segnala rifiuto con motivazione più esplicita
        server_selected.record_rejected_task(
            task_id, task_type, arrival_time_system, image_size,
            "No suitable server after hard filters (deadline/energy)"
        )
        return None, "No suitable server after hard filters (deadline/energy)"

    # 2) Tabu: evita server già provati (rimbalzi)
    tabu = _retry_tabu.get(task_id, set())
    feasible = [m for m in feasible if m['server'].name not in tabu]
    if not feasible:
        # se tutti tabu, azzera tabu per questo task (diversificazione morbida)
        _retry_tabu[task_id].clear()
        feasible = [m for m in metrics if (m['R'] <= deadline and m['E'] <= m['B_free'])]

    # 3) Ranking normalizzato
    we = float(config.get("weights", {}).get("we", 0.5))
    wR = 1.0 - we

    # normalizzazioni stabili
    Rmax = max(m['R'] for m in feasible) or 1.0
    # per energia normalizziamo su energia disponibile del server
    def score(m):
        R_hat = m['R'] / Rmax
        E_hat = m['E'] / (m['B_free'] or 1.0)
        # opzionale: piccola penalità se vicino al tramonto o code alte
        penalty = 0.0
        try:
            sunset = float(m.get('orbitalSunset') or 0.0)
            if sunset and sunset < (deadline * 1.1):
                penalty += 0.05  # penalità lieve
        except Exception:
            pass
        return we * E_hat + wR * R_hat + penalty


    feasible.sort(key=score)
    chosen_metric = feasible[0]

    # aggiorna tabu: aggiungo i non scelti per un giro
    others = [m for m in feasible[1:]]
    if others:
        _retry_tabu[task_id].update({m['server'].name for m in others})

    return chosen_metric, None



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
        ap = _ap_index()
        neighbors_at_distance_one = [n for n in server_selected.get_neighbors() if _canon_name(n.name) in ap]
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

        why_not(env, task_id, "ILP-SNAPSHOT",
            "Ek costruito",
            SENs=len(snap.sen), picked="1", neighbors=len(snap.neighbors.get(server_selected.name, [])),
            primary=str(config.get("lexi_primary", "energy")).lower(), tol=float(config.get("lexi_tol", 0.10)), bw_MBps=bw_MBps)



        # ====== CHIAMATA AL SOLVER ======
        objective_mode = str(config.get("ilp_objective", "weighted")).lower()
        if objective_mode == "hierarchical":
            ilp_res = solve_on_Ek_hierarchical(
                snapshot=snap, k=server_selected.name, picked_tasks=[str(task_id)],
                primary=str(config.get("lexi_primary", "energy")).lower(),
                tol=float(config.get("lexi_tol", 0.10)),
                alpha_cpu=alpha_cpu, alpha_net=alpha_net,
                solver_name=str(config.get("ilp_solver", "CBC")),
                default_net_bw_MBps=bw_MBps,
                debug=bool(config.get("ilp_debug", False)),
                tasks_from_prof=False
            )
            
            # esito solver
            status = getattr(ilp_res, "status", None) if hasattr(ilp_res, "status") else None
            why_not(env, task_id, "ILP-RESULT", "risultato ricevuto", status=status)
            
        else:
            ilp_res = solve_on_Ek(
                snapshot=snap, k=server_selected.name, picked_tasks=[str(task_id)],
                w_energy=w_e, w_time=w_R,
                alpha_cpu=alpha_cpu, alpha_net=alpha_net,
                solver_name="CBC", use_node_Rmax_norm=False,
                default_net_bw_MBps=bw_MBps,
                debug=False, tasks_from_prof=False
            )

        print(f"[ILP] res_type={type(ilp_res).__name__} value_preview={str(ilp_res)[:160]}")
        chosen_server_name = _extract_chosen_server(ilp_res, task_id)
        
        ap = _ap_index()
        chosen_key = _canon_name(chosen_server_name or "")
        server = ap.get(chosen_key, None)
        if server is None:
            # log e fallback
            why_not(env, task_id, "INVALID-TARGET",
                    "server scelto non presente in AP set (skip)",
                    chosen=chosen_server_name, chosen_canon=chosen_key)
            # prova il best dei rimanenti o ritorna al server_selected
            server = server_selected

        if not chosen_server_name:
            why_not(env, task_id, "ILP-NO-ASSIGN",
                    "nessuna assegnazione dal solver (infeasible/none?)",
                    note="verifica vincoli: deadline/energia/code/banda")

        # --- Finalizzazione ILP (se ha successo) ---
        if chosen_server_name:
            print(f"[{env.now:.2f}] [Task {task_id}] ILP chose server: {chosen_server_name}")
            
            ap = _ap_index()
            if _canon_name(server.name) not in ap:
                why_not(env, task_id, "FORWARD-BLOCKED",
                        "target SEN non nel dataset, inoltro bloccato",
                        target=server.name)
                # tenta un altro vicino valido o fai backoff
                return  # oppure ricadi alla selezione successiva

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

        # >>> NUOVO: log nel buffer al momento dell'ingresso <<<
        add_to_batch_buffer(task_id, env.now, D_r, temp_task_data)  # <— passiamo anche il payload


        # ⛔️ NON lanciare il task "normale" se il batching è attivo
        batching_cfg = config.get("batching", {})
        if not batching_cfg.get("enabled", False):

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

# --------------------------------------------------------------------------- CODICE NUOVO -----------------
# BATCHING CON ILP GERARCHICO
# ----------------------------------------------------------------------------------------------------------

# Buffer globale per i task in attesa di batching
def add_to_batch_buffer(task_id: int | str, entry_time: float, deadline_remaining_s: float, payload: dict | None = None):
    tid = int(task_id)
    
    p = dict(payload) if isinstance(payload, dict) else {}
    # 👇 init current_server_id se mancante
    if p.get("current_server_id") is None and globals.global_access_point:
        p["current_server_id"] = max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)).name

    # 👇 init/merge set di visitati
    visited = set(p.get("visited", []))
    if p.get("current_server_id"):
        visited.add(p["current_server_id"])
    p["visited"] = list(visited)

    # se esiste già un item per quel task_id nel buffer, aggiorna in-place
    existing_idx = next((i for i, it in enumerate(_batch_pending) if int(it.get("task_id")) == tid), None)
    new_item = {
        "task_id": tid,
        "entry_time": float(entry_time),
        "deadline_remaining_s": float(deadline_remaining_s),
        "payload": p,
        "retry_count": int(payload.get("retry_count", 0)) if isinstance(payload, dict) else 0,
        "hops": int(payload.get("hops", 0)) if isinstance(payload, dict) else 0,
    }
    if existing_idx is not None:
        _batch_pending[existing_idx] = new_item
    else:
        _batch_pending.append(new_item)

    # log: usa il tempo corrente per rendere l’ordine leggibile nel CSV
    _batch_write_row(["ENQUEUE", tid, float(globals.env.now if hasattr(globals, "env") else entry_time),
                      len(_batch_pending), float(deadline_remaining_s), ""])




# Avvia il processo di batching periodico
def start_batch_buffer(env, csv_path: str, interval_s: float = 0.1, decisions_csv_path: str | None = None):
    """
    Ogni 'interval_s':
      - logga PROCESS dei task correnti,
      - risolve ILP gerarchico per assegnarli,
      - consegna i task e svuota il buffer.
    """
    global _batch_csv_path, _batch_header_written, _batch_seq, _batch_decisions_csv
    _batch_csv_path = csv_path
    _batch_decisions_csv = decisions_csv_path
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    _batch_header_written = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    _batch_seq = 0

    # Processo interno di batching
    def _writer():
        global _batch_seq  # se già presente, ok
        while True:
            yield env.timeout(interval_s)

            if not _batch_pending:
                continue

            t_now = env.now

            # 1) snapshot degli elementi correnti (con deduplica per task_id)
            raw = _batch_pending[:]          # copia del buffer
            # 2) SWAP: svuota SUBITO il buffer, così i requeue vanno in un buffer "nuovo"
            del _batch_pending[:]            # <-- non rimuovere questa riga

            # Deduplica: per ogni task_id tieni l'item "più nuovo"
            by_tid = {}
            def _key(it):
                # priorità: retry_count > hops > entry_time
                return (
                    int(it.get("retry_count", 0)),
                    int(it.get("hops", 0)),
                    float(it.get("entry_time", 0.0)),
                )

            for it in raw:
                tid = int(it["task_id"])
                if tid not in by_tid or _key(it) > _key(by_tid[tid]):
                    by_tid[tid] = it

            snapshot = list(by_tid.values())
            buffer_size_before = len(snapshot)

            # (facoltativo) log se sono stati rimossi duplicati
            removed = len(raw) - len(snapshot)
            if removed > 0:
                print(f"[BATCH][DEDUP] removed {removed} stale entries before ILP")               # <-- differenza chiave!

            # 3) log PROCESS
            for item in snapshot:
                _batch_write_row([
                    "PROCESS", item["task_id"], t_now, buffer_size_before,
                    item["deadline_remaining_s"], _batch_seq
                ])

            try:
                # 4) ILP + consegna
                assignments = _process_batch_with_ilp(env, snapshot)
                _write_batch_decisions(assignments, batch_seq=_batch_seq, t_now=t_now)

                for item in snapshot:
                    task_id = item["task_id"]
                    chosen = assignments.get(task_id)
                    _deliver_assignment(env, item, chosen)

                print(f"[BATCH][EXEC] ILP batch executed")
                _batch_seq += 1

            except Exception as e:
                print(f"[BATCH][ERROR] ILP batch failed at t={t_now}: {e}")
                # 5) ripristina gli elementi dello snapshot (non persi) per il prossimo tick
                _batch_pending.extend(snapshot)

            # 6) NON svuotare qui: niente _batch_pending.clear()


    return env.process(_writer())


# Scrittura CSV di decisioni batch (opzionale)
def _batch_write_row(row):
    """Scrive una riga nel CSV; crea header se necessario."""
    global _batch_header_written
    if _batch_csv_path is None:
        return
    os.makedirs(os.path.dirname(_batch_csv_path), exist_ok=True)
    write_header = not _batch_header_written or not os.path.exists(_batch_csv_path) or os.path.getsize(_batch_csv_path) == 0
    with open(_batch_csv_path, mode="a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["event", "task_id", "t", "buffer_size", "deadline_remaining_s", "batch_seq"])
            _batch_header_written = True
        w.writerow(row)



def _process_batch_with_ilp(env, snapshot_items: list[dict]) -> dict[int, str]:
    if not snapshot_items:
        return {}

    # 1) Pulisci payload e raggruppa per current_server_id
    groups: dict[str, list[dict]] = {}
    for it in snapshot_items:
        p = dict(it.get("payload") or {})
        p["id"] = it["task_id"]
        if "deadline" not in p:
            p["deadline"] = it["deadline_remaining_s"]
        k_id = p.get("current_server_id")
        if not k_id and globals.global_access_point:
            k_id = max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)).name
            p["current_server_id"] = k_id
        groups.setdefault(str(k_id), []).append(p)

    # 2) Parametri fisici/solver
    P_net = float(config.get("Ptrasm", 1.0))
    alpha_cpu, alpha_net_J_per_byte = alpha_from_physics(C_sen, e_coeff, P_net, bw_Bps)
    alpha_net = alpha_net_J_per_byte * (1024 ** 2)
    primary = str(config.get("lexi_primary", "energy")).lower()
    tol = float(config.get("lexi_tol", 0.10))
    solver_name = str(config.get("ilp_solver", "CBC"))
    debug = bool(config.get("ilp_debug", False))

    all_assignments: dict[int, str] = {}

    # 3) Esegui ILP per ogni gruppo (Ek locale), con guard su k
    for k_id, tasks_payloads in groups.items():
        snap = _build_snapshot_for_batch(env, tasks_payloads)
        sen_names = set(snap.sen.keys())

        # -- GUARD: se k_id non esiste nello snapshot, riassegna k --
        if k_id not in sen_names:
            # scegli un seed valido nello snapshot (max energia)
            if sen_names:
                seed_srv = max(
                    (s for s in globals.global_access_point if s.name in sen_names),
                    key=lambda s: getattr(s, "energy", 0.0),
                )
                new_k = seed_srv.name
            else:
                # scenario estremo: nessun SEN -> nessuna assegnazione
                new_k = None

            # aggiorna il current_server_id dei payload del gruppo per evitare loop futuri
            if new_k:
                for p in tasks_payloads:
                    p["current_server_id"] = new_k
                k_id = new_k
            else:
                # Non c'è nulla da fare: salta questo gruppo (verrà riaccodato con deadline ridotta)
                continue

        picked_tasks = [str(p["id"]) for p in tasks_payloads]

        # --- DEBUG: riassunto batch locale su Ek=k_id ---
        try:
            slacks = []
            for p in tasks_payloads:
                D_rel = float(p.get("deadline", 300.0) or 300.0)  # è relativo
                # NB: env.now è “adesso”, l’arrivo del task non lo abbiamo qui -> usiamo D_rel come proxy di slack residuo
                slacks.append(D_rel)
            if slacks:
                sl_min = min(slacks); sl_med = sorted(slacks)[len(slacks)//2]; sl_max = max(slacks)
                why_not(env, "BATCH", "ILP-PREFLIGHT",
                    f"Ek={k_id} con {len(tasks_payloads)} task",
                    SENs=len(snap.sen))
        except Exception:
            pass


        ilp_res = solve_on_Ek_hierarchical(
            snapshot=snap,
            k=str(k_id),
            picked_tasks=picked_tasks,
            primary=primary,
            tol=tol,
            alpha_cpu=alpha_cpu,
            alpha_net=alpha_net,
            solver_name=solver_name,
            default_net_bw_MBps=bw_MBps,
            debug=debug,
            tasks_from_prof=False
        )

        all_assignments.update(_extract_assignments_from_solution(ilp_res))


        # --- DEBUG: copertura assegnazioni su questo gruppo ---
        missing = [p["id"] for p in tasks_payloads if int(p["id"]) not in all_assignments]
        if missing:
            why_not(env, "BATCH", "ILP-PARTIAL",
                    f"alcuni task senza assegnazione su Ek={k_id}",
                    missing_ids=",".join(map(str, missing)))


    return all_assignments




def _build_snapshot_for_batch(env, tasks_payloads: list[dict]):
    """
    Costruisce uno Snapshot 'globale' al tempo corrente che include:
      - tutti i SEN visibili (globals.global_access_point),
      - la mappa dei vicini a 1-hop,
      - TUTTE le richieste (requests) del batch corrente.

    d_net dei task è espresso in **MB** (come fa già _build_snapshot_Ek), il solver
    convertirà in secondi usando default_net_bw_MBps.
    """
    sen_map = {}
    neighbors_map = {}
    listening = []

    # 1) Costruisci stato dei SEN (come nella tua _build_snapshot_Ek)
    for srv in globals.global_access_point:
        st = srv.export_state(env)  # richiede enable_queue_monitoring=true
        B = float(st.get("energy_budget_J", getattr(srv, "energy", 0.0)))
        B_max = float(config.get("initial_energy", B if B > 0 else 1.0))

        cpu_q, net_q = _merge_queues_for_ilp(st)

        s_state = SENState(
            B=B,
            B_max=B_max,
            Rmax_norm=1.0,
            cpu_queue=cpu_q,
            net_queue=net_q,
            in_service_cpu=None,
            in_service_net=None,
            net_bw_bps=None  # lascio None: il solver userà default_net_bw_MBps
        )
        sen_map[srv.name] = s_state

        # vicini per nome
        neigh_names = [n.name for n in srv.get_neighbors()]
        neighbors_map[srv.name] = neigh_names

        if st.get("in_listening_dome", False):
            listening.append(srv.name)

    # 2) Prepara le richieste del batch
    requests = []
    for p in tasks_payloads:
        tid = str(p.get("id"))
        task_type = p.get("type", "Generic_Service")
        d_cpu_req = float(p.get("d_cpu", 0.0) or 0.0)

        # per d_net in MB: se è CPU+DATA o Batch, usa image_size; altrimenti 0
        if task_type in ("CPU_and_Data_Intensive", "Batch"):
            d_net_MB_req = float(p.get("image_size", 0.0) or 0.0)
        else:
            d_net_MB_req = 0.0

        D_req = float(p.get("deadline", 300.0) or 300.0)

        requests.append(QueueTask(
            task_id=tid,
            d_cpu=d_cpu_req,
            d_net=d_net_MB_req,   # MB!
            D=D_req
        ))

    snap = Snapshot(
        time=float(env.now),
        listening_dome=listening,
        neighbors=neighbors_map,
        sen=sen_map,
        requests=requests,
        pre_R={},
        pre_E={}
    )
    return snap



def _extract_assignments_from_solution(sol) -> dict[int, str]:
    """
    Estrae {task_id:int -> server_id:str} dalla soluzione ILP.
    Supporta vari formati (dict/list/obj).
    """
    assignments: dict[int, str] = {}

    def _add(tid, sid):
        try:
            assignments[int(str(tid))] = str(sid)
        except Exception:
            pass

    if isinstance(sol, dict):
        # formati tipici
        if "assignments" in sol and isinstance(sol["assignments"], list):
            for a in sol["assignments"]:
                _add(a.get("task") or a.get("task_id") or a.get("id"),
                     a.get("sen") or a.get("server") or a.get("server_id"))
        elif "x" in sol and isinstance(sol["x"], dict):
            for tid, sid in sol["x"].items():
                _add(tid, sid)
        else:
            # prova ricorsivo su sotto-chiavi
            for v in sol.values():
                sub = _extract_assignments_from_solution(v)
                assignments.update(sub)
    elif isinstance(sol, list):
        for item in sol:
            if isinstance(item, dict):
                _add(item.get("task") or item.get("task_id") or item.get("id"),
                     item.get("sen") or item.get("server") or item.get("server_id"))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                _add(item[0], item[1])
    else:
        # oggetto con attributi?
        try:
            for a in getattr(sol, "assignments", []):
                _add(getattr(a, "task_id", None), getattr(a, "server_id", None))
        except Exception:
            pass

    return assignments



def _deliver_assignment(env, item: dict, chosen_server_id: str | None):
    task_id = item["task_id"]
    payload = dict(item.get("payload") or {})
    retry_count = int(item.get("retry_count", 0))
    hops = int(item.get("hops", 0))

    max_retries = int(config.get("batching", {}).get("max_retries", 3))
    max_hops    = int(config.get("batching", {}).get("max_hops", 5))

    # parametri utili
    arrival_time_system = float(item.get("entry_time", env.now))
    image_size_MB = float(payload.get("image_size", 0.0) or 0.0)
    volume_MB     = float(payload.get("Volume_size", 0.0) or 0.0)
    task_type     = payload.get("type", "Generic_Service")
    d_cpu         = float(payload.get("d_cpu", 0.0) or 0.0)
    D_r_init      = float(payload.get("deadline", item.get("deadline_remaining_s", 300.0)) or 300.0)

    # tempo trascorso dall'arrivo -> slack residuo
    elapsed = max(0.0, env.now - arrival_time_system)
    D_r_remaining = max(0.001, D_r_init - elapsed)

    # helper robusto per aggiornare l'entry corretta nel buffer dopo add_to_batch_buffer
    def _update_pending_fields(tid: int, retry: int, hopv: int):
        idx = next((i for i, it in enumerate(_batch_pending) if int(it.get("task_id")) == int(tid)), None)
        if idx is not None:
            _batch_pending[idx]["retry_count"] = retry
            _batch_pending[idx]["hops"] = hopv

    # Caso 1: ILP ha assegnato un server -> consegna immediata
    srv = next((s for s in globals.global_access_point if s.name == chosen_server_id), None)
    if chosen_server_id and srv is not None:
        # ✅ log positivo (prima c’era un 'NO-ASSIGN' qui, da rimuovere)
        why_not(env, task_id, "BATCH-ASSIGN", "solver ha assegnato un server", server=chosen_server_id)

        transfer_time = 0.0  # consegna diretta (il batch decide e avviamo TaskAssignment)
        _batch_write_row(["ASSIGN", task_id, float(env.now), len(_batch_pending),
                          float(D_r_remaining), str(chosen_server_id)])
        env.process(TaskAssignment(
            env, srv, task_id, image_size_MB,
            arrival_time_system, hops, transfer_time,
            task_type, d_cpu, D_r_init      
        ))
        return

    # Se siamo qui: nessuna assegnazione dal solver per questo task
    why_not(env, task_id, "BATCH-NO-ASSIGN", "nessuna assegnazione dal solver per questo task")

    # Caso 2: inoltro a un vicino del server corrente
    current_sid = payload.get("current_server_id")
    current_srv = next((s for s in globals.global_access_point if s.name == current_sid), None)

    if current_srv is None and globals.global_access_point:
        current_srv = max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0))
        payload["current_server_id"] = current_srv.name
        print(f"[{env.now:.2f}] [BATCH] Task {task_id}: current_server_id non valido, riassegnato a seed={current_srv.name}")

    if current_srv is None:
        # fallback finale: niente vicini e nessun server noto
        if retry_count >= max_retries:
            print(f"[{env.now:.2f}] [BATCH] Task {task_id}: max retries reached, trying heuristic fallback")
            # prova ultima spiaggia
            fallback_server = max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)) if globals.global_access_point else None
            if fallback_server and getattr(fallback_server, "energy", 0.0) > 0:
                print(f"[{env.now:.2f}] [BATCH] Task {task_id}: fallback assigned to {fallback_server.name}")
                env.process(TaskAssignment(
                    env, fallback_server, task_id, image_size_MB,
                    arrival_time_system, hops, 0.0,
                    task_type, d_cpu, D_r_remaining
                ))
                return

            # reject loggando su un server sensato (non usare current_srv, è None)
            print(f"[{env.now:.2f}] [BATCH] Task {task_id}: all attempts failed -> task rejected")
            log_srv = fallback_server or (max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)) if globals.global_access_point else None)
            if log_srv:
                log_srv.record_rejected_task(
                    task_id, task_type, arrival_time_system, image_size_MB,
                    f"Max retries ({max_retries}) exhausted in batch"
                )
            return

        # riaccodo “puro”
        add_to_batch_buffer(task_id, arrival_time_system, D_r_remaining, payload)
        _update_pending_fields(task_id, retry_count + 1, hops)
        print(f"[{env.now:.2f}] [BATCH] Task {task_id}: requeued (no-current), retry {retry_count+1}/{max_retries}")
        return

    # limite hop?
    if hops >= max_hops:
        log_srv = current_srv or (max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)) if globals.global_access_point else None)
        if log_srv is not None:
            log_srv.record_rejected_task(
                task_id, task_type, arrival_time_system, image_size_MB,
                f"Max hops ({max_hops}) reached in batch"
            )
        _batch_write_row(["REJECTED", task_id, float(env.now), len(_batch_pending),
                          float(D_r_remaining), "max_hops"])
        why_not(env, task_id, "BATCH-MAX-HOPS", f"raggiunto limite hop ({max_hops})")
        return

    visited = set(payload.get("visited", []))
    # evita anche il backtrack immediato
    visited.add(payload.get("current_server_id", ""))

    neighbor, _ = _pick_best_neighbor(current_srv, exclude=visited)
    if neighbor is not None and neighbor.name not in {s.name for s in globals.global_access_point}:
        why_not(env, task_id, "BATCH-NEIGHBOR-INVALID",
                "neighbor non fa parte del set AP (ignoro)", neighbor=neighbor.name)
        neighbor = None
    if neighbor is None:
        # nessun vicino: retry oppure reject
        if retry_count >= max_retries:
            print(f"[{env.now:.2f}] [BATCH] Task {task_id}: max retries reached, trying heuristic fallback")
            print(f"[{env.now:.2f}] [BATCH] Task {task_id}: all attempts failed -> task rejected")
            log_srv = current_srv or (max(globals.global_access_point, key=lambda s: getattr(s, "energy", 0.0)) if globals.global_access_point else None)
            if log_srv:
                log_srv.record_rejected_task(
                    task_id, task_type, arrival_time_system, image_size_MB,
                    f"Max retries ({max_retries}) exhausted in batch"
                )
            _batch_write_row(["REJECTED", task_id, float(env.now), len(_batch_pending),
                              float(D_r_remaining), "max_retries"])
            return

        all_neighbors = [n.name for n in (current_srv.get_neighbors() or []) if n.name in {s.name for s in globals.global_access_point}]
        if all(n in visited for n in all_neighbors) and all_neighbors:
            why_not(env, task_id, "BATCH-CYCLE", "tutti i vicini già visitati", current=current_srv.name, visited=",".join(sorted(visited)))
            # policy: o retry senza incrementare hop, o fallback ILP locale, o reject elegante
            add_to_batch_buffer(task_id, arrival_time_system, D_r_remaining, payload)
            _update_pending_fields(task_id, retry_count + 1, hops)  # 👈 niente hops+1 qui
            print(f"[{env.now:.2f}] [BATCH] Task {task_id}: cycle detected, requeued (no-progress), retry {retry_count+1}/{max_retries}")
            return

        # aggiorna memoria di percorso
        visited.add(neighbor.name)
        payload["visited"] = list(visited)
        payload["current_server_id"] = neighbor.name
        add_to_batch_buffer(task_id, arrival_time_system, D_r_remaining, payload)
        _update_pending_fields(task_id, retry_count + 1, hops)
        print(f"[{env.now:.2f}] [BATCH] Task {task_id}: requeued (no-neighbors), retry {retry_count+1}/{max_retries}")
        return

    # stima transfer_time reale per inoltro
    total_MB = image_size_MB + volume_MB
    bw_MBps  = current_srv.get_bandwidth(neighbor) or 0.0
    latency  = current_srv.get_latency(neighbor) or 0.0
    if bw_MBps > 0:
        transfer_time = (total_MB / bw_MBps) + latency
    else:
        transfer_time = latency if latency > 0 else 0.05  # piccolo minimo

    # aggiorna deadline residua “dopo l’inoltro”
    D_r_next = max(0.001, D_r_remaining - transfer_time)

    # aggiorna router corrente e hop
    payload["current_server_id"] = neighbor.name

    # riaccoda per il prossimo batch (ora "vive" sul vicino)
    add_to_batch_buffer(task_id, arrival_time_system, D_r_next, payload)
    _update_pending_fields(task_id, retry_count + 1, hops + 1)

    why_not(env, task_id, "BATCH-FORWARD",
            "inoltro al vicino",
            src=current_srv.name, dst=neighbor.name,
            hops=hops+1)

    print(f"[{env.now:.2f}] [BATCH] Task {task_id}: forwarded {current_srv.name} -> {neighbor.name} "
          f"(hop {hops+1}), xfer={transfer_time:.3f}s, D_rem={D_r_next:.3f}s")
    _batch_write_row(["FORWARD", task_id, float(env.now), len(_batch_pending),
                      float(D_r_next), f"{current_srv.name}->{neighbor.name}"])



# helper per la scelta del miglio vicino
def _pick_best_neighbor(current_srv, exclude=None):
    """
    Ritorna (neighbor_srv, transfer_time_s) oppure (None, None) se non ci sono vicini.
    Seleziona solo vicini appartenenti a globals.global_access_point e non presenti in 'exclude'.
    """
    exclude = set(exclude or [])
    try:
        neighbors_all = list(current_srv.get_neighbors())
    except Exception:
        neighbors_all = []

    if not neighbors_all:
        return None, None

    # Mantieni solo i vicini che sono davvero "validi" nel contesto del batch/ILP
    ap_names = set(_ap_index().keys())
    neighbors = [n for n in neighbors_all if _canon_name(n.name) in ap_names]


    if not neighbors:
        return None, None

    # Stima semplice: minimize (latency + 1/bw)
    def _score(nbr):
        bw_MBps = current_srv.get_bandwidth(nbr)  # MB/s
        lat = current_srv.get_latency(nbr) or 0.0
        if not bw_MBps or bw_MBps <= 0:
            return float('inf')
        return lat + (1.0 / bw_MBps)

    best = min(neighbors, key=_score)
    return best, None




# Scrittura CSV di decisioni batch (opzionale)
def _write_batch_decisions(assignments: dict[int, str], batch_seq: int, t_now: float):
    if not _batch_decisions_csv:
        return
    os.makedirs(os.path.dirname(_batch_decisions_csv), exist_ok=True)
    new_file = not os.path.exists(_batch_decisions_csv)
    with open(_batch_decisions_csv, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["batch_seq", "t", "task_id", "server_id"])
        for tid, sid in assignments.items():
            w.writerow([batch_seq, t_now, tid, sid])

