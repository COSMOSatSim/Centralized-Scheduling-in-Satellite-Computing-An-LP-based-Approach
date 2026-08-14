import os
import csv
import re
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==========================================
# 1. CONFIGURAZIONI PARAMETRI
# ==========================================
root_folder = "results_esp_7_2" 

base_colors = [
    '#4E79A7', '#A0CBE8', # Coppia 1: Blues
    '#F28E2B', '#FFBE7D', # Coppia 2: Oranges
    '#59A14F', '#8CD17D', # Coppia 3: Greens
    '#B6992D', '#F1CE63', # Coppia 4: Yellow/Golds
    '#499894', '#86BCB6', # Coppia 5: Teals
    '#E15759', '#FF9D9A', # Coppia 6: Reds/Pinks
    '#79706E', '#BAB0AC', # Coppia 7: Greys
]
# ==========================================


# -----------------------------
# Funzioni di utilità & Parsing
# -----------------------------
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    at_match = re.search(r'AT_([\d.]+)', filepath)
    at_val = at_match.group(1) if at_match else None
    ar_val = int(round(1.0 / float(at_val))) if at_val else None

    bs_match = re.search(r'batch_size_(\d+)', filepath)
    bt_match = re.search(r'batch_timeout_([\d.]+)', filepath)
    obj_match = re.search(r'(obj_energy|obj_time)', filepath)
    dijk_match = re.search(r'dijk_(\d+_\d+)', filepath)
    
    # --- ESTRAZIONE DEADLINE ---
    # Assumo che il file contenga 'deadline_10', 'deadline_20', ecc.
    # Se il formato è diverso (es. 'dl_10'), modifica la stringa in r'dl_(\d+)'
    dl_match = re.search(r'deadline_(\d+)', filepath, re.IGNORECASE)
    
    bs_val = bs_match.group(1) if bs_match else "N/A"
    bt_val = bt_match.group(1) if bt_match else "N/A"
    obj_val = obj_match.group(1).replace("obj_", "").upper() if obj_match else "N/A"
    dl_val = int(dl_match.group(1)) if dl_match else "N/A"
    
    dijk_raw = dijk_match.group(1) if dijk_match else "N/A"
    if dijk_raw == "1_0":
        dijk_val = "Time"
    elif dijk_raw == "0_1":
        dijk_val = "Energy"
    else:
        dijk_val = dijk_raw 
    
    config_key = f"BS:{bs_val} | BT:{bt_val} | Dijk:{dijk_val}"
    return ar_val, obj_val, config_key, dl_val


def config_sort_key(config_str):
    bs_match = re.search(r'BS:(\d+)', config_str)
    bt_match = re.search(r'BT:([\d.]+)', config_str)
    dijk_match = re.search(r'Dijk:([\w]+)', config_str)
    
    bs_val = int(bs_match.group(1)) if bs_match else float('inf')
    bt_val = float(bt_match.group(1)) if bt_match else float('inf')
    dijk_val = dijk_match.group(1) if dijk_match else "Z"
    
    return (bs_val, bt_val, dijk_val)

def compute_stats(lines):
    completed = rejected = deadline = insuff_cn = insuff_c = no_server = ilp_infeasible = sunset = 0
    total_time = sys_time = 0.0

    for line in lines:
        if len(line) <= 26: 
            continue
            
        status = str(line[2]).strip()
        
        if status == "Completed":
            completed += 1
            if str(line[26]).strip() != "N/A":
                total_time += float(line[9]) + float(line[15]) + float(line[26])
                sys_time += float(line[9])
                
        elif status == "Rejected":
            rejected += 1
            reason = str(line[23]).lower()
            
            if "deadline" in reason:
                deadline += 1
            elif "energy" in reason:
                if "net" in reason:
                    insuff_cn += 1
                else:
                    insuff_c += 1
            elif "route" in reason:
                no_server += 1
            elif "infeasible" in reason:
                ilp_infeasible += 1
            elif "sunset" in reason:
                sunset += 1

    return completed, rejected, deadline, insuff_cn, insuff_c, no_server, ilp_infeasible, total_time, sys_time, sunset


# ==========================================
# ESECUZIONE PRINCIPALE: RACCOLTA DATI
# ==========================================
print("Inizio Estrazione e Classificazione Dati...")

data_store = {}
unique_configs = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file and "AT_" in file:
            filepath = os.path.join(root, file)
            ar, obj, config, dl = extract_parameters(filepath)
            
            # Escludiamo file di cui non riusciamo a mappare arrival rate, obj o deadline
            if ar is not None and obj != "N/A" and dl != "N/A":
                all_ars.add(ar)
                
                # Inizializziamo le strutture per le nuove deadline se non esistono
                if dl not in data_store:
                    data_store[dl] = {"ENERGY": {}, "TIME": {}}
                    unique_configs[dl] = {"ENERGY": set(), "TIME": set()}
                
                unique_configs[dl][obj].add(config)
                
                if ar not in data_store[dl][obj]:
                    data_store[dl][obj][ar] = {}
                if config not in data_store[dl][obj][ar]:
                    data_store[dl][obj][ar][config] = []
                
                rows = read_csv_to_2d_array(filepath)
                data_store[dl][obj][ar][config].extend(rows)

sorted_ars = sorted(list(all_ars))
sorted_deadlines = sorted(list(data_store.keys()))

# ==========================================
# ESPORTAZIONE CSV CON TUTTE LE STATISTICHE
# ==========================================
print("Esportazione delle statistiche in 'summary_statistics.csv'...")

csv_header = [
    "Deadline", "Objective_Mapping", "Arrival_Rate_ReqSec", "Batch_Size", "Batch_Timeout", "Dijkstra_Weight",
    "Total_Tasks", "Completed", "Rejected", "Success_Rate_PCT",
    "Rej_Deadline_PCT", "Rej_Insuff_CPU_NET_PCT", "Rej_Insuff_CPU_PCT",
    "Rej_No_Server_PCT", "Rej_ILP_Infeasible_PCT", 
    "Rej_Sunset_PCT", "Avg_System_Exec_ms", "Avg_Wait_Time_ms", "Avg_Total_Response_ms"
]

csv_rows = []

for dl in sorted_deadlines:
    for obj_type in ["ENERGY", "TIME"]:
        if not unique_configs[dl][obj_type]: continue
        sorted_configs = sorted(list(unique_configs[dl][obj_type]), key=config_sort_key)
        
        for config in sorted_configs:
            bs_match = re.search(r'BS:(\d+)', config)
            bt_match = re.search(r'BT:([\d.]+)', config)
            dijk_match = re.search(r'Dijk:([\w]+)', config)
            
            bs = bs_match.group(1) if bs_match else "N/A"
            bt = bt_match.group(1) if bt_match else "N/A"
            dijk = dijk_match.group(1) if dijk_match else "N/A"
            
            for ar in sorted_ars:
                rows = data_store[dl][obj_type].get(ar, {}).get(config, [])
                if not rows: continue
                    
                stats = compute_stats(rows)
                completed, rejected, deadline_rej, insuff_cn, insuff_c, no_server, ilp_infeasible, total_time, sys_time, sunset = stats
                
                total_tasks = completed + rejected
                
                # Calcolo Percentuali 
                sr = round((completed / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_dead = round((deadline_rej / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_cn = round((insuff_cn / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_c = round((insuff_c / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_ns = round((no_server / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_ilp = round((ilp_infeasible / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                r_sunset = round((sunset / total_tasks * 100), 2) if total_tasks > 0 else 0.0
                
                # Calcolo Tempi Medi
                avg_sys = round((sys_time / completed), 4) if completed > 0 else 0.0
                avg_tot = round((total_time / completed), 4) if completed > 0 else 0.0
                avg_wait = round(max(0, avg_tot - avg_sys), 4)
                
                csv_rows.append([
                    dl, obj_type, ar, bs, bt, dijk,
                    total_tasks, completed, rejected, sr,
                    r_dead, r_cn, r_c, r_ns, r_ilp,
                    r_sunset, avg_sys, avg_wait, avg_tot
                ])

with open("summary_statistics.csv", "w", newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(csv_header)
    writer.writerows(csv_rows)

print("Esportazione CSV completata con successo.")


# ==========================================
# CICLO GENERAZIONE GRAFICI (PER OGNI DEADLINE E OBIETTIVO)
# ==========================================
for dl in sorted_deadlines:
    print(f"\n=============================================")
    print(f" ELABORAZIONE DEADLINE: {dl}")
    print(f"=============================================")
    
    for obj_type in ["ENERGY", "TIME"]:
        sorted_configs = sorted(list(unique_configs[dl][obj_type]), key=config_sort_key)
        
        if not sorted_configs:
            print(f"Nessun dato per l'obiettivo {obj_type} con DL {dl}. Salto...")
            continue

        print(f"--- Generazione Grafici per Obiettivo: {obj_type} (DL: {dl}) ---")
        
        config_colors = {cfg: base_colors[i % len(base_colors)] for i, cfg in enumerate(sorted_configs)}
        n_configs = len(sorted_configs)
        
        step_width = 0.25      
        bar_width = 0.21       
        group_width = n_configs * step_width
        group_spacing = 0.8   
        
        x_base = np.arange(len(sorted_ars)) * (group_width + group_spacing)
        offsets = np.linspace(-group_width/2 + step_width/2, group_width/2 - step_width/2, n_configs)

        def draw_separators():
            for x in x_base[:-1]:
                plt.axvline(x + group_width/2 + group_spacing/2, color='gray', linestyle=':', alpha=0.4)

        # --------------------------------------------------
        # 1. SUCCESS RATE
        # --------------------------------------------------
        plt.figure(figsize=(32, 14))
        for i, config in enumerate(sorted_configs):
            y_vals = []
            for ar in sorted_ars:
                rows = data_store[dl][obj_type].get(ar, {}).get(config, [])
                if not rows:
                    y_vals.append(0)
                    continue
                stats = compute_stats(rows)
                c, r = stats[0], stats[1]
                y_vals.append(c / (c + r) if (c + r) > 0 else 0)
                
            plt.bar(x_base + offsets[i], y_vals, width=bar_width, color=config_colors[config], edgecolor='black', linewidth=0.3, label=config)

        draw_separators()
        plt.title(f"Success Rate per Arrival Rate ({obj_type} Mapping, DL={dl})", fontsize=26)
        plt.ylabel("Success Rate (%)", fontsize=26)
        plt.xlabel("Arrival Rate (req/sec)", fontsize=26)
        plt.ylim(0, 1)
        plt.xticks(x_base, sorted_ars, fontsize=22)
        plt.yticks(np.arange(0, 1.05, 0.1), fontsize=22)
        plt.grid(axis="y", linestyle="--", alpha=0.4) 
        plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=16, title="Configurations", title_fontsize=18)
        
        plt.savefig(f"01_AR_success_rate_{obj_type.lower()}_dl_{dl}.png", bbox_inches='tight')
        plt.close()

        # --------------------------------------------------
        # 2. REJECTION CAUSES
        # --------------------------------------------------
        plt.figure(figsize=(32, 14))
        
        cause_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"] 
        cause_labels = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]

        for i, config in enumerate(sorted_configs):
            bottom = np.zeros(len(sorted_ars))
            for cause_idx in range(len(cause_labels)):
                y_vals = []
                for ar in sorted_ars:
                    rows = data_store[dl][obj_type].get(ar, {}).get(config, [])
                    if not rows:
                        y_vals.append(0)
                        continue
                    stats = compute_stats(rows)
                    rejected = stats[1]
                    val = stats[2 + cause_idx] 
                    y_vals.append(val / rejected if rejected > 0 else 0)
                    
                plt.bar(x_base + offsets[i], y_vals, width=bar_width, bottom=bottom, color=cause_colors[cause_idx], 
                        edgecolor='black', linewidth=0.3)
                bottom += np.array(y_vals)

        draw_separators()
        plt.title(f"Failure causes per Arrival Rate ({obj_type} Mapping, DL={dl})", fontsize=26)
        plt.ylabel("Rejection Rate (%)", fontsize=26)
        plt.xlabel("Arrival Rate (req/sec)", fontsize=26)
        plt.ylim(0, 1)
        plt.xticks(x_base, sorted_ars, fontsize=22)
        plt.yticks(np.arange(0, 1.05, 0.1), fontsize=22)
        plt.grid(axis="y", linestyle="--", alpha=0.4)

        cause_patches = [mpatches.Patch(color=cause_colors[idx], label=cause_labels[idx]) for idx in range(len(cause_labels))]
        legend1 = plt.legend(handles=cause_patches, loc='upper left', bbox_to_anchor=(1.01, 1.03), fontsize=16, title="Failure Causes", title_fontsize=18)

        config_labels = [f"{cfg}" for cfg in sorted_configs]
        config_patches = [Line2D([0], [0], color='none', label=lbl) for lbl in config_labels]
        legend2 = plt.legend(handles=config_patches, loc='upper left', bbox_to_anchor=(1.01, 0.8), fontsize=16, title="Configurations", title_fontsize=18)
        plt.gca().add_artist(legend1)

        plt.savefig(f"02_AR_rejection_{obj_type.lower()}_dl_{dl}.png", bbox_inches='tight')
        plt.close()

        # --------------------------------------------------
        # 3. RESPONSE TIME 
        # --------------------------------------------------
        plt.figure(figsize=(32, 14))
        max_val = 0

        for i, config in enumerate(sorted_configs):
            y_sys = []
            y_diff = []
            for ar in sorted_ars:
                rows = data_store[dl][obj_type].get(ar, {}).get(config, [])
                if not rows:
                    y_sys.append(0)
                    y_diff.append(0)
                    continue
                stats = compute_stats(rows)
                completed = stats[0]
                sys_time = stats[8] / completed if completed > 0 else 0
                tot_time = stats[7] / completed if completed > 0 else 0
                
                y_sys.append(sys_time)
                y_diff.append(max(0, tot_time - sys_time))
                if tot_time > max_val: max_val = tot_time

            plt.bar(x_base + offsets[i], y_sys, width=bar_width, color=config_colors[config], edgecolor='black', linewidth=0.3)
            plt.bar(x_base + offsets[i], y_diff, width=bar_width, bottom=y_sys, color=config_colors[config], alpha=0.3, edgecolor='black', linewidth=0.3)

        draw_separators()
        plt.title(f"Stacked Response Time per Arrival Rate ({obj_type} Mapping, DL={dl})", fontsize=26)
        plt.ylabel("Response Time (ms)", fontsize=26)
        plt.xlabel("Arrival Rate (req/sec)", fontsize=26)
        plt.xticks(x_base, sorted_ars, fontsize=22)
        plt.ylim(0, max_val * 1.15 if max_val > 0 else 1)
        plt.yticks(fontsize=22)
        plt.grid(axis="y", linestyle="--", alpha=0.4)

        time_patches = [
                mpatches.Patch(facecolor='black', edgecolor='black', alpha=1.0, label='System Execution (Bottom)'),
                mpatches.Patch(facecolor='black', edgecolor='black', alpha=0.3, label='Network/Wait Time (Top)')
            ]
        legend_time = plt.legend(handles=time_patches, loc='upper left', bbox_to_anchor=(1.01, 0.075), fontsize=16, title="Time Component", title_fontsize=18)
        
        config_patches_rt = [mpatches.Patch(color=config_colors[cfg], label=cfg) for cfg in sorted_configs]
        legend_config = plt.legend(handles=config_patches_rt, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=16, title="Configurations", title_fontsize=18)
        
        plt.gca().add_artist(legend_time)

        plt.savefig(f"03_AR_response_{obj_type.lower()}_dl_{dl}.png", bbox_inches='tight')
        plt.close()

print("\nCompletato! Grafici generati per tutte le combinazioni di Obiettivo e Deadline.")