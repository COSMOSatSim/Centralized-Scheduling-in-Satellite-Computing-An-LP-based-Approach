import random
import simpy
import json
from  Observer import Observer 
from user_based_topology import getObserverObj
from topology import distribute_ogm, loadConfiguration
from routing_Manager import periodic_recall_Routing_monitor
from routing_Manager import data_configurations


import globals
import time

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)




def process_OGM_enviroment_simulation():
    """
    Funzione usata per la costruzione delle tabelle OGM nella fase di PRE-Loading
    """
    
    random.seed(config["seed"])

    env_ogm = simpy.Environment()  
    simulation_duration = config['simulation_duration'] + 60    #Aggiungo 60 secondi (30 conf) di simulazione per il caricamento delle tabelle
    #simulation_duration = config['simulation_duration']
    
    globals.observer = Observer(env_ogm, getObserverObj())  # Singleton Observer
    globals.edge_servers, globals.global_access_point = loadConfiguration(env_ogm)
    
    env_ogm.process(distribute_ogm(env_ogm))    # ! Processo di redistribuzione

    start_time = time.time()
    env_ogm.run(simulation_duration)

    end_time = time.time()
    print(f"Simulation run time: {end_time - start_time:.2f} seconds")

    # Salva su file dopo la modifica
    print("Salvataggio modifiche configurations")
    with open("data/configurations.json", "w") as f:
        json.dump(data_configurations, f, indent=4)


def remove_first_30_configurations():
    with open("data/configurations.json", "r") as f:
        data = json.load(f)
        

    config_list = data["configurations"]
    
    n_tot_conf = int(config["simulation_duration"]) // int(config["Interval_between_Configurations_in_seconds"]) 
    
    print(f"inizialmente: {len(config_list)}")
    del config_list[:30]    # Elimino le conf di riempimento delle table
    print(f"Elimino i primi di riempimento: {len(config_list)}")
    del config_list[n_tot_conf:] # Elimino tutte le conf in eccesso
    print(f"elimino l'eccesso: {len(config_list)}")

    data["configurations"] = config_list
    data["t0"] = config_list[0]["time"]
    data["total_second"] = config['simulation_duration']

    print(f"tempo {data["t0"]} configList tempo {config_list[0]["time"]}")
    
    with open("data/configurations.json", "w") as f:
        json.dump(data, f, indent=4)


if __name__ == "__main__":
    process_OGM_enviroment_simulation()
    remove_first_30_configurations()