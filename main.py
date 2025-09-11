import csv
import json5
import os
import sys
import random
import simpy
from EdgeServer import build_task_csv_path
from Task import generate_Tasks_Status
from simulation import generate_tasks
from topology import loadConfiguration, periodic_recall_Topology_monitor, create_topology_dome, genConfigs, updateTaskValue, string_to_skyfield_time
from user_based_topology import get_current_time, getObserverObj
from SaveCurrentSATOnFile import saveTLEOnFile
from routing_Manager import periodic_recall_Routing_monitor
from Observer import Observer
from simulation_OGM import process_OGM_enviroment_simulation, remove_first_30_configurations
import globals

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)


if __name__ == "__main__":
    # Imposta seme e ambiente
    random.seed(config["seed"])
    env = simpy.Environment()
    MaxTry = config.get("max_try", 10)

    # 1) Costruzione configurazioni
    if config.get("Build_Configurations", False):
        
        tle_data = saveTLEOnFile()
        tot_config = int((config["simulation_duration"] + config["adding_time"]) / 2)
        configurations = genConfigs(
            get_current_time(),
            config["Interval_between_Configurations_in_seconds"],
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
        globals.edge_servers, globals.global_access_point = loadConfiguration(env, globals.data_configurations, globals.OGMs_tables, globals.positions_vectors)
        env.process(periodic_recall_Topology_monitor(env, globals.data_configurations, globals.OGMs_tables, globals.positions_vectors))
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

    # 4) Avvia la generazione dei task
    env.process(generate_tasks(
        env,
        globals.initial_server_counter,
        globals.different_server_counter,
        globals.other_server_counter
    ))

    # 5) Preparazione dei nomi di cartella e file
    # Prendo direttamente mode_name scritto dal runner in config.json
    mode_name             = config.get("mode_name", "UnknownMode").replace(" ", "_")
    ap                    = config.get("access_point", 0)
    seed_val              = config["seed"]
    prio_dist             = config["priority_combination"]["distribution"]
    gen_dist              = config["generate_tasks"]["distribution"]
    req_dist              = config["request_distribution"]["distribution"]
    if req_dist == "0_0_0":
        req_dist = "RR"
    atime                 = config["arrival_time_exponential"]
    cpu_mean              = config["CPU_timeout"]["mean"]

    # Cartella base: include modalità, AP e seed
    base_dir = f"{req_dist}-sim_SystemAP{ap}/seed_{seed_val}"
    task_dir = f"{req_dist}-Task_Result{ap}/seed_{seed_val}"
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(task_dir, exist_ok=True)

    # File CSV e log con nomenclatura completa
    csv_task = (
        f"{base_dir}/results_{prio_dist}_"
        f"{gen_dist}_REQ-{req_dist}_"
        f"AT_{atime}_CPU_{cpu_mean}.csv"
    )
    csv_mig = (
        f"{base_dir}/migration_{prio_dist}_"
        f"{gen_dist}_REQ-{req_dist}_"
        f"AT_{atime}_CPU_{cpu_mean}.csv"
    )
    csv_routing_task = build_task_csv_path(task_dir, atime, cpu_mean)
    
    log_file = f"{base_dir}/log_{prio_dist}_{gen_dist}_AT_{atime}.log"

    # Salvo il nome del CSV nel config per eventuali moduli esterni
    config["csv_name"] = {"name": csv_task}
    with open('config.json5', 'w') as wf:
        json5.dump(config, wf, indent=2)

    print(f"--- Avvio simulazione ---")
    print(f"Modalità: {mode_name}")
    print(f"Cartella: {base_dir}")
    print(f"CSV tasks: {csv_task}")
    print(f"CSV migrazioni: {csv_mig}")
    print(f"Log: {log_file}")

    # 6) Esecuzione simulazione
    env.run(config['simulation_duration'])

    # Stampa il riassunto dei task usando la funzione dell'Observer
    globals.observer.print_task_summary()
    print("-"*10)
    generate_Tasks_Status(csv_routing_task)


    # 7) Scrittura risultati su CSV
    with open(csv_task, mode='w', newline='') as f_out:
        writer = csv.writer(f_out)
        writer.writerow([
            "Task ID","Task Priority","Arrival time in system","arrival_time_task_queue",
            "Start Time","End Time","Execution time","Time in system","Time in queue",
            "Server Name","Num Hops","Queue length","original_TaskPriority",
            "estimated_execution_time","transfer_time","Utility","TMAX_exceeded","Exec_after_set",
            "Energy_CPU [J]","Energy_NET [J]","Energy_TOTAL [J]","Remaining_energy [J]"
        ])

        for srv in globals.edge_servers:
            # completed_tasks
            for (
                tid, tp, arr_sys, arr_q, st, et, ex_t, sv_t,
                tq, sel_srv, hops, qlen, orig_p, est_e, trf,
                util, tmax_exc, exec_set, eps_cpu, eps_net, eps_tot
            ) in srv.completed_tasks:
                orig_label = 'high' if orig_p == 1 else 'low'
                writer.writerow([
                    tid, tp, arr_sys, arr_q, st, et,
                    ex_t, sv_t, tq, sel_srv, hops,
                    qlen, orig_label, est_e, trf,
                    util, tmax_exc, exec_set,
                    eps_cpu, eps_net, eps_tot, srv.energy
                ])


            # server_queue residui
            for (
                tid, rr, rd, tp, arr_sys, est_e, trf, util,
                hops, arr_q, orig_p
            ) in srv.server_queue:
                label = 'high' if tp == 1 or orig_p == 1 else 'low'
                time_in_q = env.now - arr_q
                writer.writerow([
                    tid, label, arr_sys, arr_q,
                    0, 0, 0, time_in_q,
                    time_in_q, srv.name, hops,
                    len(srv.server_queue), label,
                    est_e, trf, util, False,
                    0.0, 0.0, 0.0, srv.energy  # se non eseguito, consumo=0
                ])

    print(f"Simulation results saved to: {csv_task}")