import json5
import subprocess

# Nome dello script di simulazione
Simulation_type_distribuited = "main.py"
# File JSON di configurazione di base
file_json = "config.json5"

# Definizione delle modalità di simulazione
modalita_simulazione = {
    "DTS-base": {
        "request_distribution": {"distribution": "DTS-base"},
        "AP_selection": "distance_based",
        "SearchNode": "ERT",
        "SEN_selection": "random"
    },
    "DTS-AP optimal": {
        "request_distribution": {"distribution": "DTS-AP optimal"},
        "AP_selection": "optimal",
        "SearchNode": "ERT",
        "SEN_selection": "random"
    },
    "OrbitAware": {
        "request_distribution": {"distribution": "OrbitAware"},
        "AP_selection": "optimal",
        "SearchNode": "ERT+SunsetCheck",
        "SEN_selection": "maxSunset"
    },
    "OrbitAware Utility": {
        "request_distribution": {"distribution": "OrbitAware Utility"},
        "AP_selection": "optimal",
        "SearchNode": "ERT/Sunset",
        "SEN_selection": "maxSunset"
    }
}

# Valori comuni
seed_values = [42]
arrival_time_values = [0.5, 1, 1.5]
CPU_timeout_values = [10, 20, 30, 40, 50]
priority_combination_values = [{"distribution": "20_0_80"}]


def esegui_simulazione(file_path):
    comando = ["python", Simulation_type_distribuited, "--file", file_path]
    print(f"Eseguo: {' '.join(comando)}")
    subprocess.run(comando, check=True)


def modifica_parametri(file_path, nuovi_parametri):
    with open(file_path, 'r') as f:
        dati = json5.load(f)

    # Parametri comuni
    dati["generate_tasks"]["distribution"] = nuovi_parametri["generate_tasks"]["distribution"]
    dati["priority_combination"]["distribution"] = nuovi_parametri["priority_combination"]["distribution"]
    dati["request_distribution"]["distribution"] = nuovi_parametri["request_distribution"]["distribution"]
    dati["seed"] = nuovi_parametri["seed"]
    dati["arrival_time_exponential"] = nuovi_parametri["arrival_time_exponential"]
    dati["CPU_timeout"] = nuovi_parametri["CPU_timeout"]

    # Parametri specifici di modalità
    dati["AP_selection"] = nuovi_parametri["AP_selection"]
    dati["SearchNode_method"] = nuovi_parametri["SearchNode"]
    dati["SEN_selection"] = nuovi_parametri["SEN_selection"]

    with open(file_path, 'w') as f:
        json5.dump(dati, f, indent=2)


if __name__ == "__main__":
    for nome, config in modalita_simulazione.items():
        print(f"\n>>> Modalità: {nome}")
        for seed in seed_values:
            for arrival in arrival_time_values:
                for priority in priority_combination_values:
                    for cpu in CPU_timeout_values:
                        params = {
                            "generate_tasks": {"distribution": "exponential"},
                            "priority_combination": priority,
                            "request_distribution": config["request_distribution"],
                            "seed": seed,
                            "arrival_time_exponential": arrival,
                            "CPU_timeout": {"min": 0, "mean": cpu, "max": 90000},
                            "AP_selection": config["AP_selection"],
                            "SearchNode": config["SearchNode"],
                            "SEN_selection": config["SEN_selection"]
                        }
                        print(f"Parametri: seed={seed}, arrival={arrival}, cpu={cpu}")
                        modifica_parametri(file_json, params)
                        esegui_simulazione(file_json)
