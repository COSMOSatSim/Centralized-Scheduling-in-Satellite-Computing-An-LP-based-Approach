import json
import subprocess

Simulation_type_distribuited = "main.py"

def esegui_simulazione(file_path):
    # Esegui la simulazione
    comando_simulazione = ["python", Simulation_type_distribuited, "--file", file_path]
    print("eseguo la simulazione")
    subprocess.run(comando_simulazione)


def modifica_parametri(file_path, nuovi_parametri):
    with open(file_path, 'r') as file:
        dati = json.load(file)

    # Modifica i parametri
    dati["generate_tasks"]["distribution"] = nuovi_parametri["generate_tasks"]["distribution"]
    dati["CPU_timeout"] = nuovi_parametri["CPU_timeout"]
    dati["priority_combination"]["distribution"] = nuovi_parametri["priority_combination"]["distribution"]
    dati["request_distribution"]["distribution"] = nuovi_parametri["request_distribution"]["distribution"]
    dati["seed"] = nuovi_parametri["seed"]
    dati["arrival_time_exponential"] = nuovi_parametri["arrival_time_exponential"]



    with open(file_path, 'w') as file:
        json.dump(dati, file, indent=2)

# Set comuni di seed e arrival_time_exponential
seed_values = [42]#, 142, 242, 342, 442, 542, 642, 742, 842, 942 ]
arrival_time_values = [0.5, 1, 1.5, 2, 2.5, 3]
CPU_timeout = [10,30,50,70,90,110]

# File JSON di input
file_json = "config.json"

request_distribution_values = [
    {"distribution": "33_33_33"},
    {"distribution": "20_30_50"}
]
priority_combination_values = [
    {"distribution": "20_0_80"}
]

# Itera su tutti i set di parametri
#Cambinanzione task (H, L) = (20_0_80), (50_0_50)
for seed in seed_values:
    for arrival_time in arrival_time_values:
        for priority_combination in priority_combination_values:
                for CPU in CPU_timeout:
                    print(CPU)
                    nuovi_parametri = {
                        "generate_tasks": {"distribution": "exponential"},
                        "priority_combination": priority_combination,
                        "request_distribution": {"distribution": "0_0_0"},
                        "seed": seed,
                        "arrival_time_exponential": arrival_time,
                        "CPU_timeout":{"min":0,"mean": CPU, "max":90000}
                    }
                    print('Ci sono quasi... preparo il file json')

                    modifica_parametri(file_json, nuovi_parametri)
                    esegui_simulazione(file_json)