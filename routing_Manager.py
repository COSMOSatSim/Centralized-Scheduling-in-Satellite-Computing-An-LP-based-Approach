import random
import json, json5
from packet import Mode, Packet
from user_based_topology import get_orbit_proximity, getSystemFromSat
from Ogm import Ogm
from Observer import Observer
import globals
import sys
import os

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

DSR = config["Routing_algorithm"]["DSR"]
# Leggi il file di configurazione JSON (Contiene le configurazioni salvate)
# try:
#     with open("data/configurations.json", "r") as f:
#         print("Configuration file loaded.\n")
#         data_configurations = json.load(f)
# except Exception as e:
#     print(f"Error loading configuration file: {e}")


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
        #print(f"{node.name} | {node.getPositionVector(t)} | AP: {node.is_acc_point}")
        create_ogm(node, node.getPositionVector(t), node.is_acc_point)

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
                    node.OGMs_position[ogm.originator] = (ogm.sequence_number, ogm.origin_position_vect, ogm.is_AP)
                    #print(f"\tsaved! : {node.OGMs_position[ogm.originator]}")
                else:
                    # $ Controllo se aggiornare il valore 
                    if ogm.sequence_number > node.OGMs_position[ogm.originator][0]:
                        #print(f"\t[{node.name}] <- ({ogm.sequence_number},{ogm.origin_position_vect}) RECEIVED")
                        #print(f"\t[{node.name}] : {node.OGMs_position[ogm.originator]} (old)")
                        node.OGMs_position[ogm.originator] = (ogm.sequence_number, ogm.origin_position_vect, ogm.is_AP)
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

    return ogm_tables_snapshot, ogm_position_dict

def saveInfoInFile(file ,value_dictionary, N_config):
    
    
    try:
        with open(file, "r") as f:
            print(f"file {file} loaded.\n")
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


def create_ogm(obj, origin_position_vect, is_AP):
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
        is_AP = is_AP,
        ttl = 15,
        sequence_number = obj.ogm_sequence
    )

    obj.ogm_sequence += 1          # Aumento la sequence del server
    obj.OGMs.append(ogm)           # Lo inserisco nella lista degli OGM da processare in questo server


def routeDiscovery(source, task, neighbors):
    """
    Questa funzione prende un task è fa partire un processo 
    di route request fino alla destinazione.
    """
    task.routeRequestIst = source.env.now    # Save timestamp
    
    for node in neighbors:

        pkt_ID = source.name+"_"+str(source.packets_seq)
        pkt = Packet(pkt_ID, task.id, task.current_node, task.dest_node, Mode.ROUTE_DISCOVERY)
        
        node.packets.append(pkt)
        pkt.current_node = node.name
        
        source.pkt_history.append(pkt_ID)
        source.packets_seq += 1
        globals.gbl_packet.append(pkt)
        #print(f"[{pkt_ID}] {task.current_node} --> {node.name}")

def getNextNode(neighbors, nextHopName):

    neighbor = next((n for n in neighbors if n.name == nextHopName), None)
    return neighbor

def startRouteReply(source, neighbors, pkt: Packet):
    print(f"AVVIO FASE DI ROUTE REPLY")
    pkt.mode = Mode.ROUTE_REPLY
    last_node = pkt.node_stack.pop()
    
    nextHop = getNextNode(neighbors, last_node)
    
    if nextHop:
        print(f"\t[START-RREPLY] Task {pkt.taskID} pktID {pkt.id}\t| {source.name} -> {nextHop.name}")
        nextHop.packets.append(pkt)
    else:
        #! ROUTE ERROR?
        print(f"\tERROR ROUTE ??\n{source.name} tryed to send {pkt.taskID} pkt to one of:")
        [print(n.name) for n in neighbors]
        print(f"pkt said the last_node was {last_node}")
        print(f"{source.name} fails to send pktID{pkt.id} of taskID {pkt.taskID}")
    




def sendPkt(source, dest, pkt:Packet):
    if dest == None:
        sys.exit("ERRORE: destination = None")
    
    newPkt = pkt.duplicate()

    newPkt.current_node = dest.name

    newPkt.visited.add(source.name)         
    newPkt.hop_History.append(source.name)
    newPkt.node_stack.append(source.name)

    dest.packets.append(newPkt)



def forward_packet_DSR(env, node):
    
    # ? Gestione dei vicini 
    neighbors = None
    if node.name != 'OBS':
        neighbors = list(node.neighbors.keys()) # Vicini Nodo Normale
        if node.is_acc_point:
            neighbors += [globals.observer]     # Vicini Nodo AP
    else:
        neighbors = globals.global_access_point # Vicini Observer


    for pkt in node.packets[:]:
        if pkt.mode == Mode.ROUTE_DISCOVERY:
            if pkt.id not in node.pkt_history:
                if pkt.dest == node.name:
                    startRouteReply(node, neighbors, pkt)
                else:
                    print(f"[RDISCOVERY] pktID:{pkt.id} taskID.{pkt.taskID} on {node.name}")
                    for n in neighbors:
                        sendPkt(node, n, pkt)
            
            # Nella history inserisco i DISCOVERY
            node.pkt_history.append(pkt.id)

        elif pkt.mode == Mode.ROUTE_REPLY:

            if pkt.source == node.name:
                # Se la source di questo pacchetto sono io
                print(f"CONSEGNATO [{pkt.id}] TASK:{pkt.taskID}")
                
                #! Salviamo l'informazione che ci è giunta
                if pkt.taskID not in node.routes:
                    node.routes[pkt.taskID] = []
                
                if pkt.hop_History not in node.routes[pkt.taskID]:
                    node.routes[pkt.taskID].append(pkt.hop_History)

                # Rendiamo il Task Spedibile
                task = next((t for t in node.tasks if t.id == pkt.taskID), None)
                task.RouteReply = True
                
            else:
                # Lo mando al prossimo nodo della rete
                lastNodeStack = pkt.node_stack.pop()
                nextNode = getNextNode(neighbors,lastNodeStack)
                sendPkt(node, nextNode, pkt)

        node.packets.remove(pkt)

    # ! Route Request
    for task in node.tasks: 
        if not task.routeRequestIst:
            routeDiscovery(node, task, neighbors)
            print(f"\t[RDISCOVERY] Task {task.id}\t| {node.name} start routeRequest: {round(task.routeRequestIst,4)} ")
        else:
            if task.RouteReply:
                # Abbiamo ricevuto un Pacchetto Reply

                sys.exit("Possiamo iniziare il trasferimento")
            else:
                # Controllo che non sia scaduto il suo tempo.
                if env.now - task.routeRequestIst > 2:
                    print(f"Route request for task {task.id} expired (timestamp: {task.routeRequestIst}, now: {env.now})")
                    # Puoi aggiungere qui la logica per gestire la scadenza, ad esempio rimuovere il task o ritentare
                    
                    if task.id in node.routes:
                        print(f"{node.routes[task.id]}")
                    else:
                        print(f"Nessuna informazione di routing per il task {task.id}")

                    print("\n\n")
                    [print(p) for p in globals.gbl_packet]
                    sys.exit(f"BRO IL TEMPO é SCADUPTO DEL TASK: {task.id}")



















# | Secondi | Millisecondi |
# | ------- | ------------ |
# | 1       | 1000 ms      |
# | 0,5     | 500 ms       |
# | 0,1     | 100 ms       |
# | 0,01    | 10 ms        |
# | 0,001   | 1 ms         |

def periodic_recall_Routing_monitor(env, interval = 0.005):
    """
    Questa funzione dovrà scorrere costantemente tutti i task dentro
    la lista dei globali, e costantemente spingerli verso la destinazione.
    """
    while True:
        print(f"env time: {env.now}")
        for node in globals.edge_servers:
            yield from node.forward_packet(env)    # Eseguiamo il forwarding
            if DSR:
                forward_packet_DSR(env, globals.observer)

        # TODO DIMINUIRE QUESTO VALORE PER rendere il routing più veloce
        yield env.timeout(interval)

























