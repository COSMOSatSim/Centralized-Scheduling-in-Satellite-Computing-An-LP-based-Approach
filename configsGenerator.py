import os
import json5

seeds = [101, 2333, 5843, 7843, 7879, 9973]             # SEEDS
# algorithms = ["GREEDY", "BATMAN", "DINAMICO", "DSR"]   # Algo
routing_algorithms = ["GREEDY"]
routing_interval = [0.1]                             # Intervallo di Routing
apBIDIR = [True]                                 # Access Point Bidirezionali


mu_gen_mean = [0.05] # mu : CPU_timeout gen mean
mu_cpui_mean = [0.5] # mu : CPU_timeout cpui mean

# dts_algorithm = ["DTS-base", "OrbitAware"]                              # Algoritmo di selezione AP, searchNode e selezione SEN
# ap_selection = ["base", "optimal"]                                      # Selezione AP

scheduling_algorithm = [("DTS-base","DTS-base","base","ERT"), 
                        ("DTS-APopt","DTS-base","optimal","ERT"),
                        ("OrbitAware","OrbitAware","optimal","ERT"), 
                        ("ILP","DTS-base","optimal","ILP")]

# ARRIVAL RATE
# 2 = 0,5
# 3 = 0.33
# 4 = 0.25
# 6 = 0.16
# 8 = 0.125
# 10 = 0.1
arrival_rate = [0.5, 0.25, 0.16, 0.125, 0.1]
deadline = [10]
energy_budget = [80000, 100000, 120000]

# -- IMG RES -- #
beta_list = [(0.4, 0.35, 0.25)]                         # Beta
alpha_list = [(0.3, 0.5, 0.2)]                          # Alpha
gamma_list = [(0.7, 0.3)]                               # Gamma


OUTPUT_DIR_CONFIG = "SIMS_SETS"
OUTPUT_DIR_IMG_RESOLUTION = "SIMS_IMG_RESOLUTIONS"
os.makedirs(OUTPUT_DIR_CONFIG, exist_ok=True)  # Controllo l'esistenza del PATH
# Controllo l'esistenza del PATH
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
                                            
                                            cfg["request_distribution"]["distribution"] = scheduling_algo   # DTS Algorithm
                                            cfg["AP_selection"] = ap_selection                              # AP Selection
                                            cfg["SearchNode"] = searchNode                                  # SearchNode
                                                       
                                            # Arrival Rate
                                            cfg["arrival_time_exponential"] = ar_rate
                                            cfg["deadline"] = deadl # Deadline
                                            cfg["initial_energy"] = ener_bud # Energy Budget

                                            

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
                                                f"energy_budget_{ener_bud}.json5"
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
