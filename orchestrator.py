import heapq
import simpy
import globals
import pulp
import ILP_simulation
import utils
from Task import Task
from EdgeServer import get_pos_proximity

class Orchestrator:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        
        # Recupero parametri di batch dal config
        self.batch_size = config.get("centralized_batch_size", 5)
        self.batch_timeout = config.get("centralized_batch_timeout", 0.25)
        
        self.task_buffer = []
        
        # Eventi SimPy
        self.item_arrived_event = self.env.event()
        self.batch_ready_event = self.env.event()
        
        # Avvia il processo in background dell'orchestratore
        self.env.process(self._run_loop())

    def add_task(self, task_data, task_id, visible_aps):
        """
        Aggiunge un task al buffer e gestisce i trigger degli eventi.
        Viene chiamata esternamente
        """
        # Se il buffer era vuoto, sblocca il loop segnalando l'arrivo del primo task
        if not self.task_buffer and not self.item_arrived_event.triggered:
            self.item_arrived_event.succeed()

        # Aggiungiamo il task con i metadati necessari per l'ILP
        self.task_buffer.append({
            "task_id": task_id,
            "data": task_data,
            "visible_aps": visible_aps,
            "arrival_time": self.env.now
        })

        # Se raggiungiamo la capienza massima N, forziamo l'esecuzione del batch
        if len(self.task_buffer) >= self.batch_size and not self.batch_ready_event.triggered:
            self.batch_ready_event.succeed()

    def _run_loop(self):
        """
        Ciclo vitale dell'orchestratore. Gestisce le attese senza bloccare l'ambiente.
        """
        while True:
            # 1. Attende in letargo l'arrivo del PRIMO task
            if not self.task_buffer:
                yield self.item_arrived_event

            # 2. Partenza del timer (Timeout)
            timeout_event = self.env.timeout(self.batch_timeout)

            # 3. Attende che si verifichi IL PRIMO dei due eventi
            yield self.batch_ready_event | timeout_event

            # 4. Processa i task accumulati
            if self.task_buffer:
                trigger_reason = "Capacità massima" if self.batch_ready_event.triggered else "Timeout"
                print(f"[{self.env.now:.3f}] Orchestrator: Trigger ILP per {trigger_reason} ({len(self.task_buffer)} tasks).")
                self._process_batch()

            # 5. Reset degli eventi per il prossimo ciclo
            self.item_arrived_event = self.env.event()
            self.batch_ready_event = self.env.event()

    def _process_batch(self):
        """
        Funzione core che orchestra il flusso di risoluzione.
        """
        # A. Mappatura della costellazione
        network_state = self._map_constellation()
        
        # B. Chiamata al risolutore ILP (ora basato su PuLP)
        assignments = self._solve_ilp(network_state, self.task_buffer)
        print(f"[{self.env.now:.3f}] Orchestrator: ILP completato.")

        # C. Esecuzione/Smistamento dei task in base ai risultati dell'ILP
        self._dispatch_tasks(assignments)

        # Svuotiamo il buffer per il prossimo batch
        self.task_buffer.clear()


    def _map_constellation(self):
        """
        Mappa i percorsi migliori da ogni AP a tutti i satelliti (SEN) usando Dijkstra.
        Il costo del link è calcolato come combinazione pesata di Tempo ed Energia.
        """
        # Recuperiamo i pesi per la funzione di costo dal file di configurazione
        w_e = self.config.get("centralized_w_e", 0.5)
        w_R = self.config.get("centralized_w_r", 0.5)
        p_trasm = self.config.get("Ptrasm", 1.0)

        # Utilizziamo 1 MB come dato di riferimento (in byte) per standardizzare
        # i calcoli di tempo ed energia sui vari link.
        REF_DATA_BYTES = 1024 * 1024 

        network_state = {
            "routing_table": {}, # Formato: {ap_name: {sen_name: {'cost': X, 'time': Y, 'energy': Z, 'path': [...]}}}
            "node_states": {}    # Formato: {sen_name: {'energy_residual': X, 'cpu_queue': Y, ...}}
        }

        # 1. Raccogliamo tutti i nodi della topologia per facilitarci la ricerca
        all_nodes = globals.global_access_point + globals.edge_servers
        node_dict = {n.name: n for n in all_nodes}

        # 2. Dijkstra Multi-Sorgente: da ogni AP esploriamo la rete
        for ap in globals.global_access_point:
            network_state["routing_table"][ap.name] = {}
            
            # Coda di priorità. Struttura tupla:
            # (costo_totale, tempo_totale, energia_totale, nome_nodo_corrente, path_fino_a_qui)
            pq = [(0.0, 0.0, 0.0, ap.name, [ap.name])]
            
            # Traccia il costo minimo scoperto per raggiungere ciascun nodo da questo AP
            min_costs = {ap.name: 0.0}

            while pq:
                current_cost, current_time, current_energy, current_node_name, path = heapq.heappop(pq)
                
                # Se abbiamo estratto un percorso obsoleto (sub-ottimale), lo ignoriamo
                if current_cost > min_costs.get(current_node_name, float('inf')):
                    continue

                # Se il nodo corrente è un Satellite (SEN), salviamo il suo percorso definitivo
                current_node_obj = node_dict[current_node_name]
                if current_node_obj in globals.edge_servers:
                    network_state["routing_table"][ap.name][current_node_name] = {
                        "total_cost": current_cost,
                        "total_time": current_time,
                        "total_energy": current_energy,
                        "path": path
                    }

                # Esploriamo i vicini fisici del nodo corrente
                for neighbor in current_node_obj.get_neighbors():

                    if neighbor.name not in node_dict:
                        continue

                    # Estraiamo le metriche fisiche del link
                    latency = current_node_obj.get_latency(neighbor) or 0.0
                    bw_MBps = current_node_obj.get_bandwidth(neighbor) or 0.0
                    bw_Bps = bw_MBps * (1024**2)

                    # Se non c'è banda, il link è interrotto:
                    if bw_Bps <= 0:
                        continue

                    # Imposta una stima della banda minima e latenza massima della rete
                    MIN_BW_BPS = 100000 # Esempio: 100 KB/s
                    MAX_LATENCY = 0.1   # Esempio: 100 ms

                    # Calcola i massimi teorici per il Reference Payload
                    MAX_LINK_TIME = MAX_LATENCY + (REF_DATA_BYTES / MIN_BW_BPS)
                    MAX_LINK_ENERGY = current_node_obj.compute_routing_energy(REF_DATA_BYTES, bw_Bps, p_trasm)
                    
                    # Calcoliamo tempo ed energia per trasmettere il Reference Payload
                    trans_time = REF_DATA_BYTES / bw_Bps
                    link_time = latency + trans_time
                    link_energy = current_node_obj.compute_routing_energy(REF_DATA_BYTES, bw_Bps, p_trasm)

                    # Normalizzazione
                    norm_time = link_time / MAX_LINK_TIME if MAX_LINK_TIME > 0 else 0.0
                    norm_energy = link_energy / MAX_LINK_ENERGY if MAX_LINK_ENERGY > 0 else 0.0

                    # Funzione di costo combinata e adimensionale
                    link_cost = (w_R * norm_time) + (w_e * norm_energy)

                    new_cost = current_cost + link_cost
                    new_time = current_time + link_time
                    new_energy = current_energy + link_energy

                    # Se troviamo una via più economica, l'aggiorniamo
                    if new_cost < min_costs.get(neighbor.name, float('inf')):
                        min_costs[neighbor.name] = new_cost
                        heapq.heappush(pq, (new_cost, new_time, new_energy, neighbor.name, path + [neighbor.name]))

        # 3. Mappatura dello stato vitale dei nodi candidati (SEN)
        for node in globals.edge_servers:
            try:
                w_cpu_simpy = node.W_cpu()
            except Exception:
                w_cpu_simpy = getattr(node, "W_cpu", lambda: 0.0)()

            try:
                w_net_simpy = node.W_net()
            except Exception:
                w_net_simpy = getattr(node, "W_net", lambda: 0.0)()

            # ------------------------------
            # Calcolo del sunset time
            raw_sunset = getattr(node, "orbitalSunset", None)
            if raw_sunset is not None:
                safe_sunset = float(raw_sunset)
            else:
                safe_sunset = 0.0
            # ------------------------------

            # Creazione dello snapshot del nodo
            network_state["node_states"][node.name] = {
                "energy_residual": node.energy,
                "W_cpu_simpy": w_cpu_simpy,
                "W_net_simpy": w_net_simpy,      
                "C_sen": getattr(node, "C_sen", 1e9),
                "e_coeff": self.config.get("energy_coefficient", 5e-26),
                "sunset_time": safe_sunset
            }

        return network_state
        

    def _solve_ilp(self, network_state, tasks):
        """
        Modello Gerarchico PuLP Open-Source
        """
        # Creazione del problema di minimizzazione
        m = pulp.LpProblem("SECMotionModel_Centralized_ILP", pulp.LpMinimize)

        # Parametri
        primary_obj = self.config.get("centralized_primary_objective", "time")
        
        # Uplink payload fisso (2 KB)
        S_REQ_BYTES = 2048  
        p_net = self.config.get("Ptrasm", 1.0)
        
        R_set = tasks
        S_set = list(network_state["node_states"].keys())
        all_nodes = globals.global_access_point + globals.edge_servers
        node_dict = {n.name: n for n in all_nodes}

        # Definizione variabili
        x = pulp.LpVariable.dicts("x", ((r, i) for r in range(len(R_set)) for i in S_set), cat='Binary')
        
        y = pulp.LpVariable.dicts("y", (r for r in range(len(R_set))), cat='Binary')

        # --- VINCOLO 1: Assegnazione o Scarto ---
        for r_idx in range(len(R_set)):
            # La somma delle assegnazioni + la variabile di scarto deve fare 1
            m += pulp.lpSum(x[r_idx, i] for i in S_set) + y[r_idx] == 1, f"Assign_Or_Drop_{r_idx}"

        time_costs = {}
        energy_costs = {}
        
        node_energy_expressions = {k: [] for k in S_set}

        # 2. Costruzione parametri e vincoli fisici
        for r_idx, task in enumerate(R_set):
            task_data = task["data"]
            ap_origin = task["visible_aps"][0].name
            d_cpu = task_data.get('d_cpu', 0.0)
            deadline = task_data.get('deadline', 300.0)
            s_r_bytes = task_data.get('image_size', 0.0) * 1024 * 1024
            
            for i in S_set:
                route_info_up = network_state["routing_table"].get(ap_origin, {}).get(i)
                
                if not route_info_up:
                    m += x[r_idx, i] == 0, f"NoRoute_{r_idx}_{i}"
                    time_costs[r_idx, i] = 0
                    energy_costs[r_idx, i] = 0
                    continue

                path_up = route_info_up["path"]
                num_hops_up = len(path_up) - 1

                t_up = 0.0
                e_fwd_total = 0.0

                # --- UPLINK Tempo ed Energia
                for h in range(num_hops_up):
                    node_curr = node_dict[path_up[h]]
                    node_next = node_dict[path_up[h+1]]
                    lat = node_curr.get_latency(node_next) or 0.0
                    
                    bw_raw = node_curr.get_bandwidth(node_next) or 0.0
                    b_isl = (bw_raw / 8.0) * (1024 ** 2) if bw_raw > 0 else 0.0
                    
                    if b_isl > 0:
                        Wn = network_state["node_states"].get(node_curr.name, {}).get("W_net_simpy", 0.0)
                        d_net_hop = S_REQ_BYTES / b_isl
                        t_up += Wn + d_net_hop + lat

                        if hasattr(node_curr, 'compute_routing_energy'):
                            e_hop_fwd = node_curr.compute_routing_energy(S_REQ_BYTES, b_isl, p_net)
                        else:
                            e_hop_fwd = p_net * (S_REQ_BYTES / b_isl)
                            
                        e_fwd_total += e_hop_fwd
                        
                        if node_curr.name in S_set:
                            node_energy_expressions[node_curr.name].append(x[r_idx, i] * e_hop_fwd)

                # --- CPU LOCAL (Tempo ed Energia) ---
                node_obj = node_dict[i]
                c_sen_i = network_state["node_states"][i]["C_sen"]
                e_coeff_i = network_state["node_states"][i]["e_coeff"]

                # Tempo
                Wc = network_state["node_states"][i].get("W_cpu_simpy", 0.0)
                t_cpu_local = Wc + d_cpu

                # Energia
                if hasattr(node_obj, 'compute_execution_energy'):
                    e_cpu_local = node_obj.compute_execution_energy(d_cpu, c_sen_i, e=e_coeff_i)
                else:
                    e_cpu_local = d_cpu * e_coeff_i * (c_sen_i ** 3)
                    
                node_energy_expressions[i].append(x[r_idx, i] * e_cpu_local)

                # --- AGGREGAZIONE E VINCOLO DEADLINE ---
                time_costs[r_idx, i] = t_up + t_cpu_local
                energy_costs[r_idx, i] = e_fwd_total + e_cpu_local

                # Vincolo 2: Deadline Esatta
                R_ri_for_constraint = t_up + t_cpu_local 
                m += x[r_idx, i] * R_ri_for_constraint <= deadline, f"Deadline_{r_idx}_{i}"

        # Vincolo 3: Budget Energetico di Flotta Distribuito
        for k in S_set:
            budget_k = max(0.0, network_state["node_states"][k]["energy_residual"])
            if node_energy_expressions[k]:
                m += pulp.lpSum(node_energy_expressions[k]) <= budget_k, f"Energy_Limit_{k}"

        # --- Vincolo 4: Anti-Congestione / Load Balancing ---
        num_satellites = len(S_set)
        
        # Calcoliamo una "Fair Share"
        if num_satellites > 0:
            fair_share = len(R_set) // num_satellites
        else:
            fair_share = len(R_set)

        MAX_TASKS_PER_NODE = fair_share + 5 
            
        for i in S_set:
            m += pulp.lpSum(x[r_idx, i] for r_idx in range(len(R_set))) <= MAX_TASKS_PER_NODE, f"Max_Capacity_{i}"
        # -------------------------------------------------------------
        
        # --- PREPARAZIONE PENALITÀ SUNSET ---
        # Troviamo il massimo per normalizzare la penalità tra 0 e 1
        valid_sunsets = [network_state["node_states"][k].get("sunset_time", 0.0) for k in S_set]
        max_sunset = max(valid_sunsets + [1.0])
        
        sunset_penalties = {}
        for i in S_set:
            s_time = network_state["node_states"][i].get("sunset_time", 0.0)
            
            # Se s_time è 0.0 (satellite sotto l'orizzonte), la penalità sarà 1.0 (Massima)
            sunset_penalties[i] = 1.0 - (s_time / max_sunset) if max_sunset > 0 else 0.0
        # -----------------------------------------------------

        # 3. Ottimizzazione Gerarchica
        PENALTY_VALUE = 1000000.0  # Valore gigantesco per forzare il salvataggio dei task
        
        obj_time = pulp.lpSum(x[r_idx, i] * time_costs[r_idx, i] for r_idx in range(len(R_set)) for i in S_set) + \
                   pulp.lpSum(y[r_idx] * PENALTY_VALUE for r_idx in range(len(R_set)))
                   
        obj_energy = pulp.lpSum(x[r_idx, i] * energy_costs[r_idx, i] for r_idx in range(len(R_set)) for i in S_set) + \
                     pulp.lpSum(y[r_idx] * PENALTY_VALUE for r_idx in range(len(R_set)))

        # --- COMPONENTE SUNSET ---
        obj_sunset = pulp.lpSum(x[r_idx, i] * sunset_penalties[i] for r_idx in range(len(R_set)) for i in S_set)

        WEIGHT_PRIMARY = 10.0
        WEIGHT_SECONDARY = 1.0
        WEIGHT_SUNSET = 5.0

        if primary_obj == "time":
            m += WEIGHT_PRIMARY * obj_time + WEIGHT_SECONDARY * obj_energy + WEIGHT_SUNSET * obj_sunset, "Total_Objective"
        else:
            m += WEIGHT_PRIMARY * obj_energy + WEIGHT_SECONDARY * obj_time + WEIGHT_SUNSET * obj_sunset, "Total_Objective"

        # 4. Esecuzione tramite HiGHS (Integrato in PuLP)
        solver = pulp.getSolver('HiGHS', msg=False)
        m.solve(solver)
        
        status = pulp.LpStatus[m.status]
        
        # -------------------------------------------------------
        # Calcoliamo esattamente quanta energia e quanti slot sono stati rubati dai task accettati
        assigned_energy_per_node = {i: 0.0 for i in S_set}
        assigned_tasks_per_node = {i: 0 for i in S_set}
        
        if status in ('Optimal', 'Suboptimal'):
            for r_idx in range(len(R_set)):
                if pulp.value(y[r_idx]) is not None and pulp.value(y[r_idx]) < 0.5: # Task SALVO
                    for i in S_set:
                        if pulp.value(x[r_idx, i]) is not None and pulp.value(x[r_idx, i]) > 0.5:
                            assigned_energy_per_node[i] += energy_costs.get((r_idx, i), 0.0)
                            assigned_tasks_per_node[i] += 1
        # -------------------------------------------------------

        # Estrazione Assegnamenti e Diagnostica
        assignments = []
        if status in ('Optimal', 'Suboptimal'):
            for r_idx, task in enumerate(R_set):
                
                # --- TASK SCARTATO ---
                if pulp.value(y[r_idx]) and pulp.value(y[r_idx]) > 0.5:
                    ap_origin = task["visible_aps"][0].name
                    deadline = task["data"].get('deadline', 300.0)
                    specific_reason = "Unknown"
                    
                    reachable_sens = [i for i in S_set if network_state["routing_table"].get(ap_origin, {}).get(i)]
                    
                    if not reachable_sens:
                        specific_reason = "No_Route"
                    else:
                        can_meet_deadline = False
                        can_meet_sunset = False
                        has_energy = False
                        has_capacity = False
                        
                        for i in reachable_sens:
                            R_ri = time_costs.get((r_idx, i), 0)
                            E_ri = energy_costs.get((r_idx, i), 0)
                            s_time_i = network_state["node_states"][i].get("sunset_time", 0)
                            
                            if 0 < R_ri <= deadline: can_meet_deadline = True
                            if 0 < R_ri <= s_time_i: can_meet_sunset = True
                            
                            # Calcoliamo l'energia REALE rimasta dopo che i task precedenti hanno banchettato
                            actual_energy_left = network_state["node_states"][i]["energy_residual"] - assigned_energy_per_node[i]
                            if actual_energy_left >= E_ri: has_energy = True
                            
                            # Calcoliamo se c'è spazio rispetto al vincolo 4
                            limit = locals().get('MAX_TASKS_PER_NODE', 999999)
                            if assigned_tasks_per_node[i] < limit: has_capacity = True
                        
                        # La sentenza finale
                        if not can_meet_deadline:
                            specific_reason = "Deadline_Violation"
                        elif not can_meet_sunset:
                            specific_reason = "Sunset_Violation"
                        elif not has_energy:
                            specific_reason = "Energy_Exhaustion"
                        elif not has_capacity:
                            specific_reason = "Capacity_Limit_Reached"


                    print(f"[{self.env.now:.3f}] Orchestrator: Task {task['task_id']} scartato dall'ILP. Motivo: {specific_reason}")

                    assignments.append({
                        "task_id": task["task_id"],
                        "data": task["data"],
                        "assigned_sen": None,
                        "routing_path_up": [],
                        "routing_path_down": [],
                        "status": f"Scartato_{specific_reason}"
                    })
                    continue

                # --- TASK SALVATO ---
                assigned_node = None
                for i in S_set:
                    if pulp.value(x[r_idx, i]) and pulp.value(x[r_idx, i]) > 0.5:
                        assigned_node = i
                        break
                
                if assigned_node:
                    ap_origin = task["visible_aps"][0].name
                    path_up = network_state["routing_table"][ap_origin][assigned_node]["path"]
                    path_down = [assigned_node, ap_origin]

                    assignments.append({
                        "task_id": task["task_id"],
                        "data": task["data"],
                        "assigned_sen": assigned_node,
                        "routing_path_up": path_up,
                        "routing_path_down": path_down,
                        "status": "Assigned"
                    })
        else:
            print(f"[{self.env.now:.2f}] [ILP Centralized] Batch Infeasible (Modello matematico irrisolvibile). Status: {status}")
            for task in R_set:
                assignments.append({
                    "task_id": task["task_id"], "data": task["data"],
                    "assigned_sen": None, "routing_path_up": [], "routing_path_down": [],
                    "status": "Infeasible"
                })

        return assignments

    def _dispatch_tasks(self, assignments):

        all_nodes = {n.name: n for n in (globals.global_access_point + globals.edge_servers)}

        for assignment in assignments:
            task_id = assignment["task_id"]
            data = assignment["data"]
            status = assignment["status"]
            dispatch_time = self.env.now

            if status != "Assigned":
                if "No_Route" in status or "Infeasible" in status:
                    arrival = data.get("arrival_time", dispatch_time)
                    print(f"[{dispatch_time:.3f}] Orchestrator: ILP fallito ({status}) per Task {task_id}. REINSERIMENTO incondizionato nel buffer!")
                    
                    self.task_buffer.append({
                        "task_id": task_id,
                        "data": data,
                        "visible_aps": globals.global_access_point,
                        "arrival_time": arrival 
                    })
                    
                    if len(self.task_buffer) >= self.batch_size and not self.batch_ready_event.triggered:
                        self.batch_ready_event.succeed()
                        
                    continue

                # --- PIANO B: Rifiuto definitivo (es. Batteria insufficiente calcolata dall'ILP) ---
                ap = globals.global_access_point[0]
                print(f"[{dispatch_time:.3f}] Orchestrator: Task {task_id} SCARTATO ({status}).")
                ap.record_rejected_task(
                    task_id, data["type"], dispatch_time, data["image_size"], f"ILP_{status}", data.get("d_cpu", 0)
                )
                continue

            # --- CASO 2: TASK ASSEGNATO, INIZIO VIAGGIO ---
            self.env.process(self._route_and_execute_task(assignment, all_nodes, dispatch_time))
                
    def _route_and_execute_task(self, assignment, all_nodes, dispatch_time):
            task_id = assignment["task_id"]
            data = assignment["data"]
            sen_name = assignment["assigned_sen"]
            sen_obj = all_nodes.get(sen_name)
            path_up = assignment.get("routing_path_up", [])

            ap_origin = path_up[0] if path_up else globals.global_access_point[0].name

            # --- 1. CREAZIONE TASK TEMPORANEO DI ROUTING ---
            routing_task = Task(
                task_id=task_id,
                current_node=ap_origin,
                dest_node=sen_name,
                routingInitTime=dispatch_time,
                task_type=data["type"],
                image_size=data["image_size"]
            )
            routing_task.weight = data["image_size"]
            routing_task.visited.add(ap_origin) 
            
            start_node = all_nodes.get(ap_origin)
            if start_node and routing_task not in start_node.tasks:
                start_node.tasks.append(routing_task)

            # --- 2. LOOP DINAMICO (Navigazione ibrida: ILP -> GREEDY) ---
            current_node_name = ap_origin
            target_dest_name = sen_name
            path_index = 0
            is_greedy = False 
        
            while current_node_name != target_dest_name:
                current_node_obj = all_nodes.get(current_node_name)
                
                if not is_greedy:
                    # ==========================================
                    # FASE A: NAVIGAZIONE SU ROTTA PIANIFICATA (ILP)
                    # ==========================================
                    next_planned = path_up[path_index + 1] if path_index < len(path_up) - 1 else None
                    next_planned_obj = all_nodes.get(next_planned) if next_planned else None

                    if next_planned_obj and current_node_obj.get_bandwidth(next_planned_obj) > 0:
                        # Link vivo: seguiamo il piano dell'Orchestratore
                        yield self.env.process(
                            utils.sendTask(self.env, routing_task, current_node_obj, next_planned_obj, "ILP_Centralized")
                        )
                        path_index += 1
                        routing_task.visited.add(next_planned)
                    else:
                        # LINK ROTTO: Fallback innescato!
                        print(f"[{self.env.now:.3f}] Orchestrator: Link interrotto al nodo {current_node_name} (Task {task_id}). Attivazione Fallback GREEDY!")
                        is_greedy = True
                        
                if is_greedy:
                    # ==========================================
                    # FASE B: NAVIGAZIONE D'EMERGENZA (GREEDY)
                    # ==========================================
                    target_dest_obj = all_nodes.get(target_dest_name)
                    dest_pos = target_dest_obj.getPositionVector(globals.ist_in_conf)
                    ranker_neighbors = []
                    neighbors_list = getattr(current_node_obj, 'neighbors', current_node_obj.get_neighbors())

                    for server in neighbors_list:
                        if current_node_obj.get_bandwidth(server) > 0:
                            neighbor_distance = get_pos_proximity(dest_pos, server.getPositionVector(globals.ist_in_conf))
                            is_ap = getattr(server, 'is_acc_point', False)
                            ranker_neighbors.append((server, neighbor_distance, is_ap))

                    ranker_neighbors.sort(key=lambda x: (not x[2], x[1]))

                    best_server = None
                    for neighbor_tuple in ranker_neighbors:
                        # Prevenzione dei loop ping-pong tra due satelliti
                        if neighbor_tuple[0].name not in routing_task.visited:
                            best_server = neighbor_tuple[0]
                            break

                    if best_server:
                        yield self.env.process(
                            utils.sendTask(self.env, routing_task, current_node_obj, best_server, 'GREEDY_FALLBACK')
                        )
                        routing_task.visited.add(best_server.name)
                    else:
                        print(f"[{self.env.now:.3f}] Orchestrator: Fallback GREEDY fallito (vicolo cieco) al nodo {current_node_name}. Task {task_id} droppato.")
                        routing_task.routingEndTime = self.env.now
                        routing_task.label = "DROPPED_GREEDY_DEADEND"
                        globals.gbl_tasks.append(routing_task)
                        return

                # ==========================================
                # FASE C: CONTROLLO SICUREZZA COMUNE
                # ==========================================
                if getattr(routing_task, 'label', '') == 'TTL_EXPIRED':
                    print(f"[{self.env.now:.3f}] Orchestrator: Task {task_id} droppato per TTL durante il routing.")
                    globals.gbl_tasks.append(routing_task)
                    return

                current_node_name = routing_task.current_node

            # --- 3. ARRIVO ALLA DESTINAZIONE FINALE ---
            transfer_time_up = self.env.now - dispatch_time
            final_hops = routing_task.hop
            init_time = routing_task.routingInitTime
            end_time = self.env.now
            algos = routing_task.algorithms_used

            print(f"[{self.env.now:.3f}] Orchestrator: Task {task_id} arrivato a {sen_name} in {transfer_time_up:.3f}s (Hops: {final_hops})")

            # --- 4. DATASET STATS ---
            globals.initial_server_counter[sen_name] = globals.initial_server_counter.get(sen_name, 0) + 1
            globals.gbl_task_hops[str(task_id)] = final_hops
            globals.gbl_task_final_hops[str(task_id)] = final_hops
            globals.gbl_generated_tasks_data.append({
                "task_id": task_id, "arrival_time": dispatch_time, "type": data["type"],
                "ram": data.get("required_ram", 0), "disk": data.get("required_disk", 0),
                "image_size": data["image_size"], "exec_time": data["d_cpu"],
                "transfer_time": transfer_time_up, "performed_transfers": final_hops,
                "final_hops": final_hops, "execution_server": sen_name
            })

            # --- 5. ESECUZIONE SIMULAZIONE CPU ---
            yield self.env.process(
                ILP_simulation.TaskAssignment_ILP(
                    env=self.env, selected_server=sen_obj, task_id=task_id, image_size=data["image_size"],
                    arrival_time_system=data.get("arrival_time", dispatch_time), num_hops=final_hops, 
                    transfer_time=transfer_time_up, task_type=data["type"], d_cpu=data["d_cpu"], D_r=data["deadline"],
                    net_bw_override_Bps=None, result_sink={}, allow_retry=False,              
                    routing_already_charged=True, routing_energy_from=None, transfer_already_simulated=True
                )
            )

            # --- 6. SINCRONIZZAZIONE METRICHE POST-ESECUZIONE ---
            final_task = next((t for t in globals.gbl_tasks if t.id == task_id), None)
            if final_task:
                final_task.hop = final_hops
                final_task.routingInitTime = init_time
                final_task.routingEndTime = end_time
                final_task.algorithms_used = algos
            else:
                routing_task.routingEndTime = end_time
                routing_task.label = "REJECTED_POST_ROUTING"
                globals.gbl_tasks.append(routing_task)