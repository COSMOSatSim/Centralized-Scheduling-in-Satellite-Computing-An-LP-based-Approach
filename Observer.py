
from collections import OrderedDict
from skyfield.api import wgs84
import globals
import sys
import json

# Leggi il file di configurazione JSON
with open('config.json') as config_file:
    config = json.load(config_file)

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

        self.tasks = []

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

        return self.getLocation().at(t).position.km.tolist()

# ob1 = Observer(1)
# ob2 = Observer(2)

# print(f"{ob1.position} - {ob2.position}")
# print(f"type: {type(ob1)}")
# if id(ob1) == id(ob2):
#     print("So uguali")
# else:
#     print("so diversi")

# # Controllo se ob1 è di tipo Observer
# if type(ob1) == Observer:
#     print("ob1 è di tipo <class '__main__.Observer'>")
# else:
#     print("ob1 NON è di tipo <class '__main__.Observer'>")


