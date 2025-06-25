import json
import logging
import simpy
from skyfield.api import EarthSatellite
from collections import OrderedDict
from user_based_topology import getSystemFromSat
from Task import Task
import sys 

import globals


# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

def setup_logging(log_file_path):
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG)

total_time = 0  # Imposta il valore iniziale di total_time

class EdgeServer:
    def __init__(self, env, name, satellite: EarthSatellite, orbitalSunset, is_acc_point, elev_angle):
        '''
                Initialize an EdgeServer instance.

                :param env: Simulation environment.
                :param name: Name of the edge server.
        '''
        self.env = env
        self.name = name
        self.satellite = satellite
        self.orbitalSunset = orbitalSunset
        self.is_acc_point = is_acc_point
        self.elev_angle = elev_angle
        self.neighbors = {}
        self.latency = {}
        self.bandwidth = {}
        self.process_queue = simpy.PriorityResource(env, capacity=5)  # Initialize a PriorityResource for the task queue
        self.server_queue = []
        self.utility_value = 0  # Valore iniziale di utilità del server
        self.completed_tasks = []

        self.tasks = []              # Lista task da Spedire

        self.OGMs_position = {}     # Dizionario delle posizioni dei vicini 

        self.ogm_sequence = 0           # Contatore OGM emessi
        self.OGMs = []                  # OGM to process
        self.OGMs_NP = []               # OGM received and Not-Processed
        self.ogm_table = {}             # OGMs Table {'originator': { 'neighbor': 'count'
        
        self.OGMs_History = OrderedDict()# Lista OGM visionati in passato (FIFO)
        self.OGMs_History_dim = 2046     # Limite dimensione History OGM 

    def task_completed(self, task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time, end_time,
                       execution_time, service_time, time_in_queue, selected_server, num_hops, lunghezza_coda,
                       original_TaskPriority, estimated_execution_time, transfer_time, utility, TMAX_exceeded, exec_after_set):
        '''
                Record completed tasks.

                :param task_id: ID of the completed task.
                :param task_priority: Priority of the completed task.
                :param arrival_time_system: Arrival time of the task in the system.
                :param arrival_time_task_queue: Arrival time of the task in the server queue.
                :param start_time: Start time of task execution.
                :param end_time: End time of task execution.
                :param execution_time: Execution time of the task.
                :param service_time: Service time of the task.
                :param time_in_queue: Time spent by the task in the queue.
                :param selected_server: Server selected for task execution.
                :param num_hops: Number of hops to reach the selected server.
                :param lunghezza_coda: Length of the server queue.

                :return: None
                '''
        task = Task(task_id, self.name, globals.observer.name)  # Creo la task
        self.tasks.append(task)

        #exec_after_set = False # booleano che indica se il task è stato eseguito quando il satellite è tramontato
        if self.elev_angle < config["Phi_max"]:
            exec_after_set = True

        #print(f"Completamento Task {task_id}: Priority {task_priority}, Start {start_time}, End {end_time}, {self.name} Tramontato: {exec_after_set}")

        self.completed_tasks.append((task_id, task_priority, arrival_time_system, arrival_time_task_queue, start_time,
                                     end_time, execution_time, service_time, time_in_queue, selected_server, num_hops,
                                     lunghezza_coda, original_TaskPriority, estimated_execution_time, transfer_time, utility, TMAX_exceeded, exec_after_set))

    def add_neighbor(self, neighbor_server, hop_count, latency, bandwidth):
        '''
                Add a neighbor server with its hop count and latency.

                :param neighbor_server: Neighbor server to add.
                :param hop_count: Number of hops to reach the neighbor server.
                :param latency: Latency to the neighbor server.

                :return: None
                '''
        self.neighbors[neighbor_server] = hop_count
        self.latency[neighbor_server] = latency
        self.bandwidth[neighbor_server] = bandwidth

    def update_neighbors(self, new_neighbors, new_latency, new_bandwidth):
        """
        Update the neighbors, latency, and bandwidth of the edge server.

        :param new_neighbors: Dictionary of new neighbors and their hop counts.
        :param new_latency: Dictionary of new latencies to the neighbors.
        :param new_bandwidth: Dictionary of new bandwidths to the neighbors.

        :return: None
        """
        self.neighbors = new_neighbors
        self.latency = new_latency
        self.bandwidth = new_bandwidth

    def get_neighbors(self):
        '''
        Get neighbor servers at a distance of one hop.

        :return: List of neighbor servers at a distance of one hop.
        '''
        neighbors_at_distance_one = []

        for neighbor, hop_count in self.neighbors.items():
            if hop_count <= 1:
                neighbors_at_distance_one.append(neighbor)

        return neighbors_at_distance_one

    def get_satellite(self):
        return self.satellite

    def get_latency(self, neighbor_server):
        '''
        Get latency to a specific neighbor server.

        :param neighbor_server: Neighbor server to get the latency for.

        :return: Latency to the neighbor server.
        '''
        return self.latency.get(neighbor_server, None)

    def get_bandwidth(self, neighbor_server):
        '''
        Get bandwidth to a specific neighbor server.

        :param neighbor_server: Neighbor server to get the bandwidth for.

        :return: Bandwidth to the neighbor server.
        '''
        return self.bandwidth.get(neighbor_server, None)


    
    def __str__(self):
        return f"Satellite :{self.name} neighbor:({len(self.neighbors)})\n"

    def getPositionVector(self, t):
        """
        Questa funzione ritorna un vettore in 3 dimensioni,
        rappresenta la posizione del satellite in un determinato istante.
        """

        return getSystemFromSat(self.satellite, t, True).position.km.tolist()


    def batman_approach(self, t):

        # ! SE NON ARRIVATO, PRENDO IL VICINO CON NUMERO OGM MAGGIORE PER QUESTO PACCHETTO
        ogm_from_neighbors = self.ogm_table[t.dest_node]

        # Trova la key con il value maggiore
        if ogm_from_neighbors:
            if self.is_acc_point:
                sendTask(t, self, globals.observer)
                print(f"Zio è arrivato {t.id}")
            else:
                
                # Generiamo l'intersezione tra i vicini reali e quelli salvati nell'OGM_Table,
                # ESCLUDENDO i satelliti già visitati dal task.
                intersection = {
                    neighbor: ogm_from_neighbors[neighbor.name]
                    for neighbor in self.neighbors
                    if (
                        neighbor.name in ogm_from_neighbors
                        and neighbor.name not in t.visited      # nuovo filtro anti-loop
                    )
                }

                # Trova il Neighbor con il valore OGM più alto
                if intersection:                                       # evita ValueError se vuoto
                    max_neighbor, max_value = max(intersection.items(), key=lambda item: item[1])
                else:
                    max_neighbor, max_value = None, None

                if max_neighbor:
                    sendTask(t, self, max_neighbor)
                else:
                    # ! Capiamo perché questo pacchetto non può essere spedito
                    
                    print("!"*10)
                    print(f"{self.name} vuole mandare il Task {t.id}. Ma non ci sono vicini disponibili")
                    print("INFO SATELLITE:")
                    print(f"\t Angolo di Elevazione : {self.elev_angle}")
                    print(f"\t Orbital Sunset : {self.orbitalSunset}")
                    print(f"\t Numero vicini: {len(self.neighbors)}")
                    print(f"\t SITUAZIONE TABLE originator : {t.dest_node}")
                    [print(f"\t\t {n} : {v}") for n,v in self.ogm_table[t.dest_node].items()]
                    print("!"*10)
        else:
            print("No neighbors found in OGM table.")
            sys.exit("Nessun vicino disponibile")
                         



    def forward_packet_BATMAN(self):
        for t in self.tasks:

            if not t.arrived:

                print(f"CHECK {self.name} | Destination Task : {t.dest_node}")
                if t.dest_node in self.ogm_table:
                    self.batman_approach(t)
                else:
                    # ! Probabile applicazione Greedy
                    sys.exit("non è presente l' OGM nella table")





    def UpdateUtilityValue(self, env, estimated_execution_time, transfer_time, restart_time, download_time, server, task_priority):
        '''
        Aggiorna il valore di utilità del server in base ai task attualmente in coda e al carico richiesto.

        :param estimated_execution_time: CPU richiesta dal task.
        :param transfer_time: Tempo di trasferimento del contesto.
        :param restart_time: Tempo di riavvio del task.
        :param download_time: Tempo di download dell'immagine.
        :param task_priority: Priorità del task (1 = alta, 100 = bassa).
        :param server: Server su cui viene aggiornato il valore di utilità.

        :return: Nessun valore di ritorno, aggiorna l'attributo utility_value del server.
        '''
        # Ottiene la lista di task attualmente in coda nel server
        tasks_in_queue = list(server.server_queue)
        #  task_id, required_ram, required_disk, task_priority, arrival_time_system, estimated_execution_time, transfer_time, num_hops, arrival_time_task_queue, original_TaskPriority
        #     0            1          2           3               4                    5                        6              7             8                    9

        # Se ci sono task in coda, calcola i parametri di utilità
        if len(tasks_in_queue) > 0:
            # Calcola il numero di task che sono arrivati prima del tempo attuale (env.now)
            self.total_priority_in_queue = sum([1 for r in tasks_in_queue if r[4] < env.now])

            # Calcola il tempo di attesa totale dei task (waiting_time)
            self.waiting_time = sum([r[5] for r in tasks_in_queue if r[8] < env.now])

            # Calcola il tempo medio di servizio (AVG_service_time)
            self.AVG_service_time = self.waiting_time / self.total_priority_in_queue if self.total_priority_in_queue > 0 else 0

            # Conta il numero di task ad alta priorità nella coda
            num_high_priority = sum(1 for r in tasks_in_queue if r[3] == 1 and (env.now - 1) < r[8] <= (env.now))

            # Conta il numero di task a bassa priorità nella coda
            num_low_priority = sum(1 for r in tasks_in_queue if r[3] == 100 and (env.now - 1) < r[8] <= (env.now))

            # Calcola rho_l_ij (carico della bassa priorità)
            rho_l_ij = num_low_priority * self.AVG_service_time

            # Calcola rho_h_ij (carico dell'alta priorità)
            rho_h_ij = num_high_priority * self.AVG_service_time

            if rho_h_ij > 1:
                rho_h_ij = 0.99  # Se rho_h_ij è maggiore di 1, lo limitiamo a 0.99

            # Calcola il tempo di attesa per i task ad alta priorità (Th_ij)
            self.Th_ij = ((1 + rho_l_ij) * self.AVG_service_time) / (1 - rho_h_ij)

            # Calcola rho totale (somma di carico alta e bassa priorità)
            rho = rho_h_ij + rho_l_ij
            if rho > 1:
                rho = 0.99  # Limitiamo rho a 0.99 per evitare sovraccarichi

            # Calcola il tempo di attesa per i task a bassa priorità (Tl_ij)
            self.Tl_ij = ((1 - rho_h_ij * (1 - rho)) * self.AVG_service_time) / ((1 - rho_h_ij) * (1 - rho))

        # Se non ci sono task in coda, setta i valori di utilità a zero
        else:
            self.AVG_service_time = 0
            self.Th_ij = 0
            self.Tl_ij = 0
            self.waiting_time = 0

        # Calcola il tempo totale per trasferimento, riavvio e download
        total_time = transfer_time + restart_time + download_time

        # Penalizzazione per il tramonto del server
        if server.orbitalSunset is not None and server.orbitalSunset > 0:
            sunset_penalty = 1 / server.orbitalSunset  # Più è vicino al tramonto, più alto è il valore
        else:
            sunset_penalty = float('inf')  # Penalizzazione massima se il tramonto è imminente


        # Aggiorna il valore di utilità del server in base alla priorità del task
        if task_priority == 1:  # Task ad alta priorità
            self.utility_value = self.Th_ij + (estimated_execution_time) + total_time #+ sunset_penalty
        else:  # Task a bassa priorità
            self.utility_value = self.Th_ij + self.Tl_ij + (estimated_execution_time) + total_time #+ sunset_penalty




def sendTask(task, sender, receiver):
    """
    Transfers a task from a sender satellite to a receiver satellite, updating its state and attributes.

    Args:
        task (Task): The task object to be transferred. It contains attributes such as `hop`, `ttl`, 
                     `id`, `current_server`, and `satellite_destination`.
        sender (Satellite): The satellite currently holding the task. It must have a `remove_task` method.
        receiver (Satellite): The satellite to which the task is being sent. It must have an `add_task` method.

    Behavior:
        - Increments the `hop` count of the task by 1 to track the number of hops.
        - Decrements the `ttl` (time-to-live) of the task by 1 to reflect its remaining lifespan.
        - Removes the task from the sender using `sender.remove_task(task.id)`.
        - Adds the task to the receiver using `receiver.add_task(task)`.
        - Updates the `current_server` attribute of the task to the receiver.
        - Checks if the receiver is the task's `satellite_destination`. If so, marks the task as arrived by 
          setting `task.arrived` to `True`.
        - Logs the transfer operation in the format: "[task.id] sender.name -> receiver.name".

    Note:
        This function assumes that the `task`, `sender`, and `receiver` objects are properly defined and 
        implement the required attributes and methods.
    """
    if task.ttl > 0:
        
        task.hop += 1
        task.ttl -= 1   

        # Rimuoviamo il task dal Sender
        sender.tasks.remove(task)
        # Inviamo il task al Receiver
        receiver.tasks.append(task)
        # Modifichiamo le informazioni sul task
        task.current_server = receiver.name

        # ! USIAMO SOLO I NOMI E NON PRPRIO L'oggetto
        if task.dest_node == receiver.name:
            task.arrived = True

        task.hop_History.append(receiver.name)     # Aggiorno la History
        task.visited.add(receiver.name)            # Aggiorno i visitati
        print(f"[{task.id}] {sender.name} -> {receiver.name}")
    else:
        # Rimuoviamo il task
        print(f"[{task.id}] RIMOZIONE TASK DA {sender.name}, TTL finito")
        sender.tasks.remove(task)
    

