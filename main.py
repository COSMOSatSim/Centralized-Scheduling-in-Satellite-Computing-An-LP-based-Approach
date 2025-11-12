import csv
import json5
import os
import sys
import simpy
import json
from EdgeServer import build_task_csv_path
import simulation
from Task import generate_Tasks_Status, convert_task_list_in_dict
from simulation import generate_tasks
from topology import loadConfiguration, periodic_recall_Topology_monitor, create_topology_dome, genConfigs, \
    updateTaskValue, string_to_skyfield_time
from user_based_topology import get_current_time, getObserverObj
from SaveCurrentSATOnFile import saveTLEOnFile
from routing_Manager import periodic_recall_Routing_monitor
from Observer import Observer
from simulation_OGM import process_OGM_enviroment_simulation, remove_first_30_configurations
import globals
import time

simulation_dataset = []


# Aggiungi il nuovo processo di raccolta dati
def data_collector(env, interval, start_time, end_time):
    """
    Processo per la raccolta periodica dei dati dello stato della rete
    in un intervallo di tempo specificato.
    """
    global simulation_dataset

    # Attendi fino all'inizio dell'intervallo di raccolta
    yield env.timeout(start_time)

    while env.now <= end_time:
        # Crea un 'snapshot' dello stato attuale
        snapshot = {
            "time": env.now,
            "satellites": []
        }

        # Scansiona tutti i satelliti e raccogli i dati
        for sat_obj in globals.edge_servers:
            if sat_obj:
                state = sat_obj.export_state(env)
                snapshot["satellites"].append(state)

        # Aggiungi lo snapshot alla lista globale
        simulation_dataset.append(snapshot)

        # Attendi l'intervallo di tempo specificato prima della prossima raccolta
        yield env.timeout(interval)


if __name__ == "__main__":
    # Imposta seme e ambiente
    start_time_simulation_real = time.time()
    env = simpy.Environment()
    config, resolution_config = globals.config, globals.resolution_config

    MaxTry = config.get("max_try", 10)

    # 1) Costruzione configurazioni
    if config.get("Build_Configurations", False):

        tle_data = saveTLEOnFile()
        config_interval = config["Interval_between_Configurations_in_seconds"]
        tot_config = int((config["simulation_duration"] + config["adding_time"]) / config_interval)

        configurations = genConfigs(
            get_current_time(),
            config_interval,
            tot_config,
            tle_data
        )

        T_min, T_max, T_avg = updateTaskValue(configurations)
        config["Build_Configurations"] = False
        config["CPU_timeout"]["min"] = T_min
        config["CPU_timeout"]["max"] = T_max
        config["CPU_timeout"]["mean"] = T_avg + 2.0

        with open('config.json5', 'w') as wf:
            json5.dump(config, wf, indent=2)

        if config["redistribuite_OGM"]:
            process_OGM_enviroment_simulation(configurations)
            remove_first_30_configurations()

        sys.exit("File of configurations created")

    # 2) Caricamento o creazione topologia
    if config.get("Load_Configuration", False):
        print("Carico le configurazioni dal file...")
        globals.edge_servers, globals.global_access_point = loadConfiguration(env, globals.data_configurations,
                                                                              globals.OGMs_tables,
                                                                              globals.positions_vectors)
        env.process(periodic_recall_Topology_monitor(env, globals.data_configurations, globals.OGMs_tables,
                                                     globals.positions_vectors))
    else:
        print("Creo la topologia DOMEv2...")
        globals.edge_servers = create_topology_dome(env)

    globals.observer = Observer(env, getObserverObj())  # Singleton Observer
    env.process(periodic_recall_Routing_monitor(env))

    if not globals.data_configurations:
        sys.exit("Errore: il file delle configurazioni è vuoto.")
    skyfield_time = string_to_skyfield_time(globals.data_configurations["t0"])

    globals.initial_server_counter = {
        server.name: 0 for server in globals.edge_servers}
    globals.different_server_counter = {
        server.name: 0 for server in globals.edge_servers}
    globals.other_server_counter = {
        server.name: 0 for server in globals.edge_servers}

    # 3 batch in rete
    batch_task_id = 1000  # base id per batch
    for server in globals.edge_servers:
        n_batches = globals.rnd.randint(0, 3)  # uno o più batch per server (range 0..3)
        for _ in range(n_batches):
            batch_task_id += 1000

            # requisiti (ram/disk) se vuoi tenerli
            required_ram = globals.rnd.randint(config["required_ram"]["min"], config["required_ram"]["max"])
            required_disk = globals.rnd.randint(config["required_disk"]["min"], config["required_disk"]["max"])

            # scegli image_size in base alle regole BATCH del tuo resolution_config
            ranges = resolution_config["size_ranges_MB"]
            batch_params = ranges["BATCH_TASK"]
            r = globals.rnd.random()
            if r < batch_params["gamma_H_weight"]:
                image_size = globals.rnd.uniform(*batch_params["H_range"])
            else:
                image_size = globals.rnd.uniform(*batch_params["VH_range"])

            # d_cpu = 0 per batch
            d_cpu_batch = 0.0

            # stima d_net e deadline coerente con LaTeX: D_r = (1+delta_D)*(d_cpu + d_net)
            bw_Bps, data_bytes = simulation.network_metrics(image_size)
            d_net_batch = data_bytes / bw_Bps if bw_Bps > 0 else float('inf')
            delta_D = config.get("delta_D", 0.2)
            deadline_batch = (1.0 + delta_D) * (d_cpu_batch + d_net_batch)

            # avvia il processo che mette il batch davvero nella net queue del server
            env.process(simulation.enqueue_batch_in_net(
                env,
                server,
                batch_task_id,
                image_size,
                env.now,
                deadline_batch
            ))

    print("Batch tasks for all servers scheduled (0..3 per server).")

    # 4) Avvia la generazione dei task
    env.process(generate_tasks(
        env,
        globals.initial_server_counter,
        globals.different_server_counter,
        globals.other_server_counter
    ))

    # 5) Preparazione dei nomi di cartella e file
    mode_name             = config.get("mode_name", "UnknownMode").replace(" ", "_")
    ap                    = config.get("access_point", 0)
    seed_val              = config["seed"]
    gen_dist              = config["generate_tasks"]["distribution"]
    req_dist              = config["request_distribution"]["distribution"]
    if req_dist == "0_0_0":
        req_dist = "RR"
    atime                 = config["arrival_time_exponential"]
    cpu_mean              = config["CPU_timeout"]["gen"]["mean"]
    solver                = config["SearchNode"]
    ap_dir_bidir          = config["AP_routing_bidirectional"]      # (Booleano) AP_Routing 

    # BETA, ALPHA, GAMMA
    beta = resolution_config["beta_probabilities"]
    bg, bcpui,bcpudi = beta["Generic_Service"], beta["CPU_Intensive"], beta["CPU_and_Data_Intensive"]
    alpha = resolution_config["size_ranges_MB"]["CPU_DATA_INTENSIVE"]
    am, ah, avh = alpha["alpha_M_weight"], alpha["alpha_H_weight"], alpha["alpha_VH_weight"]
    gamma = resolution_config["size_ranges_MB"]["BATCH_TASK"]
    gh, gvh = gamma["gamma_H_weight"], gamma["gamma_VH_weight"]
    img_res_dir = f"IMG_RES_bg_{bg}_bcpui_{bcpui}_bcpudi_{bcpudi}_am_{am}ah_{ah}_avh_{avh}_gh_{gh}_gvh_{gvh}"

    # Cartella base: include modalità, AP e seed
    base_dir = f"{solver}_{req_dist}-sim_SystemAP{ap}/{img_res_dir}/Routing_bidirectional_{ap_dir_bidir}/seed_{seed_val}"
    os.makedirs(base_dir, exist_ok=True)

    # File CSV e log con nomenclatura completa
    csv_task = (
        f"{base_dir}/results_"
        f"{gen_dist}_REQ-{req_dist}_"
        f"AT_{atime}_CPU_{cpu_mean}.csv"
    )
    csv_mig = (
        f"{base_dir}/migration_"
        f"{gen_dist}_REQ-{req_dist}_"
        f"AT_{atime}_CPU_{cpu_mean}.csv"
    )
    csv_routing_task = build_task_csv_path(base_dir, atime, cpu_mean)

    # Salvo il nome del CSV nel config per eventuali moduli esterni
    config["csv_name"] = {"name": csv_task}
    with open('config.json5', 'w') as wf:
        json5.dump(config, wf, indent=2)

    print(f"--- Avvio simulazione ---")
    print(f"Modalità: {mode_name}")
    print(f"Cartella: {base_dir}")
    print(f"CSV tasks: {csv_task}")
    print(f"CSV migrazioni: {csv_mig}")

    # esempio: ogni 2s, dal secondo 100 al 200
    env.process(data_collector(env, interval=2, start_time=100, end_time=200))
    
    # NUOVO
    # CSV per il buffer batching (solo id, tempo ingresso, tempo rimanente deadline)
    csv_batch_buffer = f"{base_dir}/BATCH_BUFFER/buffer_log.csv"
    os.makedirs(os.path.dirname(csv_batch_buffer), exist_ok=True)

    # Avvio writer periodico del buffer se abilitato in config
    batching_cfg = config.get("batching", {})
    if batching_cfg.get("enabled", False):
        interval_s = float(batching_cfg.get("interval_s", 0.1))
        decisions_csv = f"{base_dir}/BATCH_BUFFER/BATCH_DECISIONS.csv"
        simulation.start_batch_buffer(env, csv_batch_buffer, interval_s, decisions_csv_path=decisions_csv)
        print(f"[BATCHING] Abilitato: interval={interval_s}s -> {csv_batch_buffer}")
    else:
        print("[BATCHING] Disabilitato da config.") 
    
    

    # 6) Esecuzione simulazione
    env.run(config['simulation_duration'])

    # Definisci il nome del file di output
    output_folder = "Generated_datasets"

    if config.get("save_generated_tasks_dataset", True) and globals.gbl_generated_tasks_data:

        os.makedirs(output_folder, exist_ok=True)
        # Genera un nome di file basato su seed e durata (per unicità)
        file_name = f"generated_tasks_seed{config['seed']}_dur{config['simulation_duration']}.json5"
        output_path = os.path.join(output_folder, file_name)

        print(f"\nSalvataggio del dataset generato in: {output_path}")

        try:
            with open(output_path, 'w') as f:
                json5.dump(globals.gbl_generated_tasks_data, f, indent=4)
            print("Salvataggio completato con successo.")
        except Exception as e:
            print(f"ERRORE nel salvataggio del dataset: {e}")

    # Salva il dataset alla fine della simulazione
    ENABLE_MONITORING = config.get("enable_queue_monitoring", False)
    if ENABLE_MONITORING:
        output_path_monitor = os.path.join(output_folder, "simulation_dataset.json")
        with open(output_path_monitor, "w") as f:
            json.dump(simulation_dataset, f, indent=4)
        print("\nDataset dello stato della simulazione salvato in 'simulation_dataset.json'")

    # Stampa il riassunto dei task usando la funzione dell'Observer
    globals.observer.print_task_summary()
    print("-" * 10)
    generate_Tasks_Status(csv_routing_task, base_dir)
    task_dict = convert_task_list_in_dict(globals.gbl_tasks)

    # ---------------------------------------------------------------------
    # 7) Scrittura risultati su CSV (Task completati/rifiutati/residui)
    # ---------------------------------------------------------------------

    # Raccogli tutti i server in un'unica lista per l'iterazione
    all_servers_by_name = {}
    for s in (globals.edge_servers or []) + (globals.global_access_point or []):
        if s is None:
            continue
        all_servers_by_name[s.name] = s
    all_servers = list(all_servers_by_name.values())

    with open(csv_task, mode='w', newline='') as f_out:
        writer = csv.writer(f_out)
        # Intestazione aggiornata a 27 colonne
        writer.writerow([
            "Task ID", "Task Type", "Status", "Arrival Time (System)",
            "Arrival Time (Queue)", "Start Time", "End Time", "Execution time",
            "Service Time", "Time in system", "Time in queue", "Server Name", "Num Hops",
            "Num Hops Routing",  # <-- Nuova colonna
            "Queue length", "transfer_time", "Image_Size_MB", "DeadLine Exceded", "Exec_after_set",
            "Energy_CPU [J]", "Energy_NET [J]", "Energy_TOTAL [J]", "Remaining_energy [J]", "Remaining_energy [%]",
            "Rejection Reason",
            "Routing Init Time", # <-- Nuova colonna
            "Routing End Time",  # <-- Nuova colonna
            "Routing Duration"   # <-- Nuova colonna
        ])

        initial_energy_for_percent = config.get("initial_energy", 0.0)

        for srv in all_servers:
            # completed tasks
            for entry in getattr(srv, 'completed_tasks', []):

                (tid, task_type, arr_sys, arr_q, start_t, end_t, ex_t, service_t,
                 time_q, sel_srv, hops, qlen, tranfer_t, image_size,
                 DeadLine, exec_set, eps_cpu, eps_net, eps_tot, srv_rem_energy) = entry

                time_in_system = (end_t - arr_sys) if (
                        isinstance(end_t, (int, float)) and isinstance(arr_sys, (int, float))) else "N/A"

                remaining_percent = "N/A"
                if isinstance(srv_rem_energy, (int, float)) and initial_energy_for_percent > 0:
                    remaining_percent = (srv_rem_energy / initial_energy_for_percent) * 100

                # Ottieni i dati di routing dal dizionario
                r_hops, r_init_time, r_end_time, r_duration = "N/A", "N/A", "N/A", "N/A" # Default
                if tid in task_dict:
                    try:
                        r_hops, r_init_time, r_end_time, r_duration = task_dict[tid].get_stat_csv()
                    except Exception as e:
                        print(f"Warning: could not get routing stats for task {tid}: {e}")

                writer.writerow([
                    tid, task_type, "Completed", arr_sys, arr_q, start_t, end_t,
                    ex_t, service_t, time_in_system, time_q, sel_srv, hops,
                    r_hops, # <-- Valore Routing Hops
                    qlen, tranfer_t, image_size, DeadLine, exec_set,
                    eps_cpu, eps_net, eps_tot, srv_rem_energy, remaining_percent, "N/A",
                    r_init_time, # <-- Valore Routing Init Time
                    r_end_time,  # <-- Valore Routing End Time
                    r_duration   # <-- Valore Routing Duration
                ])

            # rejected tasks (come prima)
            remaining_percent = "N/A"
            if isinstance(srv.energy, (int, float)) and initial_energy_for_percent > 0:
                remaining_percent = (srv.energy / initial_energy_for_percent) * 100

            for (tid, task_type, arr_sys, img_size, reason) in getattr(srv, 'rejected_tasks', []):
                # *** CORREZIONE: Aggiunti 4 "N/A" per le colonne di routing ***
                writer.writerow([
                    tid, task_type, "Rejected", arr_sys, "N/A", "N/A", "N/A",
                    "N/A", "N/A", "N/A", "N/A", srv.name, "N/A",
                    "N/A", # Num Hops Routing
                    "N/A", "N/A", img_size, "N/A", "N/A",
                    "N/A", "N/A", "N/A", srv.energy, remaining_percent, reason,
                    "N/A", # Routing Init Time
                    "N/A", # Routing End Time
                    "N/A"  # Routing Duration
                ])

            # residual tasks: CPU queue & NET queue
            residual_tasks = []
            for req in getattr(srv, 'cpu_dev').queue:
                if hasattr(req, 'task_data'):
                    td = req.task_data
                    residual_tasks.append(
                        {"tid": td.id, "type": "CPU_Waiting", "demand": getattr(td, 'd_cpu', 'N/A')})
            for req in getattr(srv, 'net_dev').queue:
                if hasattr(req, 'task_data'):
                    td = req.task_data
                    residual_tasks.append(
                        {"tid": td.id, "type": "NET_Waiting", "demand": getattr(td, 'd_net', 'N/A')})

            total_residual_count = len(residual_tasks)
            for task_data in residual_tasks:
                tid = task_data["tid"]
                task_type_label = f"Residual ({task_data['type']})"
                demand = task_data["demand"]
                execution_time = demand if task_data["type"] == "CPU_Waiting" else "N/A"
                service_time = demand if task_data["type"] == "NET_Waiting" else "N/A"

                # *** CORREZIONE: Aggiunti 4 "N/A" per le colonne di routing ***
                writer.writerow([
                    tid, task_type_label, "In Queue", "N/A", "N/A", "N/A", "N/A",
                    execution_time, service_time, "N/A", "N/A", srv.name, "N/A",
                    "N/A", # Num Hops Routing
                    total_residual_count, "N/A", "N/A", "N/A", "N/A",
                    "N/A", "N/A", "N/A", srv.energy, "N/A", "In Queue at End",
                    "N/A", # Routing Init Time
                    "N/A", # Routing End Time
                    "N/A"  # Routing Duration
                ])

        # dump also global batch completions (if any)
        for entry in getattr(globals, 'gbl_batch_completed', []):
            (tid, task_type, arr_sys, arr_q, start_t, end_t, ex_t, service_t,
             tq, sel_srv, hops, qlen, trf, image_size,
             DeadLine, exec_set, eps_cpu, eps_net, eps_tot, srv_rem_energy) = entry

            time_in_system = (end_t - arr_sys) if (
                    isinstance(end_t, (int, float)) and isinstance(arr_sys, (int, float))) else "N/A"

            remaining_percent = "N/A"
            if isinstance(srv_rem_energy, (int, float)) and initial_energy_for_percent > 0:
                remaining_percent = (srv_rem_energy / initial_energy_for_percent) * 100

            # *** CORREZIONE: Aggiunti 4 "N/A" per le colonne di routing ***
            writer.writerow([
                tid, task_type, "Completed", arr_sys, arr_q, start_t, end_t,
                ex_t, service_t, time_in_system, tq, sel_srv, hops,
                "N/A", # Num Hops Routing
                qlen, trf, image_size,
                DeadLine, exec_set,
                eps_cpu, eps_net, eps_tot, srv_rem_energy, remaining_percent, "N/A",
                "N/A", # Routing Init Time
                "N/A", # Routing End Time
                "N/A"  # Routing Duration
            ])

    print(f"Simulation results saved to: {csv_task}")

    # --------------------------------------------------
    # 8) Scrittura Statistiche Energetiche e Task Counts
    # --------------------------------------------------

    csv_energy_stats = (
        f"{base_dir}/energy_stats_"
        f"{gen_dist}_REQ-{req_dist}_"
        f"AT_{atime}_CPU_{cpu_mean}.csv"
    )

    print(f"\nSalvataggio statistiche energetiche e conteggi task su: {csv_energy_stats}")

    try:
        # Prendi l'energia iniziale dal config per calcolare la percentuale
        initial_energy = config.get("initial_energy", 0.0)

        # 1. Inizializza un dizionario per raccogliere le statistiche
        stats_per_server = {}
        for srv in all_servers:
            stats_per_server[srv.name] = {
                "server_obj": srv,
                "energy_consumptions": [],
                "task_counts": {
                    "Generic_Service": 0,
                    "CPU_Intensive": 0,
                    "CPU_and_Data_Intensive": 0,
                    "Batch": 0
                }
            }

        # 2. Popola le statistiche dai task NON-BATCH (da srv.completed_tasks)
        for srv in all_servers:
            for entry in getattr(srv, 'completed_tasks', []):
                task_type = entry[1]  # Indice 1 per task_type
                energy = entry[18]    # Indice 18 per eps_tot

                if task_type in stats_per_server[srv.name]["task_counts"]:
                    stats_per_server[srv.name]["task_counts"][task_type] += 1

                if isinstance(energy, (int, float)) and energy > 0.0:
                    stats_per_server[srv.name]["energy_consumptions"].append(energy)

        # 3. Popola le statistiche dai task BATCH (da globals.gbl_batch_completed)
        for entry in getattr(globals, 'gbl_batch_completed', []):
            server_name = entry[9]  # Indice 9 per sel_srv
            task_type = entry[1]    # Indice 1 per task_type
            energy = entry[18]      # Indice 18 per eps_tot

            if server_name in stats_per_server and task_type == "Batch":
                stats_per_server[server_name]["task_counts"]["Batch"] += 1
                if isinstance(energy, (int, float)) and energy > 0.0:
                    stats_per_server[server_name]["energy_consumptions"].append(energy)

        # 4. Scrivi il file CSV
        with open(csv_energy_stats, mode='w', newline='') as f_stats:
            writer_stats = csv.writer(f_stats)

            # Scrivi l'intestazione
            writer_stats.writerow([
                "Server_Name",
                "Total_Tasks_Completed",
                "Generic_Service_Count",
                "CPU_Intensive_Count",
                "CPU_Data_Intensive_Count",
                "Batch_Count",
                "Generic_Service_%",
                "CPU_Intensive_%",
                "CPU_Data_Intensive_%",
                "Batch_%",
                "Total_Energy_Consumed_J",
                "Total_Energy_Consumed_%",
                "Min_Energy_Consumed_J",
                "Max_Energy_Consumed_J",
                "Avg_Energy_Consumed_J",
                "Final_Remaining_Energy_J"
            ])

            # 5. Calcola le statistiche finali e scrivi le righe
            for server_name, stats in stats_per_server.items():

                task_counts = stats["task_counts"]
                energy_consumptions = stats["energy_consumptions"]

                total_tasks_completed = sum(task_counts.values())

                # Calcolo percentuali per tipo di task
                if total_tasks_completed > 0:
                    percent_generic = (task_counts["Generic_Service"] / total_tasks_completed) * 100
                    percent_cpu = (task_counts["CPU_Intensive"] / total_tasks_completed) * 100
                    percent_cpu_data = (task_counts["CPU_and_Data_Intensive"] / total_tasks_completed) * 100
                    percent_batch = (task_counts["Batch"] / total_tasks_completed) * 100
                else:
                    percent_generic = 0.0
                    percent_cpu = 0.0
                    percent_cpu_data = 0.0
                    percent_batch = 0.0

                # Calcolo statistiche energetiche
                if energy_consumptions:
                    total_e = sum(energy_consumptions)
                    min_e = min(energy_consumptions)
                    max_e = max(energy_consumptions)
                    avg_e = total_e / len(energy_consumptions)
                    total_e_percent = (total_e / initial_energy) * 100 if initial_energy > 0 else 0.0
                else:
                    total_e = 0.0
                    min_e = 0.0
                    max_e = 0.0
                    avg_e = 0.0
                    total_e_percent = 0.0

                # Scrivi la riga
                writer_stats.writerow([
                    server_name,
                    total_tasks_completed,
                    task_counts["Generic_Service"],
                    task_counts["CPU_Intensive"],
                    task_counts["CPU_and_Data_Intensive"],
                    task_counts["Batch"],
                    percent_generic,
                    percent_cpu,
                    percent_cpu_data,
                    percent_batch,
                    total_e,
                    total_e_percent,
                    min_e,
                    max_e,
                    avg_e,
                    stats["server_obj"].energy  # Energia finale rimasta
                ])

    except Exception as e:
        print(f"ERRORE during writing the energy stats file: {e}")

    # Calcolo tempo reale di esecuzione
    end_time_simulation_real = time.time()
    duration_simulation = end_time_simulation_real - start_time_simulation_real
    print(f"Tempo di esecuzione REALE della simulazione {duration_simulation:.4f} secondi")