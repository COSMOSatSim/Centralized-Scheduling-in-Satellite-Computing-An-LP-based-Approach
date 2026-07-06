import heapq
import simpy
import globals
import pulp
import ILP_simulation

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
        print(f"[{self.env.now:.3f}] Orchestrator: ILP completato. Assegnazioni: {assignments}")

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

            # Creazione dello snapshot del nodo
            network_state["node_states"][node.name] = {
                "energy_residual": node.energy - getattr(node, "energy_reserved", 0.0),
                "W_cpu_simpy": w_cpu_simpy,
                "W_net_simpy": w_net_simpy,      
                "C_sen": getattr(node, "C_sen", 1e9),
                "e_coeff": self.config.get("energy_coefficient", 5e-26)
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

        # 1. Variabili di decisione binarie e penalità
        x = {}
        for r_idx, task in enumerate(R_set):
            for i in S_set:
                x[r_idx, i] = pulp.LpVariable(name=f"x_{r_idx}_{i}", cat='Binary')

        y = {}
        for r_idx in range(len(R_set)):
            y[r_idx] = pulp.LpVariable(name=f"y_unassigned_{r_idx}", cat='Binary')

        # Vincolo 1: Ammissibilità Decisionale
        for r_idx in range(len(R_set)):
            m += pulp.lpSum(x[r_idx, i] for i in S_set) + y[r_idx] == 1, f"Assignment_{r_idx}"

        time_costs = {}
        energy_costs = {}
        
        # In PuLP raccogliamo le espressioni in liste prima di sommarle
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

                # --- DOWNLINK 
                BANDWIDTH_TO_GU_BPS = self.config.get("Bandwidth_to_GU_Bps", 100000)
                
                # Tempo
                t_down = s_r_bytes / BANDWIDTH_TO_GU_BPS

                # Energia
                if hasattr(node_obj, 'compute_routing_energy'):
                    e_down_simpy = node_obj.compute_routing_energy(s_r_bytes, BANDWIDTH_TO_GU_BPS, p_net)
                else:
                    e_down_simpy = p_net * (s_r_bytes / BANDWIDTH_TO_GU_BPS)
                    
                node_energy_expressions[i].append(x[r_idx, i] * e_down_simpy)

                # --- AGGREGAZIONE E VINCOLO DEADLINE ---
                time_costs[r_idx, i] = t_up + t_cpu_local + t_down
                energy_costs[r_idx, i] = e_fwd_total + e_cpu_local + e_down_simpy

                # Vincolo 2: Deadline Esatta
                R_ri_for_constraint = t_up + t_cpu_local 
                m += x[r_idx, i] * R_ri_for_constraint <= deadline, f"Deadline_{r_idx}_{i}"

        # Vincolo 3: Budget Energetico di Flotta Distribuito
        for k in S_set:
            # FIX 1: Impediamo che il budget diventi matematicamente negativo
            budget_k = max(0.0, network_state["node_states"][k]["energy_residual"])
            if node_energy_expressions[k]:
                m += pulp.lpSum(node_energy_expressions[k]) <= budget_k, f"Energy_Limit_{k}"

        # 3. Ottimizzazione Gerarchica (Somma Pesata Stabilizzata)
        # FIX 2: Abbassiamo la penalità per evitare il malcondizionamento numerico in HiGHS
        PENALTY_VALUE = 10000.0 
        
        obj_time = pulp.lpSum(x[r_idx, i] * time_costs[r_idx, i] for r_idx in range(len(R_set)) for i in S_set) + \
                   pulp.lpSum(y[r_idx] * PENALTY_VALUE for r_idx in range(len(R_set)))
                   
        obj_energy = pulp.lpSum(x[r_idx, i] * energy_costs[r_idx, i] for r_idx in range(len(R_set)) for i in S_set) + \
                     pulp.lpSum(y[r_idx] * PENALTY_VALUE for r_idx in range(len(R_set)))

        # FIX 3: Pesi più bilanciati
        WEIGHT_PRIMARY = 10.0
        WEIGHT_SECONDARY = 1.0

        if primary_obj == "time":
            m += WEIGHT_PRIMARY * obj_time + WEIGHT_SECONDARY * obj_energy, "Total_Objective"
        else:
            m += WEIGHT_PRIMARY * obj_energy + WEIGHT_SECONDARY * obj_time, "Total_Objective"

        # 4. Esecuzione tramite HiGHS (Integrato in PuLP)
        solver = pulp.getSolver('HiGHS', msg=False)
        m.solve(solver)
        
        status = pulp.LpStatus[m.status]

        # 5. Estrazione e Mappatura Percorsi Semplificata
        assignments = []
        if status in ('Optimal', 'Suboptimal'):
            for r_idx, task in enumerate(R_set):
                assigned_node = None
                
                # Cerchiamo se il solver ha scelto un nodo (Valore binario > 0.5)
                for i in S_set:
                    if pulp.value(x[r_idx, i]) and pulp.value(x[r_idx, i]) > 0.5:
                        assigned_node = i
                        break
                
                if assigned_node:
                    # --- TASK ASSEGNATO CON SUCCESSO ---
                    ap_origin = task["visible_aps"][0].name
                    
                    # Percorso in andata
                    path_up = network_state["routing_table"][ap_origin][assigned_node]["path"]
                    
                    # Percorso di ritorno
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
                    # --- TASK RIFIUTATO: DIAGNOSTICA ---
                    ap_origin = task["visible_aps"][0].name
                    deadline = task["data"].get('deadline', 300.0)
                    specific_reason = "Unknown"
                    
                    reachable_sens = [i for i in S_set if network_state["routing_table"].get(ap_origin, {}).get(i)]
                    
                    if not reachable_sens:
                        specific_reason = "No_Route"
                    else:
                        can_meet_deadline = False
                        for i in reachable_sens:
                            R_ri = time_costs.get((r_idx, i), 0)
                            if R_ri > 0 and R_ri <= deadline:
                                can_meet_deadline = True
                                break
                        
                        if not can_meet_deadline:
                            specific_reason = "Deadline_Violation"
                        else:
                            specific_reason = "Energy_Exhaustion"

                    assignments.append({
                        "task_id": task["task_id"],
                        "data": task["data"],
                        "assigned_sen": None,
                        "routing_path_up": [],
                        "routing_path_down": [],
                        "status": f"Rejected_{specific_reason}"
                    })
        else:
            print(f"[{self.env.now:.2f}] [ILP Centralized] Batch Infeasible (Modello matematico irrisolvibile). Status: {status}")
            for task in R_set:
                assignments.append({
                    "task_id": task["task_id"],
                    "data": task["data"],
                    "assigned_sen": None,
                    "routing_path_up": [],
                    "routing_path_down": [],
                    "status": "Infeasible"
                })

        return assignments

    def _dispatch_tasks(self, assignments):
            """
            Traduce le decisioni dell'ILP in eventi SimPy fisici.
            """

            # Raccogliamo tutti i nodi per accedere ai loro oggetti fisici
            all_nodes = {n.name: n for n in (globals.global_access_point + globals.edge_servers)}
            p_net = self.config.get("Ptrasm", 1.0)
            s_req_bytes = 2048  # Payload fisso di andata (2 KB)

            for assignment in assignments:
                task_id = assignment["task_id"]
                data = assignment["data"]
                status = assignment["status"]

                dispatch_time = self.env.now

                # --- CASO 1: TASK RIFIUTATO O INFEASIBLE ---
                if status != "Assigned":
                    ap = globals.global_access_point[0]
                    print(f"[{dispatch_time:.3f}] Orchestrator: Task {task_id} SCARTATO ({status}).")
                    ap.record_rejected_task(
                        task_id, data["type"], dispatch_time, data["image_size"], f"ILP_{status}", data["d_cpu"]
                    )
                    continue

                # --- CASO 2: TASK ASSEGNATO ---
                sen_name = assignment["assigned_sen"]
                sen_obj = all_nodes.get(sen_name)
                path_up = assignment.get("routing_path_up", [])
                
                transfer_time_up = 0.0

                # 1. Pagamento Immediato dell'Energia di Uplink 
                if len(path_up) > 1:
                    for h in range(len(path_up) - 1):
                        node_curr = all_nodes.get(path_up[h])
                        node_next = all_nodes.get(path_up[h+1])
                        
                        if node_curr and node_next:
                            bw = node_curr.get_bandwidth(node_next) or 0.0
                            b_isl = bw * (1024**2)
                            lat = node_curr.get_latency(node_next) or 0.0
                            
                            if b_isl > 0:
                                if hasattr(node_curr, 'compute_routing_energy'):
                                    e_hop = node_curr.compute_routing_energy(s_req_bytes, b_isl, p_net)
                                else:
                                    e_hop = p_net * (s_req_bytes / b_isl)
                                    
                                node_curr.energy -= e_hop
                                transfer_time_up += (s_req_bytes / b_isl) + lat

                # 2. Pagamento Immediato (Prenotazione) dell'Energia di Downlink
                s_r_bytes = data["image_size"] * (1024**2)
                BANDWIDTH_TO_GU_BPS = self.config.get("Bandwidth_to_GU_Bps", 100000)
                
                if sen_obj:
                    if hasattr(sen_obj, 'compute_routing_energy'):
                        e_down = sen_obj.compute_routing_energy(s_r_bytes, BANDWIDTH_TO_GU_BPS, p_net)
                    else:
                        e_down = p_net * (s_r_bytes / BANDWIDTH_TO_GU_BPS)
                    
                    sen_obj.energy -= e_down

                # 3. Aggiornamento Contatori e Dataset Globali per i file CSV
                num_hops = max(0, len(path_up) - 1)
                globals.initial_server_counter[sen_name] = globals.initial_server_counter.get(sen_name, 0) + 1
                globals.gbl_task_hops[str(task_id)] = num_hops
                globals.gbl_task_final_hops[str(task_id)] = num_hops

                globals.gbl_generated_tasks_data.append({
                    "task_id": task_id,
                    "arrival_time": dispatch_time,
                    "type": data["type"],
                    "ram": data["required_ram"],
                    "disk": data["required_disk"],
                    "image_size": data["image_size"],
                    "exec_time": data["d_cpu"],
                    "transfer_time": transfer_time_up,
                    "performed_transfers": num_hops,
                    "final_hops": num_hops,
                    "execution_server": sen_name
                })

                print(f"[{dispatch_time:.3f}] Orchestrator: DISPATCH Task {task_id} -> {sen_name} (Hops: {num_hops})")

                # 4. Iniezione del task in SimPy
                self.env.process(
                    ILP_simulation.TaskAssignment_ILP(
                        env=self.env,
                        selected_server=sen_obj,
                        task_id=task_id,
                        image_size=data["image_size"],
                        arrival_time_system=data.get("arrival_time", dispatch_time), 
                        num_hops=num_hops, 
                        transfer_time=transfer_time_up,
                        task_type=data["type"],
                        d_cpu=data["d_cpu"],
                        D_r=data["deadline"],
                        net_bw_override_Bps=None,
                        result_sink={},
                        allow_retry=False,              
                        routing_already_charged=True, 
                        routing_energy_from=None
                    )
                )