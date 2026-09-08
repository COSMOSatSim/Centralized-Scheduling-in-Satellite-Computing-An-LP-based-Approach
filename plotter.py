import os
import csv
import re
import math
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==============================================================================
# 1. PARAMETRI E COSTANTI
# ==============================================================================
root_folder = "simulazioni_esp_10"

SUNSET_WEIGHTS = [2, 4, 6, 8, 10, 1000, 5000, 10000]
PRIMARY_WEIGHTS = [10, 50, 1000]

# Palette per alpha (Primary Weight)
ALPHA_COLORS = {
    10:   "#386cb0",  # Blu
    50:   "#fdb462",  # Ambra dorata
    1000: "#7fc97f"   # Verde
}

ALPHA_HATCHES = {
    10:   "",
    50:   "//",
    1000: "++"
}

# Cause di fallimento
CAUSE_KEYS = ["deadline", "insuff_cn", "insuff_c", "no_server", "ilp_infeasible", "sunset"]
CAUSE_LABELS = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]
CAUSE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

# ==============================================================================
# 2. PARSING E STATISTICHE
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # Arrival Rate
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_f = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_f)) if at_f <= 1.0 else int(round(at_f))
    else:
        ar_val = None

    # Batch config
    bs_match = re.search(r'batch_size[_=](\d+)', f_lower)
    bt_match = re.search(r'batch_timeout[_=]([\d.]+)', f_lower)
    bs_val = int(bs_match.group(1)) if bs_match else None
    bt_val = float(bt_match.group(1)) if bt_match else None

    # Objective
    obj_match = re.search(r'obj[_=]([a-z]+)', f_lower)
    obj_val = obj_match.group(1).capitalize() if obj_match else "Unknown"

    # Dijkstra
    dijk_match = re.search(r'dijk[_=]([0-9.]+)[_=]([0-9.]+)', f_lower)
    if dijk_match:
        w_r, w_e = float(dijk_match.group(1)), float(dijk_match.group(2))
        dijk_str = "Dijk-Energy" if w_e > w_r else "Dijk-Time"
    else:
        dijk_str = "Dijk-Default"

    # Alpha & Gamma
    pw_match = re.search(r'pw[_=](\d+)', f_lower)
    pw_val = int(pw_match.group(1)) if pw_match else None

    sunw_match = re.search(r'sunw[_=](\d+)', f_lower)
    sunw_val = int(sunw_match.group(1)) if sunw_match else None

    scenario_key = None
    if bs_val is not None and bt_val is not None:
        scenario_key = f"{obj_val} | BS:{bs_val} BT:{bt_val} | {dijk_str}"

    return ar_val, scenario_key, pw_val, sunw_val

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
# 3. CARICAMENTO DATI
# ==============================================================================
print("Lettura file da 'result'...")
data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            ar, scenario, pw, sunw = extract_parameters(filepath)

            if None not in (ar, scenario, pw, sunw):
                all_ars.add(ar)
                data_store.setdefault(pw, {}).setdefault(scenario, {}).setdefault(sunw, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars))
present_alphas = sorted(list(data_store.keys()))
all_scenarios = sorted(list({s for p in present_alphas for s in data_store[p].keys()}))

if not present_alphas or not all_scenarios:
    print("Nessun dato corrispondente trovato in 'result'.")
    exit()

OUTPUT_DIR = "plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Impostazione geometria griglia
num_sc = len(all_scenarios)
ncols = min(4, num_sc)
nrows = math.ceil(num_sc / ncols)

all_sunws = [w for w in SUNSET_WEIGHTS if any(w in data_store[p][s] for p in present_alphas for s in all_scenarios if s in data_store[p])]

n_alphas = len(present_alphas)
step_a = 0.85 / n_alphas
bar_a = step_a * 0.90
grp_a = n_alphas * step_a
grp_space_a = 0.50

x_sunw = np.arange(len(all_sunws)) * (grp_a + grp_space_a)
offsets_a = np.linspace(-grp_a/2 + step_a/2, grp_a/2 - step_a/2, n_alphas)

# ==============================================================================
# 4. GENERAZIONE MATRICI CROSS-SENSITIVITY (AR = 8, 10 req/s)
# ==============================================================================
for target_ar in sorted_ars:
    print(f"\n--- Generazione Cross-Sensitivity per Arrival Rate = {target_ar} req/s ---")

    # --------------------------------------------------------------------------
    # 1. SUCCESS RATE (Gamma x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.5 * nrows), sharey=True, squeeze=False)
    for idx, sc in enumerate(all_scenarios):
        ax = axes[idx // ncols, idx % ncols]
        for a_idx, pw in enumerate(present_alphas):
            y_vals = []
            for w in all_sunws:
                rows = data_store.get(pw, {}).get(sc, {}).get(w, {}).get(target_ar, [])
                st = compute_stats(rows)
                c, r = st["completed"], st["rejected"]
                y_vals.append((c / (c + r) * 100) if (c + r) > 0 else 0.0)

            ax.bar(x_sunw + offsets_a[a_idx], y_vals, width=bar_a,
                   color=ALPHA_COLORS.get(pw, "#444"), edgecolor='black', linewidth=0.3)

        for x in x_sunw[:-1]:
            ax.axvline(x + grp_a/2 + grp_space_a/2, color='gray', linestyle=':', alpha=0.3)
        ax.set_title(sc, fontsize=12, fontweight='bold')
        ax.set_xticks(x_sunw)
        ax.set_xticklabels([str(w) for w in all_sunws], fontsize=9, rotation=35)
        ax.set_xlabel("Sunset Weight ($\gamma$)", fontsize=10)
        ax.set_ylim(0, 105)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        if idx % ncols == 0:
            ax.set_ylabel("Success Rate (%)", fontsize=11)

    for idx in range(num_sc, nrows * ncols):
        fig.delaxes(axes[idx // ncols, idx % ncols])

    alpha_patches = [mpatches.Patch(color=ALPHA_COLORS.get(p, "#444"), label=f"$\\alpha = {p}$") for p in present_alphas]
    fig.legend(handles=alpha_patches, loc='lower center', ncol=len(present_alphas),
               bbox_to_anchor=(0.5, -0.04), fontsize=11, title="Primary Weight ($\mathbf{\\alpha}$)", title_fontsize=12)
    fig.suptitle(f"Cross-Sensitivity Success Rate ($\mathbf{{\\gamma \\times \\alpha}}$) at {target_ar} req/s", fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"01_Cross_Success_Rate_AR_{target_ar}.png"), bbox_inches='tight')
    plt.close()
    print(f"Salvato: 01_Cross_Success_Rate_AR_{target_ar}.png")

    # --------------------------------------------------------------------------
    # 2. REJECTION CAUSES (Gamma x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.5 * nrows), sharey=True, squeeze=False)
    for idx, sc in enumerate(all_scenarios):
        ax = axes[idx // ncols, idx % ncols]
        for a_idx, pw in enumerate(present_alphas):
            bottom = np.zeros(len(all_sunws))
            for k_idx, key in enumerate(CAUSE_KEYS):
                y_vals = []
                for w in all_sunws:
                    rows = data_store.get(pw, {}).get(sc, {}).get(w, {}).get(target_ar, [])
                    st = compute_stats(rows)
                    rej = st["rejected"]
                    y_vals.append((st[key] / rej * 100) if rej > 0 else 0.0)

                ax.bar(x_sunw + offsets_a[a_idx], y_vals, width=bar_a, bottom=bottom,
                       color=CAUSE_COLORS[k_idx], edgecolor='black', linewidth=0.25,
                       hatch=ALPHA_HATCHES.get(pw, ""))
                bottom += np.array(y_vals)

        for x in x_sunw[:-1]:
            ax.axvline(x + grp_a/2 + grp_space_a/2, color='gray', linestyle=':', alpha=0.3)
        ax.set_title(sc, fontsize=12, fontweight='bold')
        ax.set_xticks(x_sunw)
        ax.set_xticklabels([str(w) for w in all_sunws], fontsize=9, rotation=35)
        ax.set_xlabel("Sunset Weight ($\gamma$)", fontsize=10)
        ax.set_ylim(0, 105)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        if idx % ncols == 0:
            ax.set_ylabel("Rejection Rate (%)", fontsize=11)

    for idx in range(num_sc, nrows * ncols):
        fig.delaxes(axes[idx // ncols, idx % ncols])

    cause_patches = [mpatches.Patch(color=CAUSE_COLORS[k], label=CAUSE_LABELS[k]) for k in range(len(CAUSE_LABELS))]
    alpha_hatch_patches = [mpatches.Patch(facecolor='white', edgecolor='black', hatch=ALPHA_HATCHES.get(p, ""), label=f"$\\alpha={p}$") for p in present_alphas]

    leg1 = fig.legend(handles=cause_patches, loc='lower center', ncol=len(CAUSE_LABELS),
                      bbox_to_anchor=(0.22, -0.05), fontsize=10, title="Failure Causes", title_fontsize=11)
    leg2 = fig.legend(handles=alpha_hatch_patches, loc='lower center', ncol=len(present_alphas),
                      bbox_to_anchor=(0.78, -0.05), fontsize=10, title="Primary Weight ($\mathbf{\\alpha}$) Pattern", title_fontsize=11)

    fig.suptitle(f"Cross-Sensitivity Failure Causes ($\mathbf{{\\gamma \\times \\alpha}}$) at {target_ar} req/s", fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"02_Cross_Failure_Causes_AR_{target_ar}.png"),
                bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"Salvato: 02_Cross_Failure_Causes_AR_{target_ar}.png")

    # --------------------------------------------------------------------------
    # 3. RESPONSE TIME (Gamma x Alpha)
    # --------------------------------------------------------------------------
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.5 * nrows), squeeze=False)
    max_rt = 0.0

    for idx, sc in enumerate(all_scenarios):
        ax = axes[idx // ncols, idx % ncols]
        for a_idx, pw in enumerate(present_alphas):
            y_sys, y_diff = [], []
            for w in all_sunws:
                rows = data_store.get(pw, {}).get(sc, {}).get(w, {}).get(target_ar, [])
                st = compute_stats(rows)
                comp = st["completed"]
                sys_t = (st["sys_time"] / comp) if comp > 0 else 0.0
                tot_t = (st["total_time"] / comp) if comp > 0 else 0.0

                y_sys.append(sys_t)
                y_diff.append(max(0.0, tot_t - sys_t))
                if tot_t > max_rt:
                    max_rt = tot_t

            c = ALPHA_COLORS.get(pw, "#444")
            ax.bar(x_sunw + offsets_a[a_idx], y_sys, width=bar_a, color=c, edgecolor='black', linewidth=0.3)
            ax.bar(x_sunw + offsets_a[a_idx], y_diff, width=bar_a, bottom=y_sys, color=c, alpha=0.35, edgecolor='black', linewidth=0.3)

        for x in x_sunw[:-1]:
            ax.axvline(x + grp_a/2 + grp_space_a/2, color='gray', linestyle=':', alpha=0.3)
        ax.set_title(sc, fontsize=12, fontweight='bold')
        ax.set_xticks(x_sunw)
        ax.set_xticklabels([str(w) for w in all_sunws], fontsize=9, rotation=35)
        ax.set_xlabel("Sunset Weight ($\gamma$)", fontsize=10)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        if idx % ncols == 0:
            ax.set_ylabel("Response Time (ms)", fontsize=11)

    for idx in range(num_sc):
        axes[idx // ncols, idx % ncols].set_ylim(0, max_rt * 1.15 if max_rt > 0 else 1.0)
    for idx in range(num_sc, nrows * ncols):
        fig.delaxes(axes[idx // ncols, idx % ncols])

    rt_alpha_patches = [mpatches.Patch(color=ALPHA_COLORS.get(p, "#444"), label=f"$\\alpha = {p}$") for p in present_alphas]
    rt_comp_patches = [
        mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='System Execution (Solid)'),
        mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Network/Wait Time (Translucent)')
    ]
    leg_rt1 = fig.legend(handles=rt_alpha_patches, loc='lower center', ncol=len(present_alphas),
                         bbox_to_anchor=(0.22, -0.05), fontsize=10, title="Primary Weight ($\mathbf{\\alpha}$)", title_fontsize=11)
    leg_rt2 = fig.legend(handles=rt_comp_patches, loc='lower center', ncol=2,
                         bbox_to_anchor=(0.78, -0.05), fontsize=10, title="Component Breakdown", title_fontsize=11)

    fig.suptitle(f"Cross-Sensitivity Response Time ($\mathbf{{\\gamma \\times \\alpha}}$) at {target_ar} req/s", fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"03_Cross_Response_Time_AR_{target_ar}.png"),
                bbox_inches='tight', bbox_extra_artists=(leg_rt1, leg_rt2))
    plt.close()
    print(f"Salvato: 03_Cross_Response_Time_AR_{target_ar}.png")

print(f"\nTutte le matrici di cross-sensitivity sono state salvate con successo in '{OUTPUT_DIR}'.")