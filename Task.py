import json5, csv
import globals

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)
try:
    with open('img_resolution.json5') as resolution_file:
        # Carica il config completo per usarlo come riferimento
        RESOLUTION_CONFIG = json5.load(resolution_file)["TASK_GENERATOR_PARAMS"]
except FileNotFoundError:
    print("ATTENZIONE: File 'img_resolution.json5' non trovato.")
    RESOLUTION_CONFIG = {}

class Task:

    def __init__(self, task_id: int, current_node: str, dest_node: str, routingInitTime, task_type, image_size):

        self.id = task_id  
        self.ttl = 20                           # Time to live
        self.hop = 0                            # num_hop
        self.arrived = False                    # Arrived Flag                                        
        self.routingInitTime = routingInitTime  # Tempo di partenza
        self.routingEndTime = None              # Tempo di fine
        self.label = 'ON_SIMULATION'            # Failure Label 

        # PARAMETRI DEL TASK (ora puliti)
        self.task_type = task_type  # Es: "CPU_Intensive"
        self.weight = image_size  # Dimensione Immagine (MB)

        self.current_node = current_node        # Server sul quale si trova
        self.dest_node = dest_node              # Nodo di destinazione

        #self.visited: set[str] = {current_node} # Set Server precedente
        self.visited = set()                    # Set Server precedente
        self.visited.add(current_node)                # Aggiungo il primo server (il nome!)

        self.algorithms_used = {}               # Dizionario degli algoritmi utilizzati

        self.hop_History = [current_node]             # Lista di satelliti sui quali sono stato



    def __str__(self):
        """
        String representation of the Task object.
        :return: String representation of the Task object.
        """
        lista = []
        for s in self.hop_History:
            try:
                lista.append(s.name)
            except AttributeError:
                lista.append(s)  # Se è già una stringa

        return f"|HISTORY:{lista}\t|CURRENT:{self.current_node}\t|TTL:{self.ttl}|Hop:{self.hop}"

    def add_algorithm(self, algo_name: str):
        """Incrementa il contatore per l'algoritmo usato"""
        if algo_name not in self.algorithms_used:
            self.algorithms_used[algo_name] = 0
        self.algorithms_used[algo_name] += 1

def get_algo_percentages(t):
    """
    Calcola le percentuali di utilizzo degli algoritmi per un Task.
    Ritorna un dizionario {algoritmo: percentuale}.
    """
    algo_perc = {}
    total = sum(t.algorithms_used.values())
    if total > 0:
        for algo, count in t.algorithms_used.items():
            algo_perc[algo] = round((count / total) * 100, 2)
    return algo_perc  # se non ci sono algoritmi rimane {}

def generate_Tasks_Status(csv_filename):
    """
        Questa funzione salva in un file CSV le informazioni sui Task
    """
    
    total_tasks = []
    print(f"TASK GLOBALI {len(globals.gbl_tasks)} \n",)
    
    for t in globals.gbl_tasks:
        # Se il task ha un tempo di fine routing, calcola la durata e arrotonda i valori
        if t.routingEndTime is not None:
            durata = round(t.routingEndTime - t.routingInitTime, 2)
            routing_end = round(t.routingEndTime, 2)
        else:
            durata = None
            routing_end = None

        # Crea una lista con le informazioni principali del task
        elem = [
            t.id,                # ID del task
            t.current_node,      # Nodo corrente
            t.hop,               # Numero di hop
            t.label,             # Etichetta di stato
            t.task_type,        # Categoria di task_type
            round(t.routingInitTime, 2),  # Tempo di inizio routing arrotondato
            routing_end,         # Tempo di fine routing arrotondato (se presente)
            durata,              # Durata del routing (se presente)
            get_algo_percentages(t)
        ]
        # Aggiungi le informazioni del task alla lista totale
        total_tasks.append(elem)
    
    # FASE DI SORTING
    total_tasks.sort(key=lambda x: x[0])

    # FASE DI STAMPA FORMATTATA
    print(f"TOT TASK IN ROUTING SYS: {len(total_tasks)}\n")
    print(" id     | CurrentNode          | Hop | Label           | Task Type              | Start Routing (s) | End Routing (s) | duration      | Algorithms")
    for elem in total_tasks:
        id_, current_node, hop, label, task_type, routing_start, routing_end, durata, algorithms = elem
        algorithms_str = ', '.join([f"{k}:{v}%" for k, v in algorithms.items()]) if algorithms else "-"
        
        # Colora di verde se routing_start e routing_end sono entrambi presenti
        if routing_start is not None and routing_end is not None:
            color_start = "\033[92m"  # Verde
            color_end = "\033[0m"     # Reset
        else:
            color_start = ""
            color_end = ""
        
        print(f"{color_start} {id_:<6} | {str(current_node):<20} | {hop:<3} | {label:<15} | {task_type:<22} | {routing_start:<17} | {str(routing_end):<15} | {str(durata):<13} | {algorithms_str}{color_end}")
   
    print()  # Riga vuota alla fine per separare dall'output successivo

    # FASE DI SCRITTURA CSV
    headers = [
        "TaskID", "CurrentNode", "Hop", "Label", "TaskType",
        "RoutingInitTime", "RoutingEndTime", "Duration", "Algorithms"
    ]

    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)  # intestazioni
        writer.writerows(total_tasks)

    print(f"Task info saved to: {csv_filename}")