# Variabili globali per i server
initial_server_counter = {}  # Tiene traccia dei task inizializzati su ogni server
different_server_counter = {}  # Tiene traccia dei task inoltrati a server diversi
other_server_counter = {}  # Tiene traccia di altre metriche per i server
sorted_servers = {}  # Server ordinati in base a criteri specifici

# Variabili per la simulazione
transfer_time = {}  # Tempo di trasferimento per task tra server
#hop = 0  # Numero di salti (hop) per ogni task

# Lista globale degli access point
global_access_point = []  # Access point globali (copiati dagli edge servers)

# Lista globale dei server
global_edge_servers = []  # Lista completa degli edge servers creati
