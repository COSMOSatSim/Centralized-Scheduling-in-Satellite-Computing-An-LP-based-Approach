import threading, os, json5, json
import random as _random
import numpy as np
import sys

# Funzione per determinare il file di configurazione
def get_param_file():
    default_config = 'config.json5'
    default_img = 'img_resolution.json5'

    if len(sys.argv) == 3:
        config_file, img_file = sys.argv[1], sys.argv[2]

        if os.path.exists(config_file) and os.path.exists(img_file):
            return config_file, img_file
        else:
            sys.exit("Errore nel caricamento dei File.")
    else:
        print(" Prendo gli Argomenti di Deafult!")
    return default_config, default_img

# Carica il file di configurazione appropriato
config_file_path, img_resolution = get_param_file()

# Leggi il file di configurazione JSON
try:
    with open(config_file_path) as config_file:
        config = json5.load(config_file)
except FileNotFoundError:
    config = None
    sys.exit("ERRORE: Impossibile trovare 'config.json5'. Assicurati che il file esista.")


try:
    with open(img_resolution) as res_file:
        resolution_config = json5.load(res_file)["TASK_GENERATOR_PARAMS"]
except FileNotFoundError:
    resolution_config = None
    sys.exit("ERRORE: Impossibile trovare 'img_resolution.json5'. Assicurati che il file esista.")

# Imposta seme e ambiente
_seed = int(config.get("seed", 42))

# Python stdlib RNG (con API Random) — per funzioni che usano `random` builtin
rnd = _random.Random(_seed)
np.random.seed(_seed) ##questa si potrebbe rimuovere

# NumPy Generator: for exponential sampling, uniform, etc.
# Use the new Generator API so behavior is deterministic across NumPy versions
rnd_np = np.random.default_rng(_seed)


# Variabili globali per i server
initial_server_counter = {}     # Tiene traccia dei task inizializzati su ogni server
different_server_counter = {}   # Tiene traccia dei task inoltrati a server diversi
other_server_counter = {}       # Tiene traccia di altre metriche per i server
gbl_generated_tasks_data = [] # Lista per raccogliere i dettagli del task generato

global_access_point = []    # Lista degli access point globali
next_server_index = 0       # Indice del prossimo server a cui inviare un task
gbl_batch_completed = []   # new global list for batch completions
config_index = 0            # Indice che indica la configurazione corrente

edge_servers = []           # Lista dei server globali totali
edge_servers_topology = []  # Edge Servers nella topologia nella configurazione 

observer = None
ist_in_conf = None          #Istante nella configurazione attuale 

gbl_tasks = []              # Lista che mantiene tutti i Task creati per il Routing
gbl_packet = []             # Lista globale dei pacchetti che girano nel simulatore

lock_access_edge_servers_topology = threading.Lock()  # Meccanismo di lock



# Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
def load_or_create_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

try:
    configurations_path = None
    if config["AP_selection"] == "base":
        configurations_path = "data/configurations_AP_base.json"
    elif config["AP_selection"] == "optimal":
        configurations_path = "data/configurations_AP_optimal.json"
    else:
        sys.exit("Errore con AP Selection, configurazione inesistente.")

    data_configurations = load_or_create_json(configurations_path)
    print(f"Configuration file ({configurations_path}) loaded.\n")
    OGMs_tables = load_or_create_json("data/OGMs_table.json")
    print("OGMs table file loaded.")
except Exception as e:
    print(f"Error loading configuration file: {e}")
