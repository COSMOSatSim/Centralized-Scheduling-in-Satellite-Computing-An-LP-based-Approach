import random, json
# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

class Task:

    def __init__(self, task_id: int, current_node: str, dest_node: str):

        self.id = task_id  
        self.ttl = 30                           # Time to live
        self.hop = 0                            # num_hop
        self.arrived = False                    # Arrived Flag                                        

        # Scegli una risoluzione casuale tra quelle disponibili
        resolution_key = random.choice(list(config["Resolution"].keys()))
        self.resolution = resolution_key
        # Assegna un peso casuale tra il minimo e il massimo per la risoluzione scelta
        self.weight = random.randint(config["Resolution"][resolution_key]["min"], config["Resolution"][resolution_key]["max"])

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

