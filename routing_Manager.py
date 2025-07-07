import random
import json
from user_based_topology import get_orbit_proximity, getSystemFromSat
from Ogm import Ogm
from Observer import Observer
import globals
import sys
import os

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


def clear_line():
    # Sposta il cursore all'inizio e sovrascrive con spazi
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()

def print_progress_bar(i, total, bar_length=30):
    progress = int(bar_length * i / total)
    bar = '#' * progress + '-' * (bar_length - progress)
    output = f'\r\t\t[{bar}] {i}/{total}'

    sys.stdout.write(output)
    sys.stdout.flush()

    if i == total:
        # Alla fine: cancella riga e non va a capo
        clear_line()


def manage_ogm_test(ogm_map, t):

    print("\t| Generazione OGM")
    # Ogni Nodo manda un OGM
    for node in ogm_map:
        create_ogm(node, node.getPositionVector(t))

    print("\t| Processing OGMs")
    total = len(ogm_map)

    for i, node in enumerate(ogm_map, start=1):
        #print(f"\t{node.name} : N to Processing ({len(node.OGMs)})")
        for ogm in node.OGMs:
            #! Fase di Controllo
            if ogm.id in node.OGMs_History or ogm.ttl == 0:  # Il pacchetto è stato già visionato o è scaduto
                continue    # non lo mando

            # Se il pacchetto è il mio ma mi è arrivato da qualqun altro
            if ogm.originator == node.name and ogm.sender != node.name:
                continue    #non lo mando

            # Se il pacchetto non l'ho generato io, lo salvo
            if ogm.originator != node.name and ogm.sender != node.name:
                node.OGMs_History[ogm.id] = {"originator": ogm.originator, "sender": ogm.sender}
            
            # ! Fase di salvataggio del OGM nella tabella di questo nodo
            if ogm.originator != node.name:  # Non mi salvo i pacchetti che riguardano questo server
                if ogm.originator not in node.ogm_table:
                    node.ogm_table[ogm.originator] = {}

                # Aggiorno la Table
                if ogm.sender not in node.ogm_table[ogm.originator]:
                    node.ogm_table[ogm.originator][ogm.sender] = 0
                node.ogm_table[ogm.originator][ogm.sender] += 1
                
                #print("-"*10)
                # $ Inizializzazione dizionario delle posizioni
                if ogm.originator not in node.OGMs_position:
                    #print(f"\t[{node.name}] get {ogm.id} | [orig:{ogm.originator} sender:{ogm.sender}] carico -> {ogm.origin_position_vect} ")
                    node.OGMs_position[ogm.originator] = (ogm.sequence_number, ogm.origin_position_vect)
                    #print(f"\tsaved! : {node.OGMs_position[ogm.originator]}")
                else:
                    # $ Controllo se aggiornare il valore 
                    if ogm.sequence_number > node.OGMs_position[ogm.originator][0]:
                        #print(f"\t[{node.name}] <- ({ogm.sequence_number},{ogm.origin_position_vect}) RECEIVED")
                        #print(f"\t[{node.name}] : {node.OGMs_position[ogm.originator]} (old)")
                        node.OGMs_position[ogm.originator] = (ogm.sequence_number, ogm.origin_position_vect)
                        #print(f"\t[{node.name}] Aggiornato: {node.OGMs_position[ogm.originator]} (new)")
                #print("-"*10)
  

            # ! Fase di redistribuzione
            if type(node) == Observer:
                # Sto analizzando un Observer
                for ap in globals.global_access_point:
                    ap.OGMs_NP.append(ogm.clone_for_forwarding(node.name))
            else:
                # Sto analizzando un Satellite normale
                for neighbor in node.neighbors.keys():
                    # Per ogni vicino
                    if neighbor.name == ogm.sender:    # Se è il vicino che mi ha mandato questo pacchetto non lo mando
                        continue
                    else:
                        proximity = get_orbit_proximity(node.get_satellite(), neighbor.get_satellite(), t)
                        failure_prob = transmission_failure_probability(proximity)
                        value = round(random.uniform(0, 1), 2)
                        
                        if value > failure_prob:
                            # Spedisco il pacchetto
                            neighbor.OGMs_NP.append(ogm.clone_for_forwarding(node.name))
        node.OGMs = []

        print_progress_bar(i, total)


    # ! OGMs_NP -> OGMs
    for obj in ogm_map:
        obj.OGMs = obj.OGMs_NP.copy()
        obj.OGMs_NP = []

    # ! Pulizia della History
    print("\t| Cleaning History")
    for obj in ogm_map:
        # Calcolo quanto siamo fuori dimensione nella history ed eliminiamo i primi che sono entrati
        if type(obj) != Observer:
            out_dim = len(obj.OGMs_History) - obj.OGMs_History_dim
            if out_dim > 0:
                for i in range(out_dim):

                    # ! Pulizia OrderedDict
                    key, value_ogm_dict = obj.OGMs_History.popitem(last=False)                   # Rimuove il più vecchio
                    
                    obj.ogm_table[value_ogm_dict['originator']][value_ogm_dict['sender']] -= 1    # Puliamo la table
                    if obj.ogm_table[value_ogm_dict['originator']][value_ogm_dict['sender']] == 0:
                        del obj.ogm_table[value_ogm_dict['originator']][value_ogm_dict['sender']]

                    if len(obj.ogm_table[value_ogm_dict['originator']]) == 0:
                        del obj.ogm_table[value_ogm_dict['originator']]




    # ! Salvataggio informazioni table
    ogm_tables_snapshot = {
        satellite.name: satellite.ogm_table
        for satellite in ogm_map
        if type(satellite) != Observer
    }

    # $ Salvataggio informazioni posizioni
    ogm_position_dict = {
        satellite.name: satellite.OGMs_position
        for satellite in ogm_map
        if not isinstance(satellite, Observer)
    }


    # print("Checking Position Vectors")
    # for n, v in ogm_position_dict.items():
    #     print(f"{n} : {len(v)}")
    #     if not v:
    #         print(f"{n} ha un dizionario delle posizioni vuoto!")
            

    return ogm_tables_snapshot, ogm_position_dict

def saveInfoInFile(file ,value_dictionary, N_config):
    
    
    try:
        with open(file, "r") as f:
            print("file loaded.\n")
            data = json.load(f)
    except Exception as e:
        print(f"Error loading configuration file: {e}")
        data = {}

    # Scrivo la nuova configurazione
    data[N_config] = value_dictionary

    with open(file, "w") as f:
        json.dump(data, f, indent=4)



def transmission_failure_probability(distance):
    # Probabilità di fallimento cresce linearmente con la distanza
    return round(min(1.0, distance / config["Laser_Communication_Range"]), 2)


def print_dict(d, level=0):
    indent = '\t' * level

    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, (dict, list)):
                print(f"{indent}{key}:")
                print_dict(value, level + 1)
            else:
                print(f"{indent}{key}:\t{value}")
    elif isinstance(d, list):
        for i, item in enumerate(d):
            if isinstance(item, (dict, list)):
                print(f"{indent}[{i}]:")
                print_dict(item, level + 1)
            else:
                print(f"{indent}[{i}]:\t{item}")
    else:
        print(f"{indent}{d}")


def create_ogm(obj, origin_position_vect):
    """
    Crea e invia un nuovo OGM (Originator Generated Message) ai nodi vicini.

    L'OGM include informazioni come TTL, numero di sequenza e un identificatore unico.
    Aggiorna il contatore di sequenza e registra l'OGM creato.

    Returns:
        Ogm: L'istanza del nuovo OGM creato.
    """

    ogm = Ogm(
        originator = obj.name,
        sender = obj.name,
        origin_position_vect = origin_position_vect,
        ttl = 15,
        sequence_number = obj.ogm_sequence
    )

    obj.ogm_sequence += 1          # Aumento la sequence del server
    obj.OGMs.append(ogm)           # Lo inserisco nella lista degli OGM da processare in questo server



def periodic_recall_Routing_monitor(env, interval = 1):
    """
    Questa funzione dovrà scorrere costantemente tutti i task dentro
    la lista dei globali, e costantemente spingerli verso la destinazione.
    """
    while True:
        for node in globals.edge_servers:
            node.forward_packet()    # Eseguiamo il forwarding
        yield env.timeout(interval)

























