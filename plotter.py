import os
import csv
import re
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

plt.rcParams['figure.dpi'] = 300

# ==============================================================================
# 1. CONFIGURAZIONE CARTELLA E 28 CONFIGURAZIONI
# ==============================================================================
root_folder = "simulazioni_esp_8"  # Cartella contenente i risultati

CONFIG_ORDER = [
    "BS:1 | BT:2 | Dijk:Energy",    "BS:1 | BT:2 | Dijk:Time",
    "BS:2 | BT:2 | Dijk:Energy",    "BS:2 | BT:2 | Dijk:Time",
    "BS:4 | BT:2 | Dijk:Energy",    "BS:4 | BT:2 | Dijk:Time",
    "BS:6 | BT:2 | Dijk:Energy",    "BS:6 | BT:2 | Dijk:Time",
    "BS:8 | BT:2 | Dijk:Energy",    "BS:8 | BT:2 | Dijk:Time",
    "BS:10 | BT:2 | Dijk:Energy",   "BS:10 | BT:2 | Dijk:Time",
    "BS:20 | BT:0.0 | Dijk:Energy", "BS:20 | BT:0.0 | Dijk:Time",
    "BS:20 | BT:0.05 | Dijk:Energy","BS:20 | BT:0.05 | Dijk:Time",
    "BS:20 | BT:0.1 | Dijk:Energy", "BS:20 | BT:0.1 | Dijk:Time",
    "BS:20 | BT:0.2 | Dijk:Energy", "BS:20 | BT:0.2 | Dijk:Time",
    "BS:20 | BT:0.4 | Dijk:Energy", "BS:20 | BT:0.4 | Dijk:Time",
    "BS:20 | BT:0.6 | Dijk:Energy", "BS:20 | BT:0.6 | Dijk:Time",
    "BS:20 | BT:0.8 | Dijk:Energy", "BS:20 | BT:0.8 | Dijk:Time",
    "BS:20 | BT:1.0 | Dijk:Energy", "BS:20 | BT:1.0 | Dijk:Time"
]

PAIRED_PALETTES = [
    ("#1f77b4", "#aec7e8"),  # BS:1  BT:2
    ("#ff7f0e", "#ffbb78"),  # BS:2  BT:2
    ("#2ca02c", "#98df8a"),  # BS:4  BT:2
    ("#bcbd22", "#dbdb8d"),  # BS:6  BT:2
    ("#17becf", "#9edae5"),  # BS:8  BT:2
    ("#d62728", "#ff9896"),  # BS:10 BT:2
    ("#4d4d4d", "#b3b3b3"),  # BS:20 BT:0.0
    ("#393b79", "#6b6ecf"),  # BS:20 BT:0.05
    ("#e6550d", "#fdae6b"),  # BS:20 BT:0.1
    ("#31a354", "#a1d99b"),  # BS:20 BT:0.2
    ("#756bb1", "#bcbddc"),  # BS:20 BT:0.4
    ("#b8860b", "#e7ba52"),  # BS:20 BT:0.6
    ("#de9ed6", "#f7b6d2"),  # BS:20 BT:0.8
    ("#525252", "#969696")   # BS:20 BT:1.0
]

CONFIG_COLORS = {}
for pair_idx, base_idx in enumerate(range(0, len(CONFIG_ORDER), 2)):
    c_dark, c_light = PAIRED_PALETTES[pair_idx]
    CONFIG_COLORS[CONFIG_ORDER[base_idx]] = c_dark
    CONFIG_COLORS[CONFIG_ORDER[base_idx + 1]] = c_light


# ==============================================================================
# 2. PARSING ED ESTRAZIONE PARAMETRI
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def format_bt(bt_val):
    for target in [2.0, 0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]:
        if abs(bt_val - target) < 1e-4:
            return "2" if target == 2.0 else str(target)
    return str(round(bt_val, 2))

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # 1. Arrival Rate
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_float = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_float)) if at_float <= 1.0 else int(round(at_float))
    else:
        ar_val = None

    # 2. Deadline
    dl_match = re.search(r'deadline[_=](\d+)', f_lower)
    dl_val = int(dl_match.group(1)) if dl_match else None

    # 3. Batch Size
    bs_match = re.search(r'(?:batch_size|bs)[_=](\d+)', f_lower)
    bs_val = int(bs_match.group(1)) if bs_match else None

    # 4. Batch Timeout
    bt_match = re.search(r'(?:batch_timeout|bt)[_=]([\d.]+)', f_lower)
    bt_val = float(bt_match.group(1)) if bt_match else None

    # 5. Mapping (ENERGY Mapping vs TIME Mapping)
    if any(k in f_lower for k in ["obj_energy", "energy_mapping", "opt_energy", "/energy/"]):
        mapping_str = "ENERGY"
    elif any(k in f_lower for k in ["obj_time", "time_mapping", "opt_time", "/time/"]):
        mapping_str = "TIME"
    else:
        mapping_str = "Default"

    # 6. Routing Algorithm (Dijkstra Energy vs Time)
    dijk_str = None
    dijk_weights = re.search(r'dijk_(?:w_r_)?([0-9.]+)_?(?:w_e_)?([0-9.]+)', f_lower)
    if dijk_weights:
        w_r = float(dijk_weights.group(1))
        w_e = float(dijk_weights.group(2))
        dijk_str = "Energy" if w_e > w_r else "Time"
    elif any(k in f_lower for k in ["dijk_energy", "dijkstra_energy", "r_algo_energy"]):
        dijk_str = "Energy"
    elif any(k in f_lower for k in ["dijk_time", "dijkstra_time", "r_algo_time"]):
        dijk_str = "Time"

    config_label = None
    if bs_val is not None and bt_val is not None and dijk_str is not None:
        bt_repr = format_bt(bt_val)
        config_label = f"BS:{bs_val} | BT:{bt_repr} | Dijk:{dijk_str}"

    return ar_val, dl_val, mapping_str, config_label

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
        "completed": completed,
        "rejected": rejected,
        "deadline": deadline,
        "insuff_cn": insuff_cn,
        "insuff_c": insuff_c,
        "no_server": no_server,
        "ilp_infeasible": ilp_infeasible,
        "sunset": sunset,
        "total_time": total_time,
        "sys_time": sys_time
    }


# ==============================================================================
# 3. RACCOLTA DATI
# ==============================================================================
print("Scansione risultati simulazioni in corso...")

data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            ar, dl, mapping, config = extract_parameters(filepath)

            if ar is not None and dl is not None and config is not None:
                all_ars.add(ar)
                group_key = (mapping, dl)

                if group_key not in data_store:
                    data_store[group_key] = {}
                if config not in data_store[group_key]:
                    data_store[group_key][config] = {}
                if ar not in data_store[group_key][config]:
                    data_store[group_key][config][ar] = []

                data_store[group_key][config][ar].extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars))
sorted_groups = sorted(list(data_store.keys()))

# ==============================================================================
# 4. GENERAZIONE GRAFICI PER CIASCUN MAPPING & DEADLINE
# ==============================================================================
for mapping, dl in sorted_groups:
    group_title = f"{mapping} Mapping, DL={dl}" if mapping != "Default" else f"DL={dl}"
    file_tag = f"{mapping.lower()}_mapping_dl_{dl}" if mapping != "Default" else f"dl_{dl}"

    present_configs = [c for c in CONFIG_ORDER if c in data_store[(mapping, dl)]]
    if not present_configs:
        continue

    print(f"\nGenerazione grafici per {group_title} ({len(present_configs)} configurazioni trovate)...")

    n_configs = len(present_configs)
    step_width = 0.030
    bar_width = 0.026
    group_width = n_configs * step_width
    group_spacing = 0.35

    x_base = np.arange(len(sorted_ars)) * (group_width + group_spacing)
    offsets = np.linspace(-group_width/2 + step_width/2, group_width/2 - step_width/2, n_configs)

    def draw_separators():
        for x in x_base[:-1]:
            plt.axvline(x + group_width/2 + group_spacing/2, color='gray', linestyle=':', alpha=0.35)

    # --------------------------------------------------------------------------
    # 1. SUCCESS RATE
    # --------------------------------------------------------------------------
    plt.figure(figsize=(26, 10))
    for i, cfg in enumerate(present_configs):
        y_vals = []
        for ar in sorted_ars:
            rows = data_store[(mapping, dl)].get(cfg, {}).get(ar, [])
            if not rows:
                y_vals.append(0.0)
                continue
            stats = compute_stats(rows)
            c, r = stats["completed"], stats["rejected"]
            y_vals.append((c / (c + r)) if (c + r) > 0 else 0.0)

        plt.bar(x_base + offsets[i], y_vals, width=bar_width,
                color=CONFIG_COLORS.get(cfg, "#333333"), edgecolor='black', linewidth=0.2, label=cfg)

    draw_separators()
    plt.title(f"Success Rate per Arrival Rate ({group_title})", fontsize=20)
    plt.ylabel("Success Rate (%)", fontsize=18)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=18)
    plt.ylim(0, 1.05)
    plt.xticks(x_base, sorted_ars, fontsize=15)
    plt.yticks(np.arange(0.0, 1.1, 0.1), [f"{v:.1f}" for v in np.arange(0.0, 1.1, 0.1)], fontsize=14)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=10, title="Configurations", title_fontsize=11)
    plt.savefig(f"01_Success_Rate_{file_tag}.png", bbox_inches='tight')
    plt.close()

    # --------------------------------------------------------------------------
    # 2. REJECTION CAUSES
    # --------------------------------------------------------------------------
    plt.figure(figsize=(26, 10))

    cause_keys = ["deadline", "insuff_cn", "insuff_c", "no_server", "ilp_infeasible", "sunset"]
    cause_labels = ["Deadline exceeded", "Insuff. CPU+NET", "Insuff. CPU", "No server found", "ILP Infeasible", "Sunset"]
    cause_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    for i, cfg in enumerate(present_configs):
        bottom = np.zeros(len(sorted_ars))
        for k_idx, key in enumerate(cause_keys):
            y_vals = []
            for ar in sorted_ars:
                rows = data_store[(mapping, dl)].get(cfg, {}).get(ar, [])
                if not rows:
                    y_vals.append(0.0)
                    continue
                stats = compute_stats(rows)
                rej = stats["rejected"]
                val = stats[key]
                y_vals.append((val / rej) if rej > 0 else 0.0)

            plt.bar(x_base + offsets[i], y_vals, width=bar_width, bottom=bottom,
                    color=cause_colors[k_idx], edgecolor='black', linewidth=0.2)
            bottom += np.array(y_vals)

    draw_separators()
    plt.title(f"Failure causes per Arrival Rate ({group_title})", fontsize=20)
    plt.ylabel("Rejection Rate (%)", fontsize=18)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=18)
    plt.ylim(0, 1.00)
    plt.xticks(x_base, sorted_ars, fontsize=15)
    plt.yticks(np.arange(0.0, 1.1, 0.1), [f"{v:.1f}" for v in np.arange(0.0, 1.1, 0.1)], fontsize=14)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    cause_patches = [mpatches.Patch(color=cause_colors[idx], label=cause_labels[idx]) for idx in range(len(cause_labels))]
    legend_causes = plt.legend(handles=cause_patches, loc='upper left', bbox_to_anchor=(1.01, 1.0),
                               fontsize=11, title="Failure Causes", title_fontsize=13)

    cfg_lines = [Line2D([0], [0], color=CONFIG_COLORS.get(cfg, '#555'), lw=3, label=cfg) for cfg in present_configs]
    legend_cfgs = plt.legend(handles=cfg_lines, loc='upper left', bbox_to_anchor=(1.01, 0.72),
                             fontsize=10, title="Configurations", title_fontsize=11)
    plt.gca().add_artist(legend_causes)

    plt.savefig(f"02_Failure_Causes_{file_tag}.png", bbox_inches='tight',
                bbox_extra_artists=(legend_causes, legend_cfgs))
    plt.close()

    # --------------------------------------------------------------------------
    # 3. STACKED RESPONSE TIME
    # --------------------------------------------------------------------------
    plt.figure(figsize=(26, 10))
    max_val = 0.0

    for i, cfg in enumerate(present_configs):
        y_sys = []
        y_diff = []
        for ar in sorted_ars:
            rows = data_store[(mapping, dl)].get(cfg, {}).get(ar, [])
            if not rows:
                y_sys.append(0.0)
                y_diff.append(0.0)
                continue
            stats = compute_stats(rows)
            comp = stats["completed"]
            sys_t = stats["sys_time"] / comp if comp > 0 else 0.0
            tot_t = stats["total_time"] / comp if comp > 0 else 0.0

            y_sys.append(sys_t)
            y_diff.append(max(0.0, tot_t - sys_t))
            if tot_t > max_val:
                max_val = tot_t

        c = CONFIG_COLORS.get(cfg, "#333333")
        plt.bar(x_base + offsets[i], y_sys, width=bar_width, color=c, edgecolor='black', linewidth=0.2)
        plt.bar(x_base + offsets[i], y_diff, width=bar_width, bottom=y_sys,
                color=c, alpha=0.35, edgecolor='black', linewidth=0.2)

    draw_separators()
    plt.title(f"Stacked Response Time per Arrival Rate ({group_title})", fontsize=20)
    plt.ylabel("Response Time (ms)", fontsize=18)
    plt.xlabel("Arrival Rate (req/sec)", fontsize=18)
    plt.xticks(x_base, sorted_ars, fontsize=15)
    plt.ylim(0, max_val * 1.15 if max_val > 0 else 1.5)
    plt.yticks(fontsize=14)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    config_patches_rt = [mpatches.Patch(color=CONFIG_COLORS.get(cfg, '#555'), label=cfg) for cfg in present_configs]
    legend_cfgs_rt = plt.legend(handles=config_patches_rt, loc='upper left', bbox_to_anchor=(1.01, 1.0),
                                fontsize=10, title="Configurations", title_fontsize=11)

    time_patches = [
        mpatches.Patch(facecolor='black', edgecolor='black', alpha=1.0, label='System Execution (Bottom)'),
        mpatches.Patch(facecolor='black', edgecolor='black', alpha=0.35, label='Network/Wait Time (Top)')
    ]
    legend_time = plt.legend(handles=time_patches, loc='upper left', bbox_to_anchor=(1.01, 0.12),
                             fontsize=11, title="Time Component", title_fontsize=12)
    plt.gca().add_artist(legend_cfgs_rt)

    plt.savefig(f"03_Response_Time_{file_tag}.png", bbox_inches='tight',
                bbox_extra_artists=(legend_cfgs_rt, legend_time))
    plt.close()

print("\nElaborazione terminata con successo.")