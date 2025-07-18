import random, json
# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)
with open('img_resolution.json') as resolution_file:
    resolution = json.load(resolution_file)

class Task:

    def __init__(self, task_id: int, current_node: str, dest_node: str, routingInitTime, category, resolution):

        self.id = task_id  
        self.ttl = 30                           # Time to live
        self.hop = 0                            # num_hop
        self.arrived = False                    # Arrived Flag                                        
        self.routingInitTime = routingInitTime  # Tempo di partenza
        self.routingEndTime = None              # Tempo di fine

        
        self.resolution = category              # Categoria Risoluzione Immagine
        self.weight = resolution                # Dimensione Immagine

        self.current_node = current_node        # Server sul quale si trova
        self.dest_node = dest_node              # Nodo di destinazione

        #self.visited: set[str] = {current_node} # Set Server precedente
        self.visited = set()                    # Set Server precedente
        self.visited.add(current_node)                # Aggiungo il primo server (il nome!)

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

    resolution_value = random.randint(min_byte, max_byte)
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