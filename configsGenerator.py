import os
import json5
import textwrap

seeds = [101, 2333, 5843, 7843, 7879, 9973]             # SEEDS
# algorithms = ["GREEDY", "BATMAN", "DINAMICO", "DSR"]   # Algo
routing_algorithms = ["GREEDY"]
routing_interval = [0.1]                             # Intervallo di Routing
apBIDIR = [True]                                 # Access Point Bidirezionali


mu_gen_mean = [0.05] # mu : CPU_timeout gen mean
mu_cpui_mean = [0.5] # mu : CPU_timeout cpui mean

# dts_algorithm = ["DTS-base", "OrbitAware"]                              # Algoritmo di selezione AP, searchNode e selezione SEN
# ap_selection = ["base", "optimal"]                                      # Selezione AP

scheduling_algorithm = [("ILP-Centralized","DTS-base","optimal","ILP-Centralized")]  # Algoritmo di scheduling

'''scheduling_algorithm = [("DTS-base","DTS-base","base","ERT"), 
                        ("DTS-APopt","DTS-base","optimal","ERT"),
                        ("OrbitAware","OrbitAware","optimal","ERT"), 
                        ("ILP-Hierarchical","DTS-base","optimal","ILP"),
                        ("ILP-Weighted","DTS-base","optimal","ILP"),
                        ("ILP-Centralized","DTS-base","optimal","ILP-Centralized")] '''

lexi_primary = ["energy", "time"]                                          # Priorità ILP

arrival_rate = [0.5, 0.33, 0.25, 0.16, 0.125, 0.1] # da 2 a 10 req/sec
deadline = [10]
energy_budget = [80000]

ilp_weights = [
    (0.7, 0.3),
    (0.5, 0.5),
    (0.3, 0.7),
]

# -- IMG RES -- #
beta_list = [(0.4, 0.35, 0.25)]                         # Beta
alpha_list = [(0.3,0.5,0.2)]                          # Alpha
gamma_list = [(0.7, 0.3)]                               # Gamma

# === NUOVI PARAMETRI ILP CENTRALIZZATO ===
centralized_batch_size = [20] #range di valori per simulazioni successive [2, 4, 6, 8, 10]
centralized_batch_timeout = [0.2, 0.4, 0.6, 0.8, 1.0]     #>2 sec per prossime simulazioni          
centralized_lexi_tol = [0.1]
centralized_dijkstra_weights = [(1, 0), (0, 1)]   # (w_r, w_e) Pesi per il Dijkstra del Centralizzato
centralized_primary_objective = ["time", "energy"]  # Obiettivo primario per il Centralizzato
# =========================================

OUTPUT_DIR_CONFIG = "SIMS_SETS"
OUTPUT_DIR_IMG_RESOLUTION = "SIMS_IMG_RESOLUTIONS"
os.makedirs(OUTPUT_DIR_CONFIG, exist_ok=True)  
os.makedirs(OUTPUT_DIR_IMG_RESOLUTION, exist_ok=True)


# Apro la configurazione Base
with open('config.json5') as config_file:
    CONFIG = json5.load(config_file)
with open('img_resolution.json5') as img_resolution:
    IMG_RES = json5.load(img_resolution)


# GENERATORE
def gen_configs():
    for ener_bud in energy_budget:
        for deadl in deadline:
            for m_g_m in mu_gen_mean:
                for m_cpui_m in mu_cpui_mean:
                    for algo_ap in scheduling_algorithm:
                        label, scheduling_algo, ap_selection, searchNode = algo_ap

                        for ar_rate in arrival_rate:
                            for s in seeds:
                                for rout_algo in routing_algorithms:
                                    greedy, batman, dsr = None, None, None
                                    if rout_algo == "GREEDY":
                                        greedy, batman, dsr = True, False, False
                                    elif rout_algo == "BATMAN":
                                        greedy, batman, dsr = False, True, False
                                    elif rout_algo == "DINAMICO":
                                        greedy, batman, dsr = True, True, False
                                    elif rout_algo == "DSR":
                                        greedy, batman, dsr = False, False, True

                                    for rout_int in routing_interval:
                                        for apb in apBIDIR:
                                            for lx_prm in lexi_primary:
                                                for w_e, w_R in ilp_weights:
                                                    # --- 1. NUOVI CICLI FOR ---
                                                    for c_priority in centralized_primary_objective:
                                                        for batch_sz in centralized_batch_size:
                                                            for batch_tm in centralized_batch_timeout:
                                                                for c_tol in centralized_lexi_tol:
                                                                    for c_w_r, c_w_e in centralized_dijkstra_weights:
                                                                        
                                                                        cfg = CONFIG.copy()

                                                                        cfg["seed"] = s
                                                                        cfg["Routing_algorithm"] = {
                                                                            "BATMAN": batman,
                                                                            "GREEDY": greedy,
                                                                            "DSR": dsr,
                                                                        }
                                                                        cfg["Routing_Interval"] = rout_int
                                                                        cfg["AP_routing_bidirectional"] = apb

                                                                        # Mu
                                                                        cfg["CPU_timeout"]["gen"]["mean"] = m_g_m
                                                                        cfg["CPU_timeout"]["cpui"]["mean"] = m_cpui_m
                                                                        
                                                                        cfg["request_distribution"]["distribution"] = scheduling_algo   
                                                                        cfg["AP_selection"] = ap_selection                              
                                                                        cfg["SearchNode"] = searchNode                                  
                                                                            
                                                                        # Arrival Rate & Energy
                                                                        cfg["arrival_time_exponential"] = ar_rate
                                                                        cfg["deadline"] = deadl 
                                                                        cfg["initial_energy"] = ener_bud 

                                                                        # FIX BANDA: Assicura che la modifica vitale per il downlink venga iniettata
                                                                        cfg["Bandwidth_to_GU_Bps"] = 35000000
                                                                        
                                                                        config_file = ""
                                                                        if searchNode == "ERT":
                                                                            # --- 3A. AGGIORNAMENTO NOME FILE (Standard) ---
                                                                            config_file = (
                                                                                f"settings_"
                                                                                f"seed_{s}_"
                                                                                f"{label}_"
                                                                                f"Arr_Rate_{ar_rate}_"
                                                                                f"mu_gen_{m_g_m}_"
                                                                                f"mu_cpui_{m_cpui_m}_"
                                                                                f"Rout_Algo_{rout_algo}_"
                                                                                f"Rout_interv_{rout_int}_"
                                                                                f"apb_{apb}_"
                                                                                f"deadline_{deadl}_"
                                                                                f"energy_budget_{ener_bud}_"
                                                                                f"batch_{batch_sz}_"
                                                                                f"timeout_{batch_tm}_"
                                                                                f"tol_{c_tol}_"

                                                                            )
                                                                        else:
                                                                            mode = ""
                                                                            if label == "ILP-Hierarchical":
                                                                                cfg["ilp_objective"] = "hierarchical"
                                                                                cfg["lexi_primary"] = lx_prm
                                                                                mode = lx_prm
                                                                            elif label == "ILP-Weighted":
                                                                                cfg["ilp_objective"] = "weighted"
                                                                                cfg["ilp_weights"]["w_e"] = w_e
                                                                                cfg["ilp_weights"]["w_R"] = w_R
                                                                                mode = f"{w_e}_{w_R}"
                                                                            elif label == "ILP-Centralized":
                                                                                # --- GESTIONE SPECIFICA CENTRALIZZATO ---
                                                                                # Assegno l'obiettivo in base al ciclo (così testa sia "time" che "energy")
                                                                                cfg["centralized_primary_objective"] = c_priority
                                                                                                                                                        # --- 2. ASSEGNAZIONE NUOVI PARAMETRI ---
                                                                                cfg["centralized_batch_size"] = batch_sz
                                                                                cfg["centralized_batch_timeout"] = batch_tm
                                                                                cfg["centralized_lexi_tol"] = c_tol
                                                                                
                                                                                # Pesi Dijkstra Centralizzato
                                                                                cfg["centralized_w_r"] = c_w_r
                                                                                cfg["centralized_w_e"] = c_w_e
                                                                                
                                                                                cfg["centralized_primary_objective"] = c_priority
                                                                                mode = f"Centr_{c_priority}"

                                                                            # --- 3B. AGGIORNAMENTO NOME FILE (ILP) ---
                                                                            config_file = (
                                                                                f"settings_"
                                                                                f"seed_{s}_"
                                                                                f"{label}_"
                                                                                f"{mode}_"
                                                                                f"Arr_Rate_{ar_rate}_"
                                                                                f"mu_gen_{m_g_m}_"
                                                                                f"mu_cpui_{m_cpui_m}_"
                                                                                f"Rout_Algo_{rout_algo}_"
                                                                                f"Rout_interv_{rout_int}_"
                                                                                f"apb_{apb}_"
                                                                                f"deadline_{deadl}_"
                                                                                f"energy_budget_{ener_bud}_"
                                                                                f"batch_{batch_sz}_"
                                                                                f"timeout_{batch_tm}_"
                                                                                f"tol_{c_tol}_"
                                                                                f"Centr_{c_priority}"
                                                                                f"Dijk_{c_w_r}_{c_w_e}.json5" # <--- Aggiunto
                                                                            )

                                                                        filename = os.path.join(
                                                                            OUTPUT_DIR_CONFIG, config_file)

                                                                        with open(filename, "w") as f:
                                                                            json5.dump(cfg, f, indent=4)

                                                                        print(f"Creato: {filename}")


def gen_img_resolution():
    for beta in beta_list:
        for alpha in alpha_list:
            for gamma in gamma_list:
                img_res = IMG_RES.copy()

                beta_g, beta_cpui, beta_cpudi = beta
                print(f"beta: {beta_g}, {beta_cpui}, {beta_cpudi}")
                img_res["TASK_GENERATOR_PARAMS"]["beta_probabilities"]["Generic_Service"] = beta_g
                img_res["TASK_GENERATOR_PARAMS"]["beta_probabilities"]["CPU_Intensive"] = beta_cpui
                img_res["TASK_GENERATOR_PARAMS"]["beta_probabilities"]["CPU_and_Data_Intensive"] = beta_cpudi

                alpa_M, alpha_H, alpha_VH = alpha
                print(f"alpha: {alpa_M}, {alpha_H}, {alpha_VH}")
                img_res["TASK_GENERATOR_PARAMS"]["size_ranges_MB"]["CPU_DATA_INTENSIVE"]["alpha_M_weight"] = alpa_M
                img_res["TASK_GENERATOR_PARAMS"]["size_ranges_MB"]["CPU_DATA_INTENSIVE"]["alpha_H_weight"] = alpha_H
                img_res["TASK_GENERATOR_PARAMS"]["size_ranges_MB"]["CPU_DATA_INTENSIVE"]["alpha_VH_weight"] = alpha_VH

                gamma_H, gamma_VH = gamma
                print(f"gamma: {gamma_H}, {gamma_VH}")
                img_res["TASK_GENERATOR_PARAMS"]["size_ranges_MB"]["BATCH_TASK"]["gamma_H_weight"] = gamma_H
                img_res["TASK_GENERATOR_PARAMS"]["size_ranges_MB"]["BATCH_TASK"]["gamma_VH_weight"] = gamma_VH

                filename = os.path.join(
                    OUTPUT_DIR_IMG_RESOLUTION, f"img_resolution_Bg_{beta_g}_Bcpui_{beta_cpui}_Bcpudi_{beta_cpudi}_AM_{alpa_M}_AH_{alpha_H}_AVH_{alpha_VH}_GH_{gamma_H}_GVH_{gamma_VH}.json5")
                with open(filename, "w") as file:
                    json5.dump(img_res, file, indent=4)

                print(f"Creato: {filename}")


gen_configs()
gen_img_resolution()



# === CONFIGURAZIONE ===
SIMS_SETS = "SIMS_SETS"
SIMS_IMG_RESOLUTIONS = "SIMS_IMG_RESOLUTIONS"

# Nomi dei file di lista per l'Array Slurm
SIMS_LIST_FILE = "sims_sets_list.txt"
IMG_RES_LIST_FILE = "img_resolutions_list.txt"

# crea le cartelle se non esistono
os.makedirs(SIMS_SETS, exist_ok=True)
os.makedirs(SIMS_IMG_RESOLUTIONS, exist_ok=True)

# ottieni tutti i file json nelle due cartelle
sets_files = [f for f in os.listdir(SIMS_SETS) if f.endswith(".json5")]
imgres_files = [f for f in os.listdir(SIMS_IMG_RESOLUTIONS) if f.endswith(".json5")]

# === GENERAZIONE LISTE DI INPUT ===
total_jobs = 0
with open(SIMS_LIST_FILE, "w") as set_f, open(IMG_RES_LIST_FILE, "w") as img_f:
    for set_file in sets_files:
        for imgres_file in imgres_files:
            
            # Scrivi il percorso completo del file di SETS (primo argomento)
            set_f.write(f"{SIMS_SETS}/{set_file}\n")
            
            # Scrivi il percorso completo del file di IMG_RES (secondo argomento)
            img_f.write(f"{SIMS_IMG_RESOLUTIONS}/{imgres_file}\n")
            
            total_jobs += 1

print(f"Creati {total_jobs} job totali. Liste salvate in '{SIMS_LIST_FILE}' e '{IMG_RES_LIST_FILE}'.")
# Il numero totale di job è il tuo indice N per l'array Slurm (es. 1000)