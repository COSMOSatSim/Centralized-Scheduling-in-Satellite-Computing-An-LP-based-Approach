import csv
import json
import logging
import os
import sys
import time
import random
import simpy
from simulation import generate_tasks
from topology import loadConfiguration, periodic_recall_Topology_monitor, create_topology_dome, genConfigs, updateTaskValue, data_configurations, string_to_skyfield_time
from user_based_topology import get_current_time, getObserverObj
from SaveCurrentSATOnFile import saveTLEOnFile
from routing_Manager import periodic_recall_Routing_monitor
from  Observer import Observer 
import globals


# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)


if __name__ == "__main__":
    # Setup and start the simulation
    random.seed(config["seed"])

    env = simpy.Environment()
    MaxTry = config["max_try"]  # Imposta il valore massimo di MaxTry

    if config["Build_Configurations"]:  # Gestione costruizione configurazioni
        saveTLEOnFile()  # Salva i dati TLE dei satelliti in un file
        genConfigs(get_current_time(), config["Interval_between_Configurations_in_seconds"],
                   # Costruisco le configurazioni a partire dai TLE
                   config["Number_of_Configurations"])


        T_min, T_max, T_avg = updateTaskValue()     # Aggiorna i valori dei task
        config["Build_Configurations"] = False
        config["CPU_timeout"]["min"] = T_min
        config["CPU_timeout"]["max"] = T_max
        config["CPU_timeout"]["mean"] = T_avg + 2.0

        try:
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=1)
        except IOError as e:
            print(f"Errore nella scrittura del file di configurazione: {e}")
            sys.exit(1)  # Termina lo script

        sys.exit("File of configurations created")


    if config["Load_Configuration"]:
        print("Carico le configurazioni dal File")
        globals.edge_servers, globals.global_access_point = loadConfiguration(
            env)  # Carico la configurazione e assegno a edge_servers
        # Faccio partire il thread per cambiare configurazione
        env.process(periodic_recall_Topology_monitor(env))
    else:
        print("Creo la topologia")
        globals.edge_servers = create_topology_dome(env)

    globals.observer = Observer(env, getObserverObj())  # Singleton Observer
    env.process(periodic_recall_Routing_monitor(env))

    skyfield_time = string_to_skyfield_time(data_configurations["t0"])


    globals.initial_server_counter = {
        server.name: 0 for server in globals.edge_servers}
    globals.different_server_counter = {
        server.name: 0 for server in globals.edge_servers}
    globals.other_server_counter = {
        server.name: 0 for server in globals.edge_servers}

    env.process(generate_tasks(env, globals.initial_server_counter,
                globals.different_server_counter, globals.other_server_counter))

    end_time = time.time()  # Tempo finale

    network_type = config["network_type"]["type"]  # open / close

    # Costruisce il nome del file CSV
    # Ottiene i valori di priority_combination e generate_tasks
    priority_distribution = config["priority_combination"]["distribution"]
    generate_tasks_distribution = config["generate_tasks"]["distribution"]
    config_seed = config["seed"]
    config_arrival_time = config["arrival_time_exponential"]
    config_CPU_Timeout = config["CPU_timeout"]["mean"]
    distribution_string = config["request_distribution"]["distribution"]
    if distribution_string == "0_0_0":
        distribution_string = "RR"
    access_point = config["access_point"]

    # Specifica il percorso della directory che vuoi creare
    # percorso_directory = f"simulation result_{distribution_string}_request_distribution_latency_{latency}_distribuited/{config_seed}"
    percorso_directory = f"simulation result-{network_type}-System_AP{access_point}/simulation result_{distribution_string}_request_distribution_distribuited/{config_seed}"
    os.makedirs(percorso_directory, exist_ok=True)

    csv_name = f"{percorso_directory}/simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_AT_{config_arrival_time}_CPU_{config_CPU_Timeout}.csv"
    csv_name_server = f"{percorso_directory}/server_name_migration_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_AT_{config_arrival_time}_CPU_{config_CPU_Timeout}.csv"
    # Crea un file CSV per registrare i risultati
    csv_file = config["csv_name"]["name"] = csv_name
    log_name = f"simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.log"

    print(
        f"Start simulation for seed {config_seed}, priority distribution {priority_distribution}, arrival time {config_arrival_time}")

    log_file_path = os.path.join(os.path.dirname(csv_file), log_name)

    # setup_logging(log_file_path) #abilita la scrittura dei log

    env.run(config['simulation_duration'])

    print(f"A FINE SIMULAZIONE OBSERVER REGISTRA {len(globals.observer.tasks)} ")

    # task_queueprint("SIMULATION COMPLETED, check RAM :")
    '''
    for server in globals.edge_servers:
        print(f"{server.name} queue task :")
        [print(f"\t\t{task[0]}") for task in server.server_queue]
        print(f"{server.name} completed task :")
        [print(f"\t\t{task[0]}") for task in server.completed_tasks]
        print("@"*10)'''

    # Scrive i dati dei task nel file CSV
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(
            ["Task ID", "Task Priority", "Arrival time in system", "arrival_time_task_queue", "Start Time", "End Time",
             "Execution time", "Time in system", "Time in queue", "Server Name", "Num Hops", "Queue length",
             "original_TaskPriority", "estimated_execution_time", "transfer_time", "Utility", "TMAX_exceeded", "Exec_after_set"])

        for server in globals.edge_servers:
            for task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time, execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda, original_TaskPriority, estimated_execution_time, transfer_time, utility, TMAX_exceeded, exec_after_set in server.completed_tasks:
                if original_TaskPriority == 1:
                    original_TaskPriority = 'high'
                else:
                    original_TaskPriority = 'low'

                writer.writerow(
                    [task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time,
                     execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda,
                     original_TaskPriority, estimated_execution_time, transfer_time, utility, TMAX_exceeded, exec_after_set])
            for task_id, required_ram, required_disk, task_priority, arrival_time_system, estimated_execution_time, transfer_time, utility, num_hops, arrival_time_task_queue, original_TaskPriority, in server.server_queue:
                TMAX_exceeded = False
                if task_priority == 1 or original_TaskPriority == 1:
                    # print('executiontime', execution_time, 'task id', task_id, 'utilization')
                    writer.writerow(
                        [task_id, 'high', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now -
                                                               arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'high', estimated_execution_time, transfer_time, utility, TMAX_exceeded])
                else:
                    writer.writerow(
                        [task_id, 'low', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now -
                                                               arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'low', estimated_execution_time, transfer_time, utility, TMAX_exceeded])
                # il task salvato in coda ha i seguenti parametri nel seguente ordine:

    print(f"Simulation results saved to: {csv_file}")
    # print('R_j user', globals.initial_server_counter, 'F_j other', globals.different_server_counter, 'R_j other', globals.other_server_counter)

    # Compute statistics for the results
    I_j = {}
    for server_key in globals.other_server_counter.keys():  # Iterate over dictionary keys
        numerator = globals.other_server_counter[server_key]
        # Sum all values
        denominator = sum(globals.different_server_counter.values())
        if denominator != 0:
            I_j[server_key] = numerator / denominator
        else:
            I_j[server_key] = 0  # Avoid division by zero

    F_j = {}
    for server_key in globals.other_server_counter.keys():  # Iterate over dictionary keys
        numerator = globals.different_server_counter[server_key]
        denominator = globals.initial_server_counter[server_key] + \
            globals.other_server_counter[server_key]
        if denominator != 0:
            F_j[server_key] = numerator / denominator
        else:
            F_j[server_key] = 0  # Avoid division by zero

    # Print results
    # print("I_j:", I_j)
    # print("F_j:", F_j)
    # Write data to CSV file
    with open(csv_name_server, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Server', 'R_j_user', 'F_j_other',
                        'R_j_other', 'I_j', 'F_j'])
        for server_key in globals.initial_server_counter.keys():
            writer.writerow(
                [server_key, globals.initial_server_counter[server_key], globals.different_server_counter[server_key],
                 globals.other_server_counter[server_key], I_j.get(server_key, 0), F_j.get(server_key, 0)]
            )

    print(f"Data of migration server saved to {csv_name_server} ")
