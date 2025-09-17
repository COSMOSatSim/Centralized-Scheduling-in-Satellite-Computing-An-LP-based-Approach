
import globals
from collections import OrderedDict
from skyfield.api import wgs84

import sys
import json5
from Task import byte_to_dim 

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

class ObserverMeta(type):
    """
    Singleton instance of an Observer
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):

        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    

class Observer(metaclass = ObserverMeta):
    def __init__(self, env, pos):
        
        self.env = env
        self.position = pos     # Posizione dell'observers

        self.name = 'OBS' 
        self.is_acc_point = False
        
        self.tasks = []
        self.OGMs_position = {}
        self.ogm_sequence = 0               # Contatore OGM emessi
        self.OGMs = []                      # OGM to process
        self.OGMs_NP = []                   # OGM recived and Not-Processed
        self.ogm_table = {}                 # OGMs Table {'originator': [ 'neighbor': 'count']
        self.OGMs_History = OrderedDict()   # Lista OGM visionati in passato
    
    
    def getLocation(self, altitude = config["sphere_altitude_km"] ,location = config["simulation_location"]):
        if location in config["locations"]:
            lat = config["locations"][location]["lat"]
            lon = config["locations"][location]["lon"]
            #print(f"User Location: {location} ({lat},{lon}) With Altitude ")

            return wgs84.latlon(lat, lon, altitude)
        else:
                sys.exit(f"Errore: The User Position '{location}' not found in the config file.") 
    
    def getPositionVector(self, t):
        """
        Questa funzione ritorna un vettore in 3 dimensioni,
        della posizione dell'observer proiettato nello spazio.
        """

        return self.getLocation(altitude = 0).at(t).position.km.tolist()
    
    def print_task_summary(self):
        """
        Stampa un riassunto formattato dei task arrivati con successo all'Observer
        """
        print(f"TASK ARRIVATI CON SUCCESSO ALL'OBS: {len(self.tasks)}:\n")
        print(" id     | weight        | resolution    | Start Routing (s) | End Routing (s) | duration      | hop |")
        for task in self.tasks:
            print(f" {task.id:<6} | {byte_to_dim(task.weight):<13} | {task.resolution:<13} | {round(task.routingInitTime, 2):<17} | {round(task.routingEndTime, 2):<15} | {round(task.routingEndTime - task.routingInitTime, 2):<13} | {task.hop:<3} |")
        print()  # Riga vuota alla fine per separare dall'output successivo


