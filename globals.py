# Variabili globali per i server
initial_server_counter = {}     # Tiene traccia dei task inizializzati su ogni server
different_server_counter = {}   # Tiene traccia dei task inoltrati a server diversi
other_server_counter = {}       # Tiene traccia di altre metriche per i server

global_access_point = []    # Lista degli access point globali
next_server_index = 0       # Indice del prossimo server a cui inviare un task

config_index = 0            # Indice che indica la configurazione corrente

edge_servers = []           # Lista dei server globali
