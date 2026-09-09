import os
import csv
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==============================================================================
# 1. CONFIGURAZIONE GENERALE E COLORI
# ==============================================================================
root_folder = "simulazioni_esp_10"
OUTPUT_DIR = "plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

ALGO_COLORS = {
    "DTS-base":                         "#F28E2B",  # Arancione
    "DTS-Optimal":                      "#4E79A7",  # Blu
    "Orbit-aware":                      "#59A14F",  # Verde
    "ILP-Hierarchical (Time)":          "#B6992D",  # Oro
    "ILP-Hierarchical (Energy)":        "#8C564B",  # Marrone
    "ILP-Centr (BS20, BT0.05, Time)":   "#E15759",  # Rosso brillante
    "ILP-Centr (BS20, BT0.05, Energy)": "#FF9D9A",  # Rosa
    "ILP-Centr (BS2, BT2, Time)":       "#79706E",  # Antracite
    "ILP-Centr (BS2, BT2, Energy)":     "#BAB0AC"   # Grigio chiaro
}

BETA_ORDER = [
    "Beta: (0.4, 0.35, 0.25)",
    "Beta: (0, 1, 0)",
    "Beta: (0, 0, 1)"
]
BETA_TITLES = {
    "Beta: (0.4, 0.35, 0.25)": "Mixed Workload - Beta (0.4, 0.35, 0.25)",
    "Beta: (0, 1, 0)":         "CPU-Intensive - Beta (0, 1, 0)",
    "Beta: (0, 0, 1)":         "Data-Intensive - Beta (0, 0, 1)"
}

ALPHA_ORDER = [
    "Alpha: (0.3, 0.5, 0.2)",
    "Alpha: (0, 0.7, 0.3)",
    "Alpha: (0, 0.3, 0.7)",
    "Alpha: (0, 1, 0)"
]
ALPHA_TITLES = {
    "Alpha: (0.3, 0.5, 0.2)": "Alpha (0.3, 0.5, 0.2) [Std]",
    "Alpha: (0, 0.7, 0.3)":   "Alpha (0, 0.7, 0.3) [L-heavy]",
    "Alpha: (0, 0.3, 0.7)":   "Alpha (0, 0.3, 0.7) [VL-heavy]",
    "Alpha: (0, 1, 0)":       "Alpha (0, 1, 0) [Pure L]"
}

CAUSE_KEYS = ["deadline", "insuff_cn", "insuff_c", "no_server", "ilp_infeasible", "sunset"]
CAUSE_LABELS = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]
CAUSE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

# ==============================================================================
# 2. PARSING DEI FILE CSV
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # 1. Arrival Rate
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    ar_val = int(round(1.0 / float(ar_match.group(1)))) if ar_match and float(ar_match.group(1)) <= 1.0 else (int(round(float(ar_match.group(1)))) if ar_match else None)

    # 2. Budget Energetico
    budget_match = re.search(r'(?:energy_budget|budget)[_=]?(\d+)', f_lower)
    budget_str = "40 kJ" if budget_match and int(budget_match.group(1)) in [40, 40000] else "80 kJ"

    # 3. Profilo Beta
    beta_str = None
    bm = re.search(r'bg_([\d.]+)_bcpui_([\d.]+)_bcpudi_([\d.]+)', f_lower)
    if bm:
        beta_str = f"Beta: ({float(bm.group(1)):g}, {float(bm.group(2)):g}, {float(bm.group(3)):g})"

    # 4. Profilo Alpha
    alpha_str = None
    am = re.search(r'am_([\d.]+)_?ah_([\d.]+)_?avh_([\d.]+)', f_lower)
    if am:
        alpha_str = f"Alpha: ({float(am.group(1)):g}, {float(am.group(2)):g}, {float(am.group(3)):g})"

    # 5. Algoritmo
    algo_val = None
    if "centralized" in f_lower or "ilp-centralized" in f_lower:
        obj_match = re.search(r'obj[_=]([a-z]+)', f_lower)
        if obj_match:
            mapping = obj_match.group(1).capitalize()
        elif "obj_energy" in f_lower or "energy_mapping" in f_lower:
            mapping = "Energy"
        else:
            mapping = "Time"

        if any(k in f_lower for k in ["batch_size_20", "bs_20", "bs20"]):
            algo_val = f"ILP-Centr (BS20, BT0.05, {mapping})"
        elif any(k in f_lower for k in ["batch_size_2", "bs_2", "bs2"]):
            algo_val = f"ILP-Centr (BS2, BT2, {mapping})"
        else:
            algo_val = f"ILP-Centr (BS20, BT0.05, {mapping})" if "0.05" in f_lower else f"ILP-Centr (BS2, BT2, {mapping})"

    elif "hierarchical" in f_lower or "ilph" in f_lower:
        pre_deadline = f_lower.split("deadline")[0] if "deadline" in f_lower else f_lower
        is_energy = bool(
            re.search(r'hierarchical[/\-_]+energy', f_lower)
            or "/hierarchical/energy/" in f_lower
            or "/energy/" in pre_deadline
            or "lexi_primary_energy" in f_lower
        )
        is_time = bool(
            re.search(r'hierarchical[/\-_]+time', f_lower)
            or "/hierarchical/time/" in f_lower
            or "/time/" in pre_deadline
            or "lexi_primary_time" in f_lower
        )
        if is_energy:
            algo_val = "ILP-Hierarchical (Energy)"
        elif is_time:
            algo_val = "ILP-Hierarchical (Time)"

    elif "orbitaware" in f_lower or "orbit-aware" in f_lower:
        algo_val = "Orbit-aware"
    elif "dts-apopt" in f_lower or "dts-optimal" in f_lower:
        algo_val = "DTS-Optimal"
    elif "dts-base" in f_lower:
        algo_val = "DTS-base"

    return ar_val, budget_str, algo_val, beta_str, alpha_str

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
# 3. CARICAMENTO E STRUTTURAZIONE DATI
# ==============================================================================
print(f"Scansione ricorsiva di '{root_folder}'...")
data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            ar, budget, algo, beta, alpha = extract_parameters(filepath)

            if None not in (ar, budget, algo, beta, alpha):
                all_ars.add(ar)
                data_store.setdefault(budget, {}).setdefault(beta, {}).setdefault(alpha, {}).setdefault(algo, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars))
budgets = [b for b in ["40 kJ", "80 kJ"] if b in data_store]
present_algos = [a for a in ALGO_ORDER if any(a in data_store[b].get(beta, {}).get(alpha, {}) for b in budgets for beta in data_store[b] for alpha in data_store[b][beta])]
present_betas = [b for b in BETA_ORDER if any(b in data_store[bdg] for bdg in budgets)]
present_alphas = [a for a in ALPHA_ORDER if any(a in data_store[bdg].get(b, {}) for bdg in budgets for b in present_betas)]

n_algos = len(present_algos)
n_ars = len(sorted_ars)

# Calcolo geometrico per barre raggruppate
step_w = 0.85 / n_algos
bar_w = step_w * 0.90
grp_w = n_algos * step_w
grp_space = 0.55
x_base = np.arange(n_ars) * (grp_w + grp_space)
offsets = np.linspace(-grp_w/2 + step_w/2, grp_w/2 - step_w/2, n_algos)

algo_patches = [mpatches.Patch(color=ALGO_COLORS[a], label=a) for a in present_algos]
cause_patches = [mpatches.Patch(color=CAUSE_COLORS[k], label=CAUSE_LABELS[k]) for k in range(len(CAUSE_LABELS))]
time_comp_patches = [
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='System Execution'),
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Network / Wait Time')
]

# ==============================================================================
# 4. GENERAZIONE GRAFICI: 3 FIGURE PER METRICA (1 PER CIASCUN BETA)
# ==============================================================================
for beta in present_betas:
    b_tag = re.sub(r'[^a-zA-Z0-9]', '_', beta).strip('_')
    b_title = BETA_TITLES.get(beta, beta)

    # --------------------------------------------------------------------------
    # METRICA 1: SUCCESS RATE (Griglia 2x4: Budget x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(len(budgets), len(present_alphas), figsize=(6 * len(present_alphas), 4.5 * len(budgets)), sharey=True, squeeze=False)

    for r_idx, budget in enumerate(budgets):
        for c_idx, alpha in enumerate(present_alphas):
            ax = axes[r_idx, c_idx]
            for i, algo in enumerate(present_algos):
                y_vals = []
                for ar in sorted_ars:
                    rows = data_store[budget].get(beta, {}).get(alpha, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    c, r = st["completed"], st["rejected"]
                    y_vals.append((c / (c + r) * 100) if (c + r) > 0 else 0.0)

                ax.bar(x_base + offsets[i], y_vals, width=bar_w,
                       color=ALGO_COLORS[algo], edgecolor='black', linewidth=0.3)

            for x in x_base[:-1]:
                ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.3)

            ax.set_title(f"{budget} | {ALPHA_TITLES.get(alpha, alpha)}", fontsize=11, fontweight='bold')
            ax.set_xticks(x_base)
            ax.set_xticklabels(sorted_ars, fontsize=10)
            ax.set_xlabel("Arrival Rate (req/s)", fontsize=10)
            ax.set_ylim(0, 105)
            ax.grid(axis='y', linestyle='--', alpha=0.4)
            if c_idx == 0:
                ax.set_ylabel("Success Rate (%)", fontsize=11)

    fig.legend(handles=algo_patches, loc='lower center', ncol=5,
               bbox_to_anchor=(0.5, -0.075), fontsize=11, title="Algorithm Configurations", title_fontsize=12)

    fig.suptitle(f"Success Rate across Arrival Rates: {b_title}", fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    out_sr = os.path.join(OUTPUT_DIR, f"01_Success_Rate_{b_tag}.png")
    plt.savefig(out_sr, bbox_inches='tight')
    plt.close()
    print(f"Salvato: {out_sr}")

    # --------------------------------------------------------------------------
    # METRICA 2: RESPONSE TIME (Griglia 2x4: Budget x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(len(budgets), len(present_alphas), figsize=(6 * len(present_alphas), 4.5 * len(budgets)), sharey=True, squeeze=False)
    max_rt = 0.0

    # Calcolo max_rt globale del subplot per allineare l'asse Y
    for budget in budgets:
        for alpha in present_alphas:
            for algo in present_algos:
                for ar in sorted_ars:
                    rows = data_store[budget].get(beta, {}).get(alpha, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    if st["completed"] > 0:
                        tot = st["total_time"] / st["completed"]
                        if tot > max_rt:
                            max_rt = tot

    for r_idx, budget in enumerate(budgets):
        for c_idx, alpha in enumerate(present_alphas):
            ax = axes[r_idx, c_idx]
            for i, algo in enumerate(present_algos):
                y_sys, y_diff = [], []
                for ar in sorted_ars:
                    rows = data_store[budget].get(beta, {}).get(alpha, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    comp = st["completed"]
                    sys_t = (st["sys_time"] / comp) if comp > 0 else 0.0
                    tot_t = (st["total_time"] / comp) if comp > 0 else 0.0
                    y_sys.append(sys_t)
                    y_diff.append(max(0.0, tot_t - sys_t))

                c = ALGO_COLORS[algo]
                ax.bar(x_base + offsets[i], y_sys, width=bar_w, color=c, edgecolor='black', linewidth=0.3)
                ax.bar(x_base + offsets[i], y_diff, width=bar_w, bottom=y_sys, color=c, alpha=0.35, edgecolor='black', linewidth=0.3)

            for x in x_base[:-1]:
                ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.3)

            ax.set_title(f"{budget} | {ALPHA_TITLES.get(alpha, alpha)}", fontsize=11, fontweight='bold')
            ax.set_xticks(x_base)
            ax.set_xticklabels(sorted_ars, fontsize=10)
            ax.set_xlabel("Arrival Rate (req/s)", fontsize=10)
            ax.set_ylim(0, max_rt * 1.15 if max_rt > 0 else 1.0)
            ax.grid(axis='y', linestyle='--', alpha=0.4)
            if c_idx == 0:
                ax.set_ylabel("Response Time (ms)", fontsize=11)

    leg1 = fig.legend(handles=algo_patches, loc='lower center', ncol=5,
                      bbox_to_anchor=(0.30, -0.075), fontsize=11, title="Algorithm Configurations", title_fontsize=12)
    leg2 = fig.legend(handles=time_comp_patches, loc='lower center', ncol=2,
                      bbox_to_anchor=(0.78, -0.075), fontsize=10, title="Time Component", title_fontsize=11)

    fig.suptitle(f"Stacked Response Time across Arrival Rates: {b_title}", fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    out_rt = os.path.join(OUTPUT_DIR, f"02_Response_Time_{b_tag}.png")
    plt.savefig(out_rt, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"Salvato: {out_rt}")

    # --------------------------------------------------------------------------
    # METRICA 3: REJECTION CAUSES (Griglia 2x4: Budget x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(len(budgets), len(present_alphas), figsize=(6 * len(present_alphas), 4.5 * len(budgets)), sharey=True, squeeze=False)

    for r_idx, budget in enumerate(budgets):
        for c_idx, alpha in enumerate(present_alphas):
            ax = axes[r_idx, c_idx]

            for i, algo in enumerate(present_algos):
                bottom = np.zeros(n_ars)
                for k_idx, key in enumerate(CAUSE_KEYS):
                    y_vals = []
                    for ar in sorted_ars:
                        rows = data_store[budget].get(beta, {}).get(alpha, {}).get(algo, {}).get(ar, [])
                        st = compute_stats(rows)
                        rej = st["rejected"]
                        y_vals.append((st[key] / rej * 100) if rej > 0 else 0.0)

                    ax.bar(x_base + offsets[i], y_vals, width=bar_w, bottom=bottom,
                           color=CAUSE_COLORS[k_idx], edgecolor='black', linewidth=0.2)
                    bottom += np.array(y_vals)

            for x in x_base[:-1]:
                ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.3)

            ax.set_title(f"{budget} | {ALPHA_TITLES.get(alpha, alpha)}", fontsize=11, fontweight='bold')
            ax.set_xticks(x_base)
            ax.set_xticklabels(sorted_ars, fontsize=10)
            ax.set_xlabel("Arrival Rate (req/s)", fontsize=10)
            ax.set_ylim(0, 105)
            ax.grid(axis='y', linestyle='--', alpha=0.4)
            if c_idx == 0:
                ax.set_ylabel("Rejection Breakdown (%)", fontsize=11)

    leg_cause = fig.legend(handles=cause_patches, loc='lower center', ncol=len(CAUSE_LABELS),
                           bbox_to_anchor=(0.25, -0.075), fontsize=11, title="Failure Causes", title_fontsize=12)
    leg_alg = fig.legend(handles=algo_patches, loc='lower center', ncol=5,
                         bbox_to_anchor=(0.75, -0.075), fontsize=10, title="Algorithms (Bar Order inside each Arrival Rate cluster)", title_fontsize=11)

    fig.suptitle(f"Rejection Causes Breakdown across Arrival Rates: {b_title}", fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    out_rej = os.path.join(OUTPUT_DIR, f"03_Rejection_Causes_{b_tag}.png")
    plt.savefig(out_rej, bbox_inches='tight', bbox_extra_artists=(leg_cause, leg_alg))
    plt.close()
    print(f"Salvato: {out_rej}")

print(f"\nGenerazione completata con successo! I 9 grafici sono pronti nella cartella '{OUTPUT_DIR}/'.")