import random, json, json5, csv
import globals
# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)
with open('img_resolution.json') as resolution_file:
    resolution = json.load(resolution_file)

class Task:

    def __init__(self, task_id: int, current_node: str, dest_node: str, routingInitTime, category, resolution):

        self.id = task_id  
        self.ttl = 20                           # Time to live
        self.hop = 0                            # num_hop
        self.arrived = False                    # Arrived Flag                                        
        self.routingInitTime = routingInitTime  # Tempo di partenza
        self.routingEndTime = None              # Tempo di fine
        self.label = 'ON_SIMULATION'            # Failure Label 
        
        self.resolution = category              # Categoria Risoluzione Immagine
        self.weight = resolution                # Dimensione Immagine

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
            lista.append(s.name)

        return f"|HISTORY:{lista}\t|CURRENT:{self.current_server}\t|TTL:{self.ttl}|Hop:{self.hop}"

    def add_algorithm(self, algo_name: str):
        """Incrementa il contatore per l'algoritmo usato"""
        if algo_name not in self.algorithms_used:
            self.algorithms_used[algo_name] = 0
        self.algorithms_used[algo_name] += 1

def assign_resolution(required_ram, required_disk):
    
    # Normalizzazione pesata
    norm_ram = required_ram / config["required_ram"]["max"]
    norm_disk = required_disk / config["required_disk"]["max"]
    weight = 0.5 * norm_ram + 0.5 * norm_disk
    
    # Mappatura del peso a una categoria
    if weight <= 0.25:
        category = "Low"
    elif weight <= 0.5:
        category = "Medium"
    elif weight <= 0.75:
        category = "High"
    else:
        category = "Very High"

    min_value = resolution[category]["min"]
    max_value = resolution[category]["max"]

    min_byte = dim_to_Byte(min_value["dim"], min_value["value"])
    max_byte = dim_to_Byte(max_value["dim"], max_value["value"])

    resolution_value = random.randint(min_byte, max_byte)   # Valore di Ritorno in Byte
    return category, resolution_value

def dim_to_Byte(dim, value):
    """
    Converts megabytes (MB) or kilobytes (KB) to bytes.
    :param dim: Dimension unit ('MB' or 'KB').
    :param value: Value in the given unit.
    :return: Value in bytes.
    """
    if dim == 'MB': 
        return int(value * 1000 * 1000)
    if dim == 'KB':
        return int(value * 1000)

def byte_to_dim(byte_value):
    """
    Converts bytes to the most suitable unit (MB, KB, or B) and returns a formatted string.
    :param byte_value: Value in bytes.
    :return: String in the format "value unit" (e.g., "2.5 MB").
    """
    if byte_value >= 1000 * 1000:
        value = byte_value / (1000 * 1000)
        unit = 'MB'
    elif byte_value >= 1000:
        value = byte_value / 1000
        unit = 'KB'
    else:
        value = byte_value
        unit = 'B'
    return f"{value:.2f} {unit}"

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

def colorize(text: str, color: str) -> str:
    """
    Colora una stringa con i codici ANSI per il terminale.

    Args:
        text (str): La stringa da colorare.
        color (str): Il colore (es: "red", "green", "yellow", "blue", "magenta", "cyan", "white").

    Returns:
        str: La stringa colorata con codici ANSI.
    """
    colors = {
        "black": "\033[30m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "reset": "\033[0m",
        "orange": "\033[33m"  
    }

    start = colors.get(color.lower(), "")
    end = colors["reset"] if start else ""
    return f"{start}{text}{end}"




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
            t.resolution,        # Categoria di risoluzione
            round(t.routingInitTime, 2),  # Tempo di inizio routing arrotondato
            routing_end,         # Tempo di fine routing arrotondato (se presente)
            durata,              # Durata del routing (se presente)
            get_algo_percentages(t)
        ]
        # Aggiungi le informazioni del task alla lista totale
        total_tasks.append(elem)
    
    # FASE DI SORTING
    total_tasks.sort(key=lambda x: x[0])

    TArr, TExp, Tsob, ToS = 0,0,0,0

    # FASE DI STAMPA FORMATTATA
    print(f"TOT TASK IN ROUTING SYS: {len(total_tasks)}\n")
    print(" id     | CurrentNode          | Hop | Label           | Resolution    | Start Routing (s) | End Routing (s) | duration      | Algorithms")
    for elem in total_tasks:
        id_, current_node, hop, label, resolution_cat, routing_start, routing_end, durata, algorithms = elem
        algorithms_str = ', '.join([f"{k}:{v}%" for k, v in algorithms.items()]) if algorithms else "-"
        
        row = (
            f"{id_:<6} | {str(current_node):<20} | {hop:<3} | {label:<15} | "
            f"{resolution_cat:<13} | {routing_start:<17} | {str(routing_end):<15} | "
            f"{str(durata):<13} | {algorithms_str}"
        )

        if label == "TASK_ARRIVED":
            row = colorize(row, "green")
            TArr += 1
        elif label == "TTL_EXPIRED":
            row = colorize(row, "red")
            TExp += 1
        elif label == "SEN_OUT_OF_BUFF":
            row = colorize(row, "orange")
            Tsob += 1
        else:
            ToS += 1
        
        print(row)
            
    print()  # Riga vuota alla fine per separare dall'output successivo

    # FASE DI SCRITTURA CSV
    headers = [
        "TaskID", "CurrentNode", "Hop", "Label", "Resolution",
        "RoutingInitTime", "RoutingEndTime", "Duration", "Algorithms"
    ]

    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)  # intestazioni
        writer.writerows(total_tasks)

    print(f"Task info saved to: {csv_filename}")
    print(f"TASK GLOBALI {len(globals.gbl_tasks)} \n",)
    print(f"TASK CONSEGNATI:{TArr} EXP:{TExp} SOB:{Tsob} OnSim:{ToS}")