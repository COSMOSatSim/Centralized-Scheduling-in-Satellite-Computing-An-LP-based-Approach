import os
import re
import csv
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# ==============================================================================
# 1. CONFIGURAZIONE SORGENTI E ARCHETIPI
# ==============================================================================
DATA_SOURCES = {
    'Prima': 'simulazioni_esp_8',
    'Dopo':  'simulazioni_esp_11'
}

OUTPUT_DIR = 'plots_confronto_prima_dopo'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_DL_PREFERENCE = 20

ORDERED_CONFIGS = [
    'BS:2 | BT:2 [Prima]',
    'BS:2 | BT:2 [Dopo]',
    'BS:20 | BT:0.05 [Prima]',
    'BS:20 | BT:0.05 [Dopo]'
]

CONFIG_COLORS = {
    'BS:2 | BT:2 [Prima]':     '#1f77b4',  # Blu scuro
    'BS:2 | BT:2 [Dopo]':      '#aec7e8',  # Azzurro pastello
    'BS:20 | BT:0.05 [Prima]': '#d95f02',  # Arancione scuro
    'BS:20 | BT:0.05 [Dopo]':  '#fdbe85'   # Salmone chiaro
}

CONFIG_HATCHES = {
    'BS:2 | BT:2 [Prima]':     '',
    'BS:2 | BT:2 [Dopo]':      '///',
    'BS:20 | BT:0.05 [Prima]': '..',
    'BS:20 | BT:0.05 [Dopo]':  'xx'
}

CAUSE_KEYS = ['deadline', 'insuff_cn', 'insuff_c', 'no_server', 'ilp_infeasible', 'sunset']
CAUSE_LABELS = ['Deadline exceeded', 'Insuff. CPU+NET', 'Insuff. CPU', 'No server found', 'ILP Infeasible', 'Sunset']
CAUSE_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

# ==============================================================================
# 2. LOCALIZZAZIONE CARTELLE E PARSER ROBUSTO
# ==============================================================================
def resolve_folder_path(folder_name):
    candidates = [
        folder_name,
        os.path.join('..', folder_name),
        os.path.join('.', folder_name),
        os.path.join('simulazioni', folder_name)
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    for root, dirs, _ in os.walk('.'):
        for d in dirs:
            if folder_name.lower() in d.lower():
                return os.path.join(root, d)
    return folder_name

def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath, source_tag):
    f_norm = filepath.replace('\\', '/')
    f_lower = f_norm.lower()
    parts = f_lower.split('/')

    # 1. Arrival Rate
    ar_val = None
    ar_match = re.search(r'(?:arr_rate|arrival_rate|ar|rate|lambda)[_=:\-\s]*([\d.]+)', f_lower)
    if ar_match:
        v = float(ar_match.group(1))
        ar_val = int(round(1.0 / v)) if v < 1.0 else int(round(v))
    else:
        at_match = re.search(r'at[_=:\-\s]*([\d.]+)', f_lower)
        if at_match:
            at_f = float(at_match.group(1))
            ar_val = int(round(1.0 / at_f)) if at_f <= 1.0 else int(round(at_f))

    # 2. Deadline
    dl_match = re.search(r'(?:deadline|dl)[_=:\-\s]*(\d+)', f_lower)
    dl_val = int(dl_match.group(1)) if dl_match else 20

    # 3. Objective Mapping Blindato (evita false corrispondenze con energy_budget e batch_timeout)
    mapping_str = None
    for p in parts[:-1]:
        if p in ['obj_energy', 'opt_energy', 'energy_mapping', 'energy']:
            mapping_str = 'ENERGY'
            break
        elif p in ['obj_time', 'opt_time', 'time_mapping', 'time']:
            mapping_str = 'TIME'
            break

    if mapping_str is None:
        obj_match = re.search(r'(?:obj|opt|mapping)[_=:\-\s]*(energy|time)', f_lower)
        if obj_match:
            mapping_str = obj_match.group(1).upper()

    if mapping_str is None:
        # Fallback posizionale su /energy/ o /time/
        if '/energy/' in f_norm:
            mapping_str = 'ENERGY'
        elif '/time/' in f_norm:
            mapping_str = 'TIME'

    # 4. Routing Dijkstra: SELEZIONA SOLO DIJKSTRA-TIME
    dijk_str = 'Time'
    dijk_weights = re.search(r'dijk[_=]?(?:w_r_)?([0-9.]+)[_=-]?(?:w_e_)?([0-9.]+)', f_lower)
    if dijk_weights:
        w_r, w_e = float(dijk_weights.group(1)), float(dijk_weights.group(2))
        dijk_str = 'Energy' if w_e > w_r else 'Time'
    elif any(k in f_lower for k in ['dijk_energy', 'dijkstra_energy', 'r_algo_energy']):
        dijk_str = 'Energy'
    elif any(k in f_lower for k in ['dijk_time', 'dijkstra_time', 'r_algo_time']):
        dijk_str = 'Time'

    if dijk_str == 'Energy':
        return None, None, None, None

    # 5. Batch Size e Timeout (gestisce anche '0_05')
    bs_match = re.search(r'(?:batch_size|bs)[_=:\-\s]*(\d+)', f_lower)
    bt_match = re.search(r'(?:batch_timeout|bt|timeout)[_=:\-\s]*([\d._]+)', f_lower)

    if not (bs_match and bt_match):
        return None, None, None, None

    bs_val = int(bs_match.group(1))
    raw_bt = bt_match.group(1).replace('_', '.')
    try:
        bt_val = float(raw_bt)
    except ValueError:
        return None, None, None, None

    is_bs2  = (bs_val == 2) and (abs(bt_val - 2.0) < 0.1)
    is_bs20 = (bs_val == 20) and (abs(bt_val - 0.05) < 0.02)

    if not (is_bs2 or is_bs20):
        return None, None, None, None

    bt_label = '2' if is_bs2 else '0.05'
    config_label = f"BS:{bs_val} | BT:{bt_label} [{source_tag}]"

    return ar_val, dl_val, mapping_str, config_label

def compute_stats(lines):
    completed = rejected = deadline = insuff_cn = insuff_c = no_server = ilp_infeasible = sunset = 0
    total_time = sys_time = 0.0

    for line in lines:
        if len(line) <= 26:
            continue
        status = str(line[2]).strip()
        if status == 'Completed':
            completed += 1
            if str(line[26]).strip() != 'N/A':
                total_time += float(line[9]) + float(line[15]) + float(line[26])
                sys_time += float(line[9])
        elif status == 'Rejected':
            rejected += 1
            reason = str(line[23]).lower()
            if 'deadline' in reason:
                deadline += 1
            elif 'energy' in reason:
                if 'net' in reason:
                    insuff_cn += 1
                else:
                    insuff_c += 1
            elif 'route' in reason:
                no_server += 1
            elif 'infeasible' in reason:
                ilp_infeasible += 1
            elif 'sunset' in reason:
                sunset += 1

    return {
        'completed': completed, 'rejected': rejected,
        'deadline': deadline, 'insuff_cn': insuff_cn, 'insuff_c': insuff_c,
        'no_server': no_server, 'ilp_infeasible': ilp_infeasible, 'sunset': sunset,
        'total_time': total_time, 'sys_time': sys_time
    }

# ==============================================================================
# 3. SCANSIONE DATI E ALLINEAMENTO DINAMICO
# ==============================================================================
print("\n================ DIAGNOSTICA CARICAMENTO ================")
data_store = {}
all_ars = set()

for source_tag, folder_name in DATA_SOURCES.items():
    actual_path = resolve_folder_path(folder_name)
    if not os.path.exists(actual_path):
        print(f"[-] Cartella '{folder_name}' NON trovata! Verifica il path.")
        continue

    csv_count = 0
    parsed_count = 0
    mapping_counts = {'ENERGY': 0, 'TIME': 0}

    for root, _, files in os.walk(actual_path):
        for file in files:
            if file.endswith('.csv'):
                csv_count += 1
                filepath = os.path.join(root, file)
                ar, dl, mapping, config_label = extract_parameters(filepath, source_tag)

                if ar is not None and config_label is not None and mapping in ['ENERGY', 'TIME']:
                    parsed_count += 1
                    mapping_counts[mapping] += 1
                    all_ars.add(ar)
                    group_key = (mapping, dl)
                    data_store.setdefault(group_key, {}).setdefault(config_label, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

    print(f"[+] '{source_tag}' -> Path: {actual_path}")
    print(f"    - File .csv totali trovati: {csv_count}")
    print(f"    - File validati (BS2/BS20, Dijkstra-Time): {parsed_count}")
    print(f"      * Energy Mapping: {mapping_counts['ENERGY']}")
    print(f"      * Time Mapping:   {mapping_counts['TIME']}")

sorted_ars = sorted(list(all_ars)) if all_ars else [2, 3, 4, 6, 8, 10]

dls_prima = {dl for (m, dl), cfgs in data_store.items() if any('[Prima]' in c for c in cfgs)}
dls_dopo  = {dl for (m, dl), cfgs in data_store.items() if any('[Dopo]' in c for c in cfgs)}

print(f"\nDeadlines individuate: Prima={dls_prima}, Dopo={dls_dopo}")

if TARGET_DL_PREFERENCE in dls_prima and TARGET_DL_PREFERENCE in dls_dopo:
    dl_prima_use = dl_dopo_use = TARGET_DL_PREFERENCE
elif dls_prima.intersection(dls_dopo):
    dl_prima_use = dl_dopo_use = sorted(list(dls_prima.intersection(dls_dopo)))[0]
else:
    dl_dopo_use = sorted(list(dls_dopo))[0] if dls_dopo else TARGET_DL_PREFERENCE
    dl_prima_use = sorted(list(dls_prima))[0] if dls_prima else TARGET_DL_PREFERENCE

mappings_to_plot = ['ENERGY', 'TIME']

unified_plot_data = {}
for m in mappings_to_plot:
    unified_plot_data[m] = {}
    for cfg, ar_dict in data_store.get((m, dl_prima_use), {}).items():
        if '[Prima]' in cfg:
            unified_plot_data[m][cfg] = ar_dict
    for cfg, ar_dict in data_store.get((m, dl_dopo_use), {}).items():
        if '[Dopo]' in cfg:
            unified_plot_data[m][cfg] = ar_dict

present_configs = [c for c in ORDERED_CONFIGS if any(c in unified_plot_data[m] for m in mappings_to_plot)]
n_cfg = len(present_configs)

print(f"Configurazioni finali pronte a grafico ({n_cfg}): {present_configs}\n")

if n_cfg == 0:
    print("[ERRORE] Nessuna configurazione idonea estratta.")
    exit()

# Geometria spaziale delle barre
step_w = 0.85 / n_cfg
bar_w = step_w * 0.88
grp_w = n_cfg * step_w
grp_space = 0.55
x_base = np.arange(len(sorted_ars)) * (grp_w + grp_space)
offsets = np.linspace(-grp_w/2 + step_w/2, grp_w/2 - step_w/2, n_cfg)

def draw_cluster_separators(ax):
    for x in x_base[:-1]:
        ax.axvline(x + grp_w/2 + grp_space/2, color='gray', linestyle=':', alpha=0.45)

dl_str = f"{dl_prima_use}%" if dl_prima_use == dl_dopo_use else f"Prima: {dl_prima_use}%, Dopo: {dl_dopo_use}%"

# ==============================================================================
# 4. GENERAZIONE FIGURE COMPARATIVE (SENZA WARNING E A ZERO SOVRAPPOSIZIONI)
# ==============================================================================

# FIGURA 1: SUCCESS RATE
fig, axes = plt.subplots(1, 2, figsize=(16, 6.2), sharey=True, gridspec_kw={'wspace': 0.08})
for m_idx, mapping in enumerate(mappings_to_plot):
    ax = axes[m_idx]
    grp_dict = unified_plot_data[mapping]
    for i, cfg in enumerate(present_configs):
        y_vals = []
        for ar in sorted_ars:
            rows = grp_dict.get(cfg, {}).get(ar, [])
            st = compute_stats(rows)
            c, r = st['completed'], st['rejected']
            y_vals.append((c / (c + r) * 100) if (c + r) > 0 else 0.0)

        ax.bar(x_base + offsets[i], y_vals, width=bar_w,
               color=CONFIG_COLORS[cfg], edgecolor='black', linewidth=0.4)

    draw_cluster_separators(ax)
    ax.set_title(f"{mapping.capitalize()} Mapping", fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11)
    ax.set_xticks(x_base)
    ax.set_xticklabels([f"{ar}" for ar in sorted_ars], fontsize=10, fontweight='bold')
    ax.set_ylim(0, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if m_idx == 0:
        ax.set_ylabel('Success Rate (%)', fontsize=12)

fig.subplots_adjust(top=0.90, bottom=0.20, left=0.06, right=0.98, wspace=0.08)

cfg_patches = [mpatches.Patch(facecolor=CONFIG_COLORS[c], edgecolor='black', linewidth=0.5, label=c) for c in present_configs]
fig.legend(handles=cfg_patches, loc='center', ncol=min(4, n_cfg), bbox_to_anchor=(0.5, 0.06),
           fontsize=9.5, title="Evaluated Configurations (Dijkstra-Time)", title_fontsize=10.5,
           frameon=True, facecolor='white', edgecolor='#cccccc')

fig.suptitle(f"Success Rate Comparison: Prima vs Dopo (Dijkstra-Time, $\\Delta D$ = {dl_str})", fontsize=14, fontweight='bold', y=0.97)
out_sr = os.path.join(OUTPUT_DIR, '01_Confronto_Success_Rate_DijkTime.png')
plt.savefig(out_sr, bbox_inches='tight')
plt.close()
print(f"[OK] Generato: {out_sr}")

# FIGURA 2: FAILURE CAUSES BREAKDOWN
fig, axes = plt.subplots(1, 2, figsize=(17, 6.8), sharey=True, gridspec_kw={'wspace': 0.08})
for m_idx, mapping in enumerate(mappings_to_plot):
    ax = axes[m_idx]
    grp_dict = unified_plot_data[mapping]
    for i, cfg in enumerate(present_configs):
        bottom = np.zeros(len(sorted_ars))
        for k_idx, key in enumerate(CAUSE_KEYS):
            y_vals = []
            for ar in sorted_ars:
                rows = grp_dict.get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                rej = st['rejected']
                y_vals.append((st[key] / rej * 100) if rej > 0 else 0.0)

            ax.bar(x_base + offsets[i], y_vals, width=bar_w, bottom=bottom,
                   color=CAUSE_COLORS[k_idx], hatch=CONFIG_HATCHES[cfg], edgecolor='black', linewidth=0.3)
            bottom += np.array(y_vals)

    draw_cluster_separators(ax)
    ax.set_title(f"{mapping.capitalize()} Mapping", fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11)
    ax.set_xticks(x_base)
    ax.set_xticklabels([f"{ar}" for ar in sorted_ars], fontsize=10, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if m_idx == 0:
        ax.set_ylabel('Rejection Breakdown (%)', fontsize=12)

fig.subplots_adjust(top=0.90, bottom=0.23, left=0.06, right=0.98, wspace=0.08)

cause_patches = [mpatches.Patch(facecolor=CAUSE_COLORS[k], edgecolor='black', linewidth=0.5, label=CAUSE_LABELS[k]) for k in range(len(CAUSE_LABELS))]
pattern_patches = [mpatches.Patch(facecolor='white', edgecolor='black', linewidth=0.5, hatch=CONFIG_HATCHES[c], label=c) for c in present_configs]

fig.legend(handles=cause_patches, loc='center', ncol=3, bbox_to_anchor=(0.30, 0.075),
           fontsize=8.5, title="Failure Causes", title_fontsize=9.5, frameon=True, facecolor='white', edgecolor='#cccccc')
fig.legend(handles=pattern_patches, loc='center', ncol=min(2, math.ceil(n_cfg/2)), bbox_to_anchor=(0.76, 0.075),
           fontsize=8, title="Configurations (Texture Pattern)", title_fontsize=9.5, frameon=True, facecolor='white', edgecolor='#cccccc')

fig.suptitle(f"Failure Causes Evolution: Prima vs Dopo (Dijkstra-Time, $\\Delta D$ = {dl_str})", fontsize=14, fontweight='bold', y=0.97)
out_fc = os.path.join(OUTPUT_DIR, '02_Confronto_Failure_Causes_DijkTime.png')
plt.savefig(out_fc, bbox_inches='tight')
plt.close()
print(f"[OK] Generato: {out_fc}")

# FIGURA 3: RESPONSE TIME BREAKDOWN
fig, axes = plt.subplots(1, 2, figsize=(16, 6.2), sharey=True, gridspec_kw={'wspace': 0.08})
max_rt = 0.0
for m in mappings_to_plot:
    grp_dict = unified_plot_data[m]
    for cfg in present_configs:
        for ar in sorted_ars:
            rows = grp_dict.get(cfg, {}).get(ar, [])
            st = compute_stats(rows)
            if st['completed'] > 0:
                tot = st['total_time'] / st['completed']
                if tot > max_rt:
                    max_rt = tot

for m_idx, mapping in enumerate(mappings_to_plot):
    ax = axes[m_idx]
    grp_dict = unified_plot_data[mapping]
    for i, cfg in enumerate(present_configs):
        y_sys, y_diff = [], []
        for ar in sorted_ars:
            rows = grp_dict.get(cfg, {}).get(ar, [])
            st = compute_stats(rows)
            comp = st['completed']
            s_t = (st['sys_time'] / comp) if comp > 0 else 0.0
            t_t = (st['total_time'] / comp) if comp > 0 else 0.0
            y_sys.append(s_t)
            y_diff.append(max(0.0, t_t - s_t))

        c = CONFIG_COLORS[cfg]
        ax.bar(x_base + offsets[i], y_sys, width=bar_w, color=c, edgecolor='black', linewidth=0.4)
        ax.bar(x_base + offsets[i], y_diff, width=bar_w, bottom=y_sys, color=c, alpha=0.35, edgecolor='black', linewidth=0.4)

    draw_cluster_separators(ax)
    ax.set_title(f"{mapping.capitalize()} Mapping", fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11)
    ax.set_xticks(x_base)
    ax.set_xticklabels([f"{ar}" for ar in sorted_ars], fontsize=10, fontweight='bold')
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    if m_idx == 0:
        ax.set_ylabel('Response Time (ms)', fontsize=12)

for ax in axes:
    ax.set_ylim(0, max_rt * 1.15 if max_rt > 0 else 1.5)

fig.subplots_adjust(top=0.90, bottom=0.20, left=0.06, right=0.98, wspace=0.08)

time_patches = [
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='System Execution (Bottom)'),
    mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Network / Wait Time (Top)')
]
fig.legend(handles=cfg_patches, loc='center', ncol=min(4, n_cfg), bbox_to_anchor=(0.35, 0.06),
           fontsize=8.5, title="Configurations", title_fontsize=9.5, frameon=True, facecolor='white', edgecolor='#cccccc')
fig.legend(handles=time_patches, loc='center', ncol=2, bbox_to_anchor=(0.78, 0.06),
           fontsize=8.5, title="Time Component", title_fontsize=9.5, frameon=True, facecolor='white', edgecolor='#cccccc')

fig.suptitle(f"Response Time Decomposition: Prima vs Dopo (Dijkstra-Time, $\\Delta D$ = {dl_str})", fontsize=14, fontweight='bold', y=0.97)
out_rt = os.path.join(OUTPUT_DIR, '03_Confronto_Response_Time_DijkTime.png')
plt.savefig(out_rt, bbox_inches='tight')
plt.close()
print(f"[OK] Generato: {out_rt}")
print(f"\nSalvataggio ultimato con successo in '{OUTPUT_DIR}/'.")