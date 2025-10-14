import simpy
import globals
import json, json5
from  Observer import Observer 
from user_based_topology import getObserverObj
from topology import distribute_ogm, loadConfiguration, loadConfiguration_simple
from routing_Manager import periodic_recall_Routing_monitor

import time

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

ADDING_TIME = config["adding_time"] # secondi di aggiunta al  
CONFIG_RIEMPI = ADDING_TIME // 2    # configurazioni aggiuntive da rimuovere



def process_OGM_enviroment_simulation(data_configuration):
    """
    Funzione usata per la costruzione delle tabelle OGM nella fase di PRE-Loading
    """
    
    globals.rnd.seed(config["seed"])

    env_ogm = simpy.Environment()  
    simulation_duration = config['simulation_duration'] + ADDING_TIME    #Aggiungo 60 secondi (30 conf) di simulazione per il caricamento delle tabelle
    #simulation_duration = config['simulation_duration']
    

    globals.observer = Observer(env_ogm, getObserverObj())  # Singleton Observer
    env_ogm.process(distribute_ogm(env_ogm, data_configuration, CONFIG_RIEMPI))    # ! Processo di redistribuzione

    start_time = time.time()
    env_ogm.run(simulation_duration)
    end_time = time.time()
    
    print(f"Simulation run time: {end_time - start_time:.2f} seconds")



def remove_first_30_configurations():
    with open("data/configurations.json", "r") as f:
        data = json.load(f)

    config_list = data["configurations"]
    
    n_tot_conf = int(config["simulation_duration"]) // int(config["Interval_between_Configurations_in_seconds"]) 
    
    print(f"inizialmente: {len(config_list)}")
    del config_list[:CONFIG_RIEMPI]    # Elimino le conf di riempimento delle table
    print(f"Elimino i primi di riempimento: {len(config_list)}")
    
    data["configurations"] = config_list
    data["t0"] = config_list[0]["time"]
    data["total_seconds"] = config['simulation_duration']
    
    print(f"total_second: {data['total_seconds']} <= {config['simulation_duration']}")
    print(f"tempo {data['t0']} configList tempo {config_list[0]['time']}")
    
    with open("data/configurations.json", "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    process_OGM_enviroment_simulation() 
    remove_first_30_configurations()