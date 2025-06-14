import random
import simpy
import json
from  Observer import Observer 
from user_based_topology import getObserverObj
from topology import periodic_recall_Topology_monitor, loadConfiguration
from routing_Manager import periodic_recall_Routing_monitor

import globals
import time

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

# Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
try:
    with open("data/configurations.json", "r") as f:
        print("Configuration file loaded.\n")
        data_configurations = json.load(f)
except Exception as e:
    print(f"Error loading configuration file: {e}")


def process_OGM_enviroment_simulation():
    random.seed(config["seed"])

    env_ogm = simpy.Environment()   

    print("Carico le configurazioni dal File")
    globals.edge_servers, globals.global_access_point = loadConfiguration(
            env_ogm)
    
    globals.observer = Observer(env_ogm, getObserverObj())  # Singleton Observer

    env_ogm.process(periodic_recall_Topology_monitor(env_ogm))
    env_ogm.process(periodic_recall_Routing_monitor(env_ogm, globals.observer, data_configurations))

    start_time = time.time()
    env_ogm.run(config['simulation_duration'])
    end_time = time.time()
    print(f"Simulation run time: {end_time - start_time:.2f} seconds")

process_OGM_enviroment_simulation()