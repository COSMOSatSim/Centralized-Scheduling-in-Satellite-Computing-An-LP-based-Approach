import threading, os, json
import random as _random
import numpy as np

# Imposta seme e ambiente
rnd = _random.Random()
rnd.seed(13)
np.random.seed(13)


# Variabili globali per i server
initial_server_counter = {}     # Tiene traccia dei task inizializzati su ogni server
different_server_counter = {}   # Tiene traccia dei task inoltrati a server diversi
other_server_counter = {}       # Tiene traccia di altre metriche per i server

global_access_point = []    # Lista degli access point globali
next_server_index = 0       # Indice del prossimo server a cui inviare un task

config_index = 0            # Indice che indica la configurazione corrente

edge_servers = []           # Lista dei server globali totali
edge_servers_topology = []  # Edge Servers nella topologia nella configurazione 

observer = None
ist_in_conf = None          #Istante nella configurazione attuale 

gbl_tasks = []              # Lista che mantiene tutti i Task creati per il Routing

lock_access_edge_servers_topology = threading.Lock()  # Meccanismo di lock



# Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
def load_or_create_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

try:
    data_configurations = load_or_create_json("data/configurations.json")
    print("Configuration file loaded.\n")
    OGMs_tables = load_or_create_json("data/OGMs_table.json")
    print("OGMs table file loaded.")
    positions_vectors = load_or_create_json("data/positions_vectors.json")
except Exception as e:
    print(f"Error loading configuration file: {e}")

