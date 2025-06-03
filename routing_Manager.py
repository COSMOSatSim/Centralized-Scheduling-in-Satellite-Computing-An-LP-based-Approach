import random
import json
from user_based_topology import get_orbit_proximity
from Ogm import Ogm
from Observer import Observer
import globals

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

def manage_ogm(ogm_map, t):

    #! Ogni oggetto manda un OGM
    for obj in ogm_map:            
        #obj.create_ogm()
        create_ogm(obj)

    # ! Processiamo gli OGM per ogni Satellite considerando i suoi Vicini
    for obj in ogm_map:
        for ogm in obj.OGMs:
            
            # $ BATMAN TABLE
            if ogm.ogm_id in obj.OGMs_History or ogm.ttl == 0:                      # Il pacchetto è stato già visionato o è scaduto
                continue

            obj.OGMs_History.append(ogm.ogm_id)                                     # Salvo il pacchetto

            # Se l'ORIGINATOR non è nella mia BATMAN Table, lo salvo
            if ogm.originator != obj.name:                                          # Non mi salvo i pacchetti che riguardano questo server
                if ogm.originator not in obj.ogm_table:
                    obj.ogm_table[ogm.originator] = {}

                # Aggiorno la Table
                if ogm.sender not in obj.ogm_table[ogm.originator]:
                    obj.ogm_table[ogm.originator][ogm.sender] = 1
                obj.ogm_table[ogm.originator][ogm.sender] += 1
            
            # ! Controllo delle connessioni con i vicini
            if type(obj) == Observer:
                #print("Riconosciuto Observer")
                for ap in globals.global_access_point:
                    # ? Gestione della probabilità di fallimento (??)
                    ap.OGMs_NP.append(ogm.clone_for_forwarding(obj.name))
            else:
                # Mando il messaggio prima a tutti i miei vicini
                for n in obj.neighbors.keys():
                    proximity = get_orbit_proximity(obj.get_satellite(), n.get_satellite(), t)
                    failure_prob = transmission_failure_probability(proximity)
                    num = round(random.uniform(0, 1), 2)
                    if num > failure_prob:
                        n.OGMs_NP.append(ogm.clone_for_forwarding(obj.name))
                # Se sono un Access point lo mando anche all'OBSERVER
                if obj in globals.global_access_point:
                    #print(f"Ho trovato un access point {obj.name}")
                    # ? Gestione delle probabilità di fallimento (??)
                   
                    #print(f"\t Controllo Observer:")
                    #print(f"Prima observer OGMs_NP: {len(globals.observer.OGMs_NP)}")
                    globals.observer.OGMs_NP.append(ogm.clone_for_forwarding(obj.name))
                    #print(f"DOPO observer OGMs_NP: {len(globals.observer.OGMs_NP)}")
        obj.OGMs = []                                                               # Pulizia dei pacchetti processati

    # ! Per ogni oggetto OGMs_NP -> OGMs
    for obj in ogm_map:
        if obj.OGMs_NP:                                                             # Se c'è qualcosa nella lista dei Non Processati
            obj.OGMs = obj.OGMs_NP.copy()
            obj.OGMs_NP = []

def periodic_recall_Routing_monitor(env, observer):
    while True:
        yield env.timeout(config["OGMs_Interval_seconds"])

        ogm_map = [observer] + globals.edge_servers     # Aggiungo l'elemento alla lista

        manage_ogm(ogm_map, globals.instant_in_configuration)

        print("-"*20,"CHECK OGM MANAGER")
        print(f"{globals.edge_servers[0].name}")
        print_dict(globals.edge_servers[0].ogm_table)
        print("-"*20)

        


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


def create_ogm(obj):
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
        ttl = 10,
        sequence_number = obj.ogm_sequence
    )

    obj.ogm_sequence += 1          # Aumento la sequence del server
    obj.OGMs.append(ogm)           # Lo inserisco nella lista degli OGM da processare in questo server
