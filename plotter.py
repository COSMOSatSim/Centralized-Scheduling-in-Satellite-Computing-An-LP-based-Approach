import os
import csv
import re
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==========================================
# 1. CONFIGURAZIONI PARAMETRI E COLORI
# ==========================================
root_folder = "simulazioni_esp_8" # Cambia con il nome della tua cartella

# Colori fissi assegnati agli algoritmi per coerenza visiva
ALGO_COLORS = {
    "DTS-base": "#F28E2B",
    "DTS-APopt": "#4E79A7",
    "OrbitAware": "#59A14F",
    "ILP-Centralized": "#E15759",
    "ILP-Hierarchical-Time": "#B6992D",  # <-- CORRETTO
    "ILP-Weighted-0.5-0.5": "#9467BD"    # <-- CORRETTO
}

# Pattern (hatch) per distinguere le barre nelle Rejection Causes
ALGO_HATCHES = {
    "DTS-base": "",
    "DTS-APopt": "//",
    "OrbitAware": "..",
    "ILP-Centralized": "xx",
    "ILP-Hierarchical-Time": "++",       # <-- CORRETTO
    "ILP-Weighted-0.5-0.5": "||"         # <-- CORRETTO
}

# Ordine desiderato per la legenda e le barre sull'asse X
ALGO_ORDER = [
    "DTS-base", 
    "DTS-APopt", 
    "OrbitAware", 
    "ILP-Centralized", 
    "ILP-Hierarchical-Time",             # <-- CORRETTO
    "ILP-Weighted-0.5-0.5"               # <-- CORRETTO
]
# ==========================================


# -----------------------------
# Funzioni di utilità & Parsing
# -----------------------------
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    # Estrazione Arrival Rate
    ar_match = re.search(r'(?:Arr_Rate|AT)_([\d.]+)', filepath)
    if ar_match:
        at_val = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_val))
    else:
        ar_val = None

    # Convertiamo il path in minuscolo
    filepath_lower = filepath.lower()

    # Estrazione Blindata dell'Algoritmo
    algo_val = "Unknown"
    
    if "ilp-centralized" in filepath_lower:
        algo_val = "ILP-Centralized"
    elif "hierarchical" in filepath_lower and "time" in filepath_lower:
        algo_val = "ILP-Hierarchical-Time"
    # CORREZIONE: Ora cerchiamo la stringa esatta creata dal main.py
    elif "weighted" in filepath_lower and "0.5_w_r_0.5" in filepath_lower:
        algo_val = "ILP-Weighted-0.5-0.5"
    elif "dts-apopt" in filepath_lower:
        algo_val = "DTS-APopt"
    elif "dts-base" in filepath_lower:
        algo_val = "DTS-base"
    elif "orbitaware" in filepath_lower:
        algo_val = "OrbitAware"
    
    # Estrazione Deadline
    dl_match = re.search(r'deadline_(\d+)', filepath, re.IGNORECASE)
    dl_val = int(dl_match.group(1)) if dl_match else "N/A"
    
    return ar_val, algo_val, dl_val

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
all_ars = set()
unique_algos = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            ar, algo, dl = extract_parameters(filepath)
            
            if ar is not None and algo != "Unknown" and dl != "N/A":
                all_ars.add(ar)
                unique_algos.add(algo)
                
                if dl not in data_store:
                    data_store[dl] = {}
                
                if algo not in data_store[dl]:
                    data_store[dl][algo] = {}
                    
                if ar not in data_store[dl][algo]:
                    data_store[dl][algo][ar] = []
                
                rows = read_csv_to_2d_array(filepath)
                data_store[dl][algo][ar].extend(rows)

sorted_ars = sorted(list(all_ars))
sorted_deadlines = sorted(list(data_store.keys()))

# Garantisce che l'ordine sia rispettato e include i nuovi algoritmi solo se presenti
present_algos = [algo for algo in ALGO_ORDER if algo in unique_algos]

# ==========================================
# CICLO GENERAZIONE GRAFICI (PER OGNI DEADLINE)
# ==========================================
for dl in sorted_deadlines:
    print(f"\n=============================================")
    print(f" ELABORAZIONE DEADLINE: {dl}")
    print(f"=============================================")
    
    if not present_algos:
        print(f"Nessun dato trovato per la DL {dl}. Salto...")
        continue

    n_configs = len(present_algos)
    
    # Regolazione dinamica della larghezza delle barre in base al numero di algoritmi testati
    step_width = 0.85 / n_configs      
    bar_width = step_width * 0.90      
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
    print(f"Generazione Success Rate (DL={dl})...")
    plt.figure(figsize=(24, 10))
    for i, algo in enumerate(present_algos):
        y_vals = []
        for ar in sorted_ars:
            rows = data_store[dl].get(algo, {}).get(ar, [])
            if not rows:
                y_vals.append(0)
                continue
            stats = compute_stats(rows)
            c, r = stats[0], stats[1]
            y_vals.append((c / (c + r) * 100) if (c + r) > 0 else 0)
            
        plt.bar(x_base + offsets[i], y_vals, width=bar_width, color=ALGO_COLORS[algo], edgecolor='black', linewidth=0.5, label=algo)

    draw_separators()
    plt.title("Success Rate per Algorithm across Arrival Rates", fontsize=22)
    plt.ylabel("Success Rate (%)", fontsize=20)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=20)
    plt.ylim(0, 100)
    plt.xticks(x_base, sorted_ars, fontsize=16)
    plt.yticks(np.arange(0, 105, 10), fontsize=16)
    plt.grid(axis="y", linestyle="--", alpha=0.5) 
    plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=14, title="Algorithms", title_fontsize=16)
    
    plt.savefig(f"01_AR_success_rate_dl_{dl}.png", bbox_inches='tight')
    plt.close()

    # --------------------------------------------------
    # 2. REJECTION CAUSES
    # --------------------------------------------------
    print(f"Generazione Rejection Causes (DL={dl})...")
    plt.figure(figsize=(24, 10))
    
    cause_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"] 
    cause_labels = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]

    for i, algo in enumerate(present_algos):
        bottom = np.zeros(len(sorted_ars))
        for cause_idx in range(len(cause_labels)):
            y_vals = []
            for ar in sorted_ars:
                rows = data_store[dl].get(algo, {}).get(ar, [])
                if not rows:
                    y_vals.append(0)
                    continue
                stats = compute_stats(rows)
                rejected = stats[1]
                val = stats[2 + cause_idx] 
                y_vals.append((val / rejected * 100) if rejected > 0 else 0)
                
            plt.bar(x_base + offsets[i], y_vals, width=bar_width, bottom=bottom, color=cause_colors[cause_idx], 
                    edgecolor='black', linewidth=0.5, hatch=ALGO_HATCHES[algo])
            bottom += np.array(y_vals)

    draw_separators()
    plt.title("Failure Causes per Algorithm across Arrival Rates", fontsize=22)
    plt.ylabel("Rejection Rate (%)", fontsize=20)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=20)
    plt.ylim(0, 100)
    plt.xticks(x_base, sorted_ars, fontsize=16)
    plt.yticks(np.arange(0, 105, 10), fontsize=16)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    cause_patches = [mpatches.Patch(color=cause_colors[idx], label=cause_labels[idx]) for idx in range(len(cause_labels))]
    legend1 = plt.legend(handles=cause_patches, loc='upper left', bbox_to_anchor=(1.01, 1.03), fontsize=14, title="Failure Causes", title_fontsize=16)

    config_patches = [mpatches.Patch(facecolor='white', edgecolor='black', hatch=ALGO_HATCHES[algo], label=algo) for algo in present_algos]
    legend2 = plt.legend(handles=config_patches, loc='upper left', bbox_to_anchor=(1.01, 0.7), fontsize=14, title="Algorithms", title_fontsize=16)
    plt.gca().add_artist(legend1)

    # Correzione bbox_extra_artists applicata
    plt.savefig(f"02_AR_rejection_causes_dl_{dl}.png", bbox_inches='tight', bbox_extra_artists=(legend1, legend2))
    plt.close()

    # --------------------------------------------------
    # 3. RESPONSE TIME 
    # --------------------------------------------------
    print(f"Generazione Response Time (DL={dl})...")
    plt.figure(figsize=(24, 10))
    max_val = 0

    for i, algo in enumerate(present_algos):
        y_sys = []
        y_diff = []
        for ar in sorted_ars:
            rows = data_store[dl].get(algo, {}).get(ar, [])
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

        plt.bar(x_base + offsets[i], y_sys, width=bar_width, color=ALGO_COLORS[algo], edgecolor='black', linewidth=0.5)
        plt.bar(x_base + offsets[i], y_diff, width=bar_width, bottom=y_sys, color=ALGO_COLORS[algo], alpha=0.35, edgecolor='black', linewidth=0.5)

    draw_separators()
    plt.title("Stacked Response Time per Algorithm across Arrival Rates", fontsize=22)
    plt.ylabel("Response Time (ms)", fontsize=20)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=20)
    plt.xticks(x_base, sorted_ars, fontsize=16)
    plt.ylim(0, max_val * 1.15 if max_val > 0 else 1)
    plt.yticks(fontsize=16)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    time_patches = [
            mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='System Execution (Bottom)'),
            mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Network/Wait Time (Top)')
        ]
    legend_time = plt.legend(handles=time_patches, loc='upper left', bbox_to_anchor=(1.01, 0.7), fontsize=14, title="Time Components", title_fontsize=16)
    
    config_patches_rt = [mpatches.Patch(color=ALGO_COLORS[algo], label=algo) for algo in present_algos]
    legend_config = plt.legend(handles=config_patches_rt, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=14, title="Algorithms", title_fontsize=16)
    
    plt.gca().add_artist(legend_time)

    # Correzione bbox_extra_artists applicata
    plt.savefig(f"03_AR_response_time_dl_{dl}.png", bbox_inches='tight', bbox_extra_artists=(legend_time, legend_config))
    plt.close()

print("\nCompletato! Sono stati generati i 3 grafici di comparazione algoritmi.")