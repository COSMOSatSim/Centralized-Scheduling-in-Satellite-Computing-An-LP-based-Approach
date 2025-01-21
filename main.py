import csv
import json
import logging
import os
import sys
import time
import random
import simpy
from simulation import generate_tasks
from topology import loadConfiguration, periodic_recall_monitor, create_topology_dome, genConfigs, global_access_point
from user_based_topology import get_current_time

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

if __name__ == "__main__":

    global edge_servers, initial_server_counter, different_server_counter, other_server_counter

    # Setup and start the simulation
    random.seed(config["seed"])

    if config["Build_Configurations"]:  # Gestione costruizione configurazioni
        genConfigs(get_current_time(), config["Interval_between_Configurations_in_seconds"],
                   config["Number_of_Configurations"])
        config["Build_Configurations"] = False
        try:
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=1)
        except IOError as e:
            print(f"Errore nella scrittura del file di configurazione: {e}")
            sys.exit(1)  # Termina lo script

        sys.exit("File of configurations created")
    env = simpy.Environment()
    hop = 0  # Inizializza la variabile hop a zero
    MaxTry = config["max_try"]  # Imposta il valore massimo di MaxTry
    total_time = 0  # Imposta il valore iniziale di total_time

    if config["Load_Configuration"]:
        print("Carico le configurazioni dal File")
        edge_servers, global_access_point = loadConfiguration(env)  # Carico la configurazione e assegno a edge_servers
        env.process(periodic_recall_monitor(env))  # Faccio partire il thread per cambiare configurazione
    else:
        print("Creo la topologia")
        edge_servers = create_topology_dome(env)

    initial_server_counter = {server.name: 0 for server in edge_servers}
    different_server_counter = {server.name: 0 for server in edge_servers}
    other_server_counter = {server.name: 0 for server in edge_servers}

    env.process(generate_tasks(env, global_access_point))

    end_time = time.time()  # Tempo finale

    network_type = config["network_type"]["type"]  # open / close

    # Costruisce il nome del file CSV
    # Ottiene i valori di priority_combination e generate_tasks
    priority_distribution = config["priority_combination"]["distribution"]
    generate_tasks_distribution = config["generate_tasks"]["distribution"]
    config_seed = config["seed"]
    config_arrival_time = config["arrival_time_exponential"]
    distribution_string = config["request_distribution"]["distribution"]
    if distribution_string == "0_0_0":
        distribution_string = "RR"
    latency = config["latency"]["min"]
    access_point = config["access_point"]

    # Specifica il percorso della directory che vuoi creare
    # percorso_directory = f"simulation result_{distribution_string}_request_distribution_latency_{latency}_distribuited/{config_seed}"
    percorso_directory = f"simulation result-{network_type}-System_AP{access_point}/simulation result_{distribution_string}_request_distribution_latency_{latency}_distribuited/{config_seed}"
    os.makedirs(percorso_directory, exist_ok=True)

    csv_name = f"{percorso_directory}/simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.csv"
    csv_name_server = f"{percorso_directory}/server_name_migration_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.csv"
    # Crea un file CSV per registrare i risultati
    csv_file = config["csv_name"]["name"] = csv_name
    log_name = f"simulation_results_{priority_distribution}_{generate_tasks_distribution}_{config_seed}_{config_arrival_time}.log"

    print(
        f"Start simulation for seed {config_seed}, priority distribution {priority_distribution}, arrival time {config_arrival_time}")

    log_file_path = os.path.join(os.path.dirname(csv_file), log_name)

    # setup_logging(log_file_path) #abilita la scrittura dei log

    env.run(config['simulation_duration'])

    # Scrive i dati dei task nel file CSV
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(
            ["Task ID", "Task Priority", "Arrival time in system", "arrival_time_task_queue", "Start Time", "End Time",
             "Execution time", "Time in system", "Time in queue", "Server Name", "Num Hops", "Queue length",
             "original_TaskPriority", "TMAX_exceeded"])

        for server in edge_servers:
            for task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time, execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda, original_TaskPriority, TMAX_exceeded in server.completed_tasks:
                if original_TaskPriority == 1:
                    original_TaskPriority = 'high'
                else:
                    original_TaskPriority = 'low'

                writer.writerow(
                    [task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time,
                     execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda,
                     original_TaskPriority, TMAX_exceeded])
            for task_id, required_cpu, required_ram, required_disk, task_priority, arrival_time_system, utilization_CPU, num_hops, arrival_time_task_queue, original_TaskPriority in server.server_queue:
                TMAX_exceeded = False
                if task_priority == 1 or original_TaskPriority == 1:
                    # print('executiontime', execution_time, 'task id', task_id, 'utilization', utilization_CPU)
                    writer.writerow(
                        [task_id, 'high', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now - arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'high', TMAX_exceeded])
                else:
                    writer.writerow(
                        [task_id, 'low', arrival_time_system, arrival_time_task_queue, 0, 0, 0,
                         (env.now - arrival_time_task_queue), (env.now - arrival_time_task_queue), server.name,
                         num_hops, len(list(server.server_queue)), 'low', TMAX_exceeded])
                # il task salvato in coda ha i seguenti parametri nel seguente ordine:
                # task = task_id, required_cpu, required_ram, required_disk, task_priority, arrival_time_system, utilization_CPU, num_hops

    print(f"Simulation results saved to: {csv_file}")
    print('R_j user', initial_server_counter, 'F_j other', different_server_counter, 'R_j other', other_server_counter)

    # Compute statistics for the results
    I_j = {}
    for server_key in other_server_counter.keys():  # Iterate over dictionary keys
        numerator = other_server_counter[server_key]
        denominator = sum(different_server_counter.values())  # Sum all values
        if denominator != 0:
            I_j[server_key] = numerator / denominator
        else:
            I_j[server_key] = 0  # Avoid division by zero

    F_j = {}
    for server_key in other_server_counter.keys():  # Iterate over dictionary keys
        numerator = different_server_counter[server_key]
        denominator = initial_server_counter[server_key] + other_server_counter[server_key]
        if denominator != 0:
            F_j[server_key] = numerator / denominator
        else:
            F_j[server_key] = 0  # Avoid division by zero

    # Print results
    print("I_j:", I_j)
    print("F_j:", F_j)
    # Write data to CSV file
    with open(csv_name_server, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Server', 'R_j_user', 'F_j_other', 'R_j_other', 'I_j', 'F_j'])
        for server_key in initial_server_counter.keys():
            writer.writerow(
                [server_key, initial_server_counter[server_key], different_server_counter[server_key],
                 other_server_counter[server_key], I_j.get(server_key, 0), F_j.get(server_key, 0)]
            )

    print(f"Data of migration server saved to {csv_name_server} ")

    logging.info(f"Simulation results saved to: {csv_file}")
    print(f"Simulation LOG saved to: {log_name}")
    logging.info("Simulation completed")
