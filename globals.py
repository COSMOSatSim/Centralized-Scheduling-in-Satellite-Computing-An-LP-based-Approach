import threading, json

# Variabili globali per i server
initial_server_counter = {}     # Tiene traccia dei task inizializzati su ogni server
different_server_counter = {}   # Tiene traccia dei task inoltrati a server diversi
other_server_counter = {}       # Tiene traccia di altre metriche per i server

global_access_point = []    # Lista degli access point globali
next_server_index = 0       # Indice del prossimo server a cui inviare un task

config_index = 0            # Indice che indica la configurazione corrente

edge_servers = []           # Lista dei server globali totali
edge_servers_topology = []  # Edge Servers nella topologia nella configurazione 

tasks = []                  # Lista di task completate in corso di elaborazione

observer = None
instant_in_configuration = None 

lock_access_edge_servers_topology = threading.Lock()  # Meccanismo di lock