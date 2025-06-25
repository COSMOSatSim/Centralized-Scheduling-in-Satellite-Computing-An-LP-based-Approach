class Task:

    def __init__(self, task_id: int, current_node: str, dest_node: str):

        
        self.id = task_id  
        self.ttl = 10                           # Time to live
        self.hop = 0                            # num_hop
        self.arrived = False                    # Arrived Flag                                        

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

