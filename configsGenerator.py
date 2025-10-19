import os
import json5

seeds = [13, 23, 33, 43, 53, 63, 73, 83, 93, 103, 113]  # SEEDS
algorithms = ["GREEDY", "BATMAN", "DINAMICO", "DSR"]    # Algoritmi
routing_interval = [1, 0.1]                             # Intervallo di Routing
apBIDIR = [True, False]                                 # Access Point Bidirezionali



OUTPUT_DIR = "SIM_SETS"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # Controllo l'esistenza del PATH

# Apro la configurazione Base
with open('config.json5') as config_file:
    CONFIG = json5.load(config_file)



# GENERATORE
for s in seeds:
    for a in algorithms:
        
        greedy, batman, dsr = None, None, None
        if a == "GREEDY":
            greedy, batman, dsr = True, False, False
        elif a == "BATMAN":
            greedy, batman, dsr = False, True, False
        elif a == "DINAMICO":
            greedy, batman, dsr = True, True, False
        elif a == "DSR":
            greedy, batman, dsr = False, False, True
         
          
        for r in routing_interval:
            for apb in apBIDIR:
                cfg = CONFIG.copy()

                cfg["seed"] = s
                cfg["Routing_algorithm"] = {
                    "BATMAN": batman,
                    "GREEDY": greedy,
                    "DSR": dsr,
                }
                cfg["Routing_Interval"] = r
                cfg["AP_routing_bidirectional"] = apb

                filename = os.path.join(OUTPUT_DIR, f"settings_seed_{s}_algo_{a}_ri_{r}_apb_{apb}.json5")
                
                with open(filename, "w") as f:
                    json5.dump(cfg, f, indent=4)

                print(f"Creato: {filename}")
