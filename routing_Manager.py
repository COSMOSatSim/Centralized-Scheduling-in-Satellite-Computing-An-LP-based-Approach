import random
import json
from user_based_topology import get_orbit_proximity

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

def manage_ogm(topology, t):

    #! Ogni satellite manda un OGM
    for sat in topology:
        sat.create_ogm()

    # ! Processiamo gli OGM per ogni Satellite considerando i suoi Vicini
    for sat in topology:
        for ogm in sat.OGMs:
            
            # $ BATMAN TABLE
            if ogm.ogm_id in sat.OGMs_History or ogm.ttl == 0:                      # Il pacchetto è stato già visionato o è scaduto
                continue

            sat.OGMs_History.append(ogm.ogm_id)                                     # Salvo il pacchetto

            # Se l'ORIGINATOR non è nella mia BATMAN Table, lo salvo
            if ogm.originator != sat.name:                                          # Non mi salvo i pacchetti che riguardano questo server
                if ogm.originator not in sat.ogm_table:
                    sat.ogm_table[ogm.originator] = {}

                # Aggiorno la Table
                if ogm.sender not in sat.ogm_table[ogm.originator]:
                    sat.ogm_table[ogm.originator][ogm.sender] = 1
                sat.ogm_table[ogm.originator][ogm.sender] += 1
            
            for n in sat.neighbors.keys():
                proximity = get_orbit_proximity(sat.get_satellite(), n.get_satellite(), t)
                failure_prob = transmission_failure_probability(proximity)
                num = round(random.uniform(0, 1), 2)
                #print(f"{sat.name}-{n.name} : d = {proximity}\t| num {num} > f{failure_prob}")
                if num > failure_prob:
                    #print(f"\t\t {sat.name} sending packet to {n.name}")
                    # Prendo il pacchetto e lo mando al nuovo vicino
                    
                    n.OGMs_NP.append(ogm.clone_for_forwarding(sat.name))
                    #[print(f"{n.name} OGMs_NP : {t}") for t in n.OGMs_NP]

        sat.OGMs = []                                                               # Pulizia dei pacchetti processati

    # ! Per ogni satellite OGMs_NP -> OGMs
    for sat in topology:
        if sat.OGMs_NP:                                                             # Se c'è qualcosa nella lista dei Non Processati
            sat.OGMs = sat.OGMs_NP.copy()
            sat.OGMs_NP = []


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