import os
import csv
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==============================================================================
# 1. CONFIGURAZIONE PERCORSI E PARAMETRI
# ==============================================================================
root_folder = "simulazioni_esp_10"  # Sostituisci con il path dei tuoi CSV
OUTPUT_DIR = "plots"               # Cartella in cui salvare i grafici

# Creazione automatica della directory di destinazione se non esiste
os.makedirs(OUTPUT_DIR, exist_ok=True)

# I 9 algoritmi distinti da confrontare
ALGO_ORDER = [
    "DTS-base",
    "DTS-Optimal",
    "Orbit-aware",
    "ILP-Hierarchical (Time)",
    "ILP-Hierarchical (Energy)",
    "ILP-Centr (BS20, BT0.05, Time)",
    "ILP-Centr (BS20, BT0.05, Energy)",
    "ILP-Centr (BS2, BT2, Time)",
    "ILP-Centr (BS2, BT2, Energy)"
]

# Palette ad alto contrasto per distinguere chiaramente le 9 configurazioni
ALGO_COLORS = {
    "DTS-base":                         "#F28E2B",  # Arancione
    "DTS-Optimal":                      "#4E79A7",  # Blu
    "Orbit-aware":                      "#59A14F",  # Verde
    "ILP-Hierarchical (Time)":          "#B6992D",  # Oro/Senape
    "ILP-Hierarchical (Energy)":        "#8C564B",  # Marrone
    "ILP-Centr (BS20, BT0.05, Time)":   "#E15759",  # Rosso brillante
    "ILP-Centr (BS20, BT0.05, Energy)": "#FF9D9A",  # Salmone
    "ILP-Centr (BS2, BT2, Time)":       "#79706E",  # Antracite
    "ILP-Centr (BS2, BT2, Energy)":     "#BAB0AC"   # Grigio chiaro
}

CAUSE_KEYS = ["deadline", "insuff_cn", "insuff_c", "no_server", "ilp_infeasible", "sunset"]
CAUSE_LABELS = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]
CAUSE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

# ==============================================================================
# 2. PARSING DEI DATI E CLASSIFICAZIONE
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # 1. Arrival Rate (es. arr_rate_0.1 -> 10 req/s, arr_rate_0.5 -> 2 req/s)
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_f = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_f)) if at_f <= 1.0 else int(round(at_f))
    else:
        ar_val = None

    # 2. Budget Energetico (40 kJ vs 80 kJ)
    budget_match = re.search(r'(?:energy_budget|budget)[_=]?(\d+)', f_lower)
    if budget_match:
        b_val = int(budget_match.group(1))
        budget_str = "40 kJ" if b_val in [40, 40000] else "80 kJ"
    else:
        budget_str = "80 kJ"

    # 3. Classificazione univoca dei 9 Algoritmi
    algo_val = None
    if "centralized" in f_lower or "ilp-centralized" in f_lower:
        # Obiettivo primario (Energy vs Time)
        obj_match = re.search(r'obj[_=]([a-z]+)', f_lower)
        if obj_match:
            mapping = obj_match.group(1).capitalize()
        elif any(k in f_lower for k in ["obj_energy", "energy_mapping", "/energy/"]):
            mapping = "Energy"
        else:
            mapping = "Time"

        # Configurazione di Batching (BS 20 e BT 0.05 vs BS 2 e BT 2)
        if any(k in f_lower for k in ["batch_size_20", "bs_20", "bs20"]):
            algo_val = f"ILP-Centr (BS20, BT0.05, {mapping})"
        elif any(k in f_lower for k in ["batch_size_2", "bs_2", "bs2"]):
            algo_val = f"ILP-Centr (BS2, BT2, {mapping})"
        else:
            # Fallback tramite timeout
            if "0.05" in f_lower:
                algo_val = f"ILP-Centr (BS20, BT0.05, {mapping})"
            else:
                algo_val = f"ILP-Centr (BS2, BT2, {mapping})"

    elif "hierarchical" in f_lower:
        if "energy" in f_lower:
            algo_val = "ILP-Hierarchical (Energy)"
        else:
            algo_val = "ILP-Hierarchical (Time)"

    elif "orbitaware" in f_lower or "orbit-aware" in f_lower:
        algo_val = "Orbit-aware"
    elif "dts-apopt" in f_lower or "dts-optimal" in f_lower:
        algo_val = "DTS-Optimal"
    elif "dts-base" in f_lower:
        algo_val = "DTS-base"

    return ar_val, budget_str, algo_val

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

    return {
        "completed": completed, "rejected": rejected,
        "deadline": deadline, "insuff_cn": insuff_cn, "insuff_c": insuff_c,
        "no_server": no_server, "ilp_infeasible": ilp_infeasible, "sunset": sunset,
        "total_time": total_time, "sys_time": sys_time
    }

# ==============================================================================
# 3. RACCOLTA E AGGREGAZIONE SUI PROFILI DI WORKLOAD
# ==============================================================================
print(f"Scansione ricorsiva della cartella '{root_folder}'...")
data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            ar, budget, algo = extract_parameters(filepath)

            if None not in (ar, budget, algo):
                all_ars.add(ar)
                data_store.setdefault(budget, {}).setdefault(algo, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars))
budgets = [b for b in ["40 kJ", "80 kJ"] if b in data_store]

if not budgets:
    print("Nessun dato CSV valido trovato. Controlla il percorso in 'root_folder'.")
    exit()

present_algos = [a for a in ALGO_ORDER if any(a in data_store[b] for b in budgets)]
n_algos = len(present_algos)
print(f"Caricati {len(sorted_ars)} tassi di arrivo ({sorted_ars}) e {n_algos} configurazioni algoritmiche.")

step_w = 0.82 / n_algos
bar_w = step_w * 0.90
grp_w = n_algos * step_w
grp_space = 0.45
x_base = np.arange(len(sorted_ars)) * (grp_w + grp_space)
offsets = np.linspace(-grp_w/2 + step_w/2, grp_w/2 - step_w/2, n_algos)

# ==============================================================================
# 4. GRAFICO 1: SUCCESS RATE COMPARISON (40 kJ vs 80 kJ)
# ==============================================================================
fig, axes = plt.subplots(1, len(budgets), figsize=(12 * len(budgets), 7), sharey=True, squeeze=False)

for idx, b in enumerate(budgets):
    ax = axes[0, idx]
    for i, algo in enumerate(present_algos):
        y_vals = []
        for ar in sorted_ars:
            rows = data_store[b].get(algo, {}).get(ar, [])
            st = compute_stats(rows)
            c, r = st["completed"], st["rejected"]
            y_vals.append((c / (c + r) * 100) if (c + r) > 0 else 0.0)

        ax.bar(x_base + offsets[i], y_vals, width=bar_w,
               color=ALGO_COLORS[algo], edgecolor='black', linewidth=0.3)

    for x in x_base[:-1]:
        ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.35)

    ax.set_title(f"Energy Budget: {b}", fontsize=14, fontweight='bold')
    ax.set_xticks(x_base)
    ax.set_xticklabels(sorted_ars, fontsize=11)
    ax.set_xlabel("Arrival Rate (req/s)", fontsize=12)
    ax.set_ylim(0, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if idx == 0:
        ax.set_ylabel("Success Rate (%)", fontsize=12)

algo_patches = [mpatches.Patch(color=ALGO_COLORS[a], label=a) for a in present_algos]
fig.legend(handles=algo_patches, loc='lower center', ncol=3,
           bbox_to_anchor=(0.5, -0.10), fontsize=10, title="Algorithm Configuration", title_fontsize=11)

fig.suptitle("Consolidated Success Rate across 9 SCSH Configurations", fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout()

out_sr = os.path.join(OUTPUT_DIR, "01_Consolidated_Success_Rate_9Algos.png")
plt.savefig(out_sr, bbox_inches='tight')
plt.close()
print(f"Salvato: {out_sr}")

# ==============================================================================
# 5. GRAFICO 2: REJECTION CAUSES BREAKDOWN (40 kJ vs 80 kJ at Max Load)
# ==============================================================================
crit_ar = sorted_ars[-1] if sorted_ars else 10
fig, axes = plt.subplots(1, len(budgets), figsize=(12 * len(budgets), 7), sharey=True, squeeze=False)
x_algos = np.arange(len(present_algos))

for idx, b in enumerate(budgets):
    ax = axes[0, idx]
    bottom = np.zeros(len(present_algos))

    for k_idx, key in enumerate(CAUSE_KEYS):
        y_vals = []
        for algo in present_algos:
            rows = data_store[b].get(algo, {}).get(crit_ar, [])
            st = compute_stats(rows)
            rej = st["rejected"]
            y_vals.append((st[key] / rej * 100) if rej > 0 else 0.0)

        ax.bar(x_algos, y_vals, width=0.65, bottom=bottom,
               color=CAUSE_COLORS[k_idx], edgecolor='black', linewidth=0.3)
        bottom += np.array(y_vals)

    ax.set_title(f"Energy Budget: {b} (Arrival Rate = {crit_ar} req/s)", fontsize=14, fontweight='bold')
    ax.set_xticks(x_algos)
    ax.set_xticklabels(present_algos, fontsize=9, rotation=35, ha='right')
    ax.set_ylim(0, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if idx == 0:
        ax.set_ylabel("Rejection Breakdown (%)", fontsize=12)

cause_patches = [mpatches.Patch(color=CAUSE_COLORS[k], label=CAUSE_LABELS[k]) for k in range(len(CAUSE_LABELS))]
fig.legend(handles=cause_patches, loc='lower center', ncol=len(CAUSE_LABELS),
           bbox_to_anchor=(0.5, -0.08), fontsize=10, title="Failure Causes", title_fontsize=11)

fig.suptitle("Consolidated Rejection Causes Distribution under Critical Load", fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout()

out_rej = os.path.join(OUTPUT_DIR, "02_Consolidated_Failure_Causes_9Algos.png")
plt.savefig(out_rej, bbox_inches='tight')
plt.close()
print(f"Salvato: {out_rej}")

# ==============================================================================
# 6. GRAFICO 3: STACKED RESPONSE TIME (40 kJ vs 80 kJ)
# ==============================================================================
fig, axes = plt.subplots(1, len(budgets), figsize=(12 * len(budgets), 7), sharey=True, squeeze=False)
max_rt = 0.0

for idx, b in enumerate(budgets):
    ax = axes[0, idx]
    for i, algo in enumerate(present_algos):
        y_sys, y_diff = [], []
        for ar in sorted_ars:
            rows = data_store[b].get(algo, {}).get(ar, [])
            st = compute_stats(rows)
            comp = st["completed"]
            sys_t = (st["sys_time"] / comp) if comp > 0 else 0.0
            tot_t = (st["total_time"] / comp) if comp > 0 else 0.0
            y_sys.append(sys_t)
            y_diff.append(max(0.0, tot_t - sys_t))
            if tot_t > max_rt:
                max_rt = tot_t

        c = ALGO_COLORS[algo]
        ax.bar(x_base + offsets[i], y_sys, width=bar_w, color=c, edgecolor='black', linewidth=0.3)
        ax.bar(x_base + offsets[i], y_diff, width=bar_w, bottom=y_sys, color=c, alpha=0.35, edgecolor='black', linewidth=0.3)

    for x in x_base[:-1]:
        ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.35)

    ax.set_title(f"Energy Budget: {b}", fontsize=14, fontweight='bold')
    ax.set_xticks(x_base)
    ax.set_xticklabels(sorted_ars, fontsize=11)
    ax.set_xlabel("Arrival Rate (req/s)", fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if idx == 0:
        ax.set_ylabel("Response Time (ms)", fontsize=12)

for idx in range(len(budgets)):
    axes[0, idx].set_ylim(0, max_rt * 1.15 if max_rt > 0 else 1.0)

time_comp_patches = [
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='System Execution'),
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Network / Wait Time')
]

leg1 = fig.legend(handles=algo_patches, loc='lower center', ncol=3,
                  bbox_to_anchor=(0.5, -0.10), fontsize=10, title="Algorithm Configuration", title_fontsize=11)
leg2 = fig.legend(handles=time_comp_patches, loc='lower center', ncol=2,
                  bbox_to_anchor=(0.5, -0.16), fontsize=10, title="Time Component", title_fontsize=11)

fig.suptitle("Consolidated Stacked Response Time across 9 SCSH Configurations", fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout()

out_rt = os.path.join(OUTPUT_DIR, "03_Consolidated_Response_Time_9Algos.png")
plt.savefig(out_rt, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
plt.close()
print(f"Salvato: {out_rt}")

print(f"\nTutti e 3 i grafici consolidati sono stati salvati nella cartella '{OUTPUT_DIR}/'.")