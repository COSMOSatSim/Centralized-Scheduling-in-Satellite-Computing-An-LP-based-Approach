import os
import re
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# Configurazione rendering tipografico ad alta risoluzione
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# ==============================================================================
# 1. PARAMETRI GENERALI, SWEEP E PALETTE
# ==============================================================================
root_folder = 'simulazioni_esp_8_2'  # Cartella contenente i file CSV dei risultati
OUTPUT_DIR = 'plots_ottimizzati'
os.makedirs(OUTPUT_DIR, exist_ok=True)

BS_VALS = [1, 2, 4, 6, 8, 10]
BT_VALS = [0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
ROUTING_TYPES = ['Energy', 'Time']
DEADLINES = [10, 20, 30]

# Palette continue per gli sweep di batching
COLORS_BS = plt.cm.viridis(np.linspace(0.12, 0.88, len(BS_VALS)))
COLORS_BT = plt.cm.plasma(np.linspace(0.08, 0.90, len(BT_VALS)))

# ==============================================================================
# PALETTE AD ALTA LUMINOSITÀ ED ELEVATO CONTRASTO
# ==============================================================================
CAUSE_KEYS = ['deadline', 'insuff_cn', 'insuff_c', 'no_server', 'ilp_infeasible', 'sunset']
CAUSE_LABELS = [
    'Deadline exceeded',
    'Insuff. CPU+NET',
    'Insuff. CPU',
    'No server found',
    'ILP Infeasible',
    'Sunset'
]

# Tonalità vivaci e luminose: nessuno sfondo scuro, leggibilità immediata
LUMINOUS_CAUSE_COLORS = {
    'deadline':       '#3B82F6',  # Blu cobalto vivido e chiaro
    'insuff_cn':      '#F59E0B',  # Ambra dorato brillante
    'insuff_c':       '#10B981',  # Verde smeraldo vivo
    'no_server':      '#EF4444',  # Rosso corallo chiaro
    'ilp_infeasible': '#8B5CF6',  # Lavanda / Violetto luminoso
    'sunset':         '#94A3B8'   # Grigio perla chiaro
}

# ==============================================================================
# 2. FUNZIONI DI LETTURA, PARSING E STATISTICHE
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def format_bt(bt_val):
    if bt_val is None:
        return ""
    for target in [2.0, 0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]:
        if abs(bt_val - target) < 1e-4:
            return '2' if target == 2.0 else str(target)
    return str(round(bt_val, 2))

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # 1. Arrival Rate (req/s)
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_float = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_float)) if at_float <= 1.0 else int(round(at_float))
    else:
        ar_val = None

    # 2. Deadline
    dl_match = re.search(r'deadline[_=](\d+)', f_lower)
    dl_val = int(dl_match.group(1)) if dl_match else None

    # 3. Batch Size e Batch Timeout
    bs_match = re.search(r'(?:batch_size|bs)[_=](\d+)', f_lower)
    bt_match = re.search(r'(?:batch_timeout|bt)[_=]([\d.]+)', f_lower)
    bs_val = int(bs_match.group(1)) if bs_match else None
    bt_val = float(bt_match.group(1)) if bt_match else None

    # 4. Objective Mapping (evita falsi positivi da "energy_budget")
    path_no_dijk = re.sub(r'dijk[a-z0-9_.\-]*|r_algo[a-z0-9_.\-]*', '', f_lower)
    if any(k in path_no_dijk for k in ['obj_energy', 'energy_mapping', 'opt_energy', '/energy/']):
        mapping_str = 'ENERGY'
    elif any(k in path_no_dijk for k in ['obj_time', 'time_mapping', 'opt_time', '/time/']):
        mapping_str = 'TIME'
    elif 'energy' in path_no_dijk and 'time' not in path_no_dijk:
        mapping_str = 'ENERGY'
    elif 'time' in path_no_dijk:
        mapping_str = 'TIME'
    else:
        mapping_str = 'Default'

    # 5. Routing Strategy (Dijkstra)
    dijk_weights = re.search(r'dijk_(?:w_r_)?([0-9.]+)_?(?:w_e_)?([0-9.]+)', f_lower)
    if dijk_weights:
        w_r, w_e = float(dijk_weights.group(1)), float(dijk_weights.group(2))
        dijk_str = 'Energy' if w_e > w_r else 'Time'
    elif any(k in f_lower for k in ['dijk_energy', 'dijkstra_energy', 'r_algo_energy']):
        dijk_str = 'Energy'
    else:
        dijk_str = 'Time'

    config_label = None
    if bs_val is not None and bt_val is not None:
        config_label = f"BS:{bs_val} | BT:{format_bt(bt_val)} | Dijk:{dijk_str}"

    return ar_val, dl_val, mapping_str, config_label, bs_val, bt_val, dijk_str

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
        'completed': completed,
        'rejected': rejected,
        'deadline': deadline,
        'insuff_cn': insuff_cn,
        'insuff_c': insuff_c,
        'no_server': no_server,
        'ilp_infeasible': ilp_infeasible,
        'sunset': sunset,
        'total_time': total_time,
        'sys_time': sys_time
    }

# ==============================================================================
# 3. CARICAMENTO DATI
# ==============================================================================
print(f"Scansione ricorsiva della cartella '{root_folder}'...")
data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith('.csv') and 'results' in file:
            filepath = os.path.join(root, file)
            ar, dl, mapping, config, bs, bt, dijk = extract_parameters(filepath)
            if ar is not None and dl is not None and config is not None:
                all_ars.add(ar)
                group_key = (mapping, dl)
                data_store.setdefault(group_key, {}).setdefault(config, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars)) if all_ars else [2, 3, 4, 6, 8, 10]
present_mappings = sorted(list({k[0] for k in data_store.keys() if k[0] in ['ENERGY', 'TIME']}))

print(f"-> Arrival Rates rilevati: {sorted_ars}")
print(f"-> Mappings identificati: {present_mappings}")

# ==============================================================================
# 4. GRAFICO 1: SUCCESS RATE LINE PLOT (3x2 GRID)
# ==============================================================================
def generate_line_success_rate(mapping):
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(16, 11), sharex=True, sharey=True)

    for row, dl in enumerate(DEADLINES):
        ax_bs = axes[row, 0]
        ax_bt = axes[row, 1]
        group_key = (mapping, dl)

        # 1. BS Sweep (BT = 2.0s)
        for idx, bs in enumerate(BS_VALS):
            for dijk in ROUTING_TYPES:
                cfg = f"BS:{bs} | BT:2 | Dijk:{dijk}"
                y_vals = []
                for ar in sorted_ars:
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    tot = st['completed'] + st['rejected']
                    y_vals.append((st['completed'] / tot * 100.0) if tot > 0 else 0.0)

                ls = '-' if dijk == 'Energy' else '--'
                marker = 'o' if dijk == 'Energy' else 's'
                ax_bs.plot(sorted_ars, y_vals, color=COLORS_BS[idx], linestyle=ls, marker=marker,
                           markersize=5, linewidth=1.8, alpha=0.88)

        # 2. BT Sweep (BS = 20)
        for idx, bt in enumerate(BT_VALS):
            bt_str = format_bt(bt)
            for dijk in ROUTING_TYPES:
                cfg = f"BS:20 | BT:{bt_str} | Dijk:{dijk}"
                y_vals = []
                for ar in sorted_ars:
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    tot = st['completed'] + st['rejected']
                    y_vals.append((st['completed'] / tot * 100.0) if tot > 0 else 0.0)

                ls = '-' if dijk == 'Energy' else '--'
                marker = 'o' if dijk == 'Energy' else 's'
                ax_bt.plot(sorted_ars, y_vals, color=COLORS_BT[idx], linestyle=ls, marker=marker,
                           markersize=5, linewidth=1.8, alpha=0.88)

        ax_bs.set_ylabel(f'Success Rate (%)\n[$\\Delta D = {dl}\\%$]', fontsize=11, fontweight='semibold')
        ax_bs.set_ylim(-2, 105)
        ax_bt.set_ylim(-2, 105)
        ax_bs.grid(True, linestyle=':', alpha=0.55)
        ax_bt.grid(True, linestyle=':', alpha=0.55)

    axes[0, 0].set_title('Batch Size Sweep ($BS$, $BT=2.0$s)', fontsize=12, fontweight='bold', pad=10)
    axes[0, 1].set_title('Batch Timeout Sweep ($BT$, $BS=20$)', fontsize=12, fontweight='bold', pad=10)
    axes[2, 0].set_xlabel('Arrival Rate (req/sec)', fontsize=11)
    axes[2, 1].set_xlabel('Arrival Rate (req/sec)', fontsize=11)
    axes[2, 0].set_xticks(sorted_ars)
    axes[2, 1].set_xticks(sorted_ars)

    fig.tight_layout()
    fig.subplots_adjust(top=0.92, bottom=0.12, hspace=0.12, wspace=0.08)

    # Legende strutturate in basso su tre box indipendenti
    bs_lines = [Line2D([0], [0], color=COLORS_BS[i], lw=2.2, label=f'BS={bs}') for i, bs in enumerate(BS_VALS)]
    bt_lines = [Line2D([0], [0], color=COLORS_BT[i], lw=2.2, label=f'BT={format_bt(bt)}s') for i, bt in enumerate(BT_VALS)]
    routing_lines = [
        Line2D([0], [0], color='#2b2b2b', linestyle='-', marker='o', lw=1.8, label='Dijkstra Energy'),
        Line2D([0], [0], color='#2b2b2b', linestyle='--', marker='s', lw=1.8, label='Dijkstra Time')
    ]

    leg1 = fig.legend(handles=bs_lines, loc='center', bbox_to_anchor=(0.22, 0.04), ncol=6, fontsize=8.5,
                      title='Batch Size ($BS$)', title_fontsize=9.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    leg2 = fig.legend(handles=routing_lines, loc='center', bbox_to_anchor=(0.50, 0.04), ncol=2, fontsize=8.5,
                      title='Routing Strategy', title_fontsize=9.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    leg3 = fig.legend(handles=bt_lines, loc='center', bbox_to_anchor=(0.78, 0.04), ncol=4, fontsize=8.5,
                      title='Batch Timeout ($BT$)', title_fontsize=9.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')

    fig.suptitle(f'Parametric Exploration of Success Rate (%) ({mapping} Mapping)', fontsize=15, fontweight='bold', y=0.98)

    out_path = os.path.join(OUTPUT_DIR, f'01_Line_Success_Rate_{mapping}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2, leg3))
    plt.close()
    print(f"[OK] Generato: {out_path}")

# ==============================================================================
# 5. GRAFICO 2: STACKED RESPONSE TIME (3x2 GRID)
# ==============================================================================
def generate_stacked_response_time(mapping):
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(19, 12), sharex=True)

    n_ars = len(sorted_ars)
    ar_indices = np.arange(n_ars)

    bs_bar_w = 0.050
    bs_gap = 0.018
    span_bs = len(BS_VALS) * (2 * bs_bar_w) + (len(BS_VALS) - 1) * bs_gap
    bs_start = -span_bs / 2.0 + bs_bar_w / 2.0

    bt_bar_w = 0.038
    bt_gap = 0.012
    span_bt = len(BT_VALS) * (2 * bt_bar_w) + (len(BT_VALS) - 1) * bt_gap
    bt_start = -span_bt / 2.0 + bt_bar_w / 2.0

    for row, dl in enumerate(DEADLINES):
        ax_bs = axes[row, 0]
        ax_bt = axes[row, 1]
        group_key = (mapping, dl)

        for i in range(n_ars - 1):
            ax_bs.axvline(i + 0.5, color='#e0e0e0', linestyle=':', linewidth=0.8)
            ax_bt.axvline(i + 0.5, color='#e0e0e0', linestyle=':', linewidth=0.8)

        # 1. BS Sweep (sinistra)
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bs in enumerate(BS_VALS):
                p_base = c_x + bs_start + g_idx * (2 * bs_bar_w + bs_gap)
                for d_idx, dijk in enumerate(ROUTING_TYPES):
                    x_pos = p_base + d_idx * bs_bar_w
                    cfg = f"BS:{bs} | BT:2 | Dijk:{dijk}"
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    comp = st['completed']

                    sys_t = (st['sys_time'] / comp) if comp > 0 else 0.0
                    tot_t = (st['total_time'] / comp) if comp > 0 else 0.0
                    wait_t = max(0.0, tot_t - sys_t)

                    h = None if dijk == 'Energy' else '///'
                    c = COLORS_BS[g_idx]

                    # Segmento inferiore: System Execution
                    ax_bs.bar(x_pos, sys_t, width=bs_bar_w, color=c, hatch=h, edgecolor='#222222', linewidth=0.25)
                    # Segmento superiore: Waiting / Network Time
                    ax_bs.bar(x_pos, wait_t, bottom=sys_t, width=bs_bar_w, color=c, alpha=0.45, hatch=h, edgecolor='#222222', linewidth=0.25)

        # 2. BT Sweep (destra)
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bt in enumerate(BT_VALS):
                bt_str = format_bt(bt)
                p_base = c_x + bt_start + g_idx * (2 * bt_bar_w + bt_gap)
                for d_idx, dijk in enumerate(ROUTING_TYPES):
                    x_pos = p_base + d_idx * bt_bar_w
                    cfg = f"BS:20 | BT:{bt_str} | Dijk:{dijk}"
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    comp = st['completed']

                    sys_t = (st['sys_time'] / comp) if comp > 0 else 0.0
                    tot_t = (st['total_time'] / comp) if comp > 0 else 0.0
                    wait_t = max(0.0, tot_t - sys_t)

                    h = None if dijk == 'Energy' else '///'
                    c = COLORS_BT[g_idx]

                    ax_bt.bar(x_pos, sys_t, width=bt_bar_w, color=c, hatch=h, edgecolor='#222222', linewidth=0.25)
                    ax_bt.bar(x_pos, wait_t, bottom=sys_t, width=bt_bar_w, color=c, alpha=0.45, hatch=h, edgecolor='#222222', linewidth=0.25)

        ax_bs.set_ylabel(f'Response Time (s)\n[$\\Delta D = {dl}\\%$]', fontsize=11, fontweight='semibold')
        ax_bs.grid(axis='y', linestyle=':', alpha=0.55)
        ax_bt.grid(axis='y', linestyle=':', alpha=0.55)

    for col in [0, 1]:
        axes[2, col].set_xticks(ar_indices)
        axes[2, col].set_xticklabels([f'{ar}' for ar in sorted_ars], fontsize=11, fontweight='semibold')
        axes[2, col].set_xlabel('Arrival Rate (req/sec)', fontsize=11)

    axes[0, 0].set_title('Batch Size Sweep ($BS$, $BT=2.0$s)', fontsize=12, fontweight='bold', pad=10)
    axes[0, 1].set_title('Batch Timeout Sweep ($BT$, $BS=20$)', fontsize=12, fontweight='bold', pad=10)

    fig.tight_layout()
    fig.subplots_adjust(top=0.92, bottom=0.12, hspace=0.12, wspace=0.08)

    # Legende a 4 blocchi sul fondo
    bs_patches = [mpatches.Patch(color=COLORS_BS[i], label=f'BS={bs}') for i, bs in enumerate(BS_VALS)]
    bt_patches = [mpatches.Patch(color=COLORS_BT[i], label=f'BT={format_bt(bt)}s') for i, bt in enumerate(BT_VALS)]
    time_comp_patches = [
        mpatches.Patch(facecolor='#666666', edgecolor='#222', alpha=1.0, label='Execution (Bottom)'),
        mpatches.Patch(facecolor='#666666', edgecolor='#222', alpha=0.45, label='Wait/Net (Top)')
    ]
    routing_patches = [
        mpatches.Patch(facecolor='#cccccc', edgecolor='#222', label='Dijkstra Energy (Solid)'),
        mpatches.Patch(facecolor='#cccccc', edgecolor='#222', hatch='///', label='Dijkstra Time (Hatched)')
    ]

    l1 = fig.legend(handles=bs_patches, loc='center', bbox_to_anchor=(0.14, 0.04), ncol=3, fontsize=8,
                    title='Batch Size ($BS$, $BT=2.0$s)', title_fontsize=9, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l2 = fig.legend(handles=time_comp_patches, loc='center', bbox_to_anchor=(0.38, 0.04), ncol=1, fontsize=8,
                    title='Time Component', title_fontsize=9, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l3 = fig.legend(handles=routing_patches, loc='center', bbox_to_anchor=(0.58, 0.04), ncol=1, fontsize=8,
                    title='Routing Strategy', title_fontsize=9, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l4 = fig.legend(handles=bt_patches, loc='center', bbox_to_anchor=(0.84, 0.04), ncol=4, fontsize=8,
                    title='Batch Timeout ($BT$, $BS=20$)', title_fontsize=9, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')

    fig.suptitle(f'Parametric Response Time Decomposition ({mapping} Mapping)', fontsize=15, fontweight='bold', y=0.98)

    out_path = os.path.join(OUTPUT_DIR, f'02_Stacked_Response_Time_{mapping}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(l1, l2, l3, l4))
    plt.close()
    print(f"[OK] Generato: {out_path}")




# ==============================================================================
# FUNZIONE REJECTION CAUSES (LAYOUT LUMINOSO E TRATTEGGIO ALLEGGERITO)
# ==============================================================================
def generate_rejection_causes_all_ar(mapping):
    n_ars = len(sorted_ars)
    ar_indices = np.arange(n_ars)

    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(20, 13), sharex=True, sharey=True)

    bs_bar_w = 0.050
    bs_pair_gap = 0.016
    span_bs = len(BS_VALS) * (2 * bs_bar_w) + (len(BS_VALS) - 1) * bs_pair_gap
    bs_start_offset = -span_bs / 2.0 + bs_bar_w / 2.0

    bt_bar_w = 0.038
    bt_pair_gap = 0.012
    span_bt = len(BT_VALS) * (2 * bt_bar_w) + (len(BT_VALS) - 1) * bt_pair_gap
    bt_start_offset = -span_bt / 2.0 + bt_bar_w / 2.0

    for row, dl in enumerate(DEADLINES):
        ax_bs = axes[row, 0]
        ax_bt = axes[row, 1]
        group_key = (mapping, dl)

        # Sfondo alternato per raggruppare i blocchi Arrival Rate
        for i in range(n_ars):
            if i % 2 == 1:
                ax_bs.axvspan(i - 0.5, i + 0.5, color='#f8fafc', zorder=0)
                ax_bt.axvspan(i - 0.5, i + 0.5, color='#f8fafc', zorder=0)

        for i in range(n_ars - 1):
            ax_bs.axvline(i + 0.5, color='#e2e8f0', linestyle='-', linewidth=0.75, zorder=1)
            ax_bt.axvline(i + 0.5, color='#e2e8f0', linestyle='-', linewidth=0.75, zorder=1)

        # -----------------------------
        # 1. Colonna BS-Sweep
        # -----------------------------
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bs in enumerate(BS_VALS):
                pair_base_x = c_x + bs_start_offset + g_idx * (2 * bs_bar_w + bs_pair_gap)
                for d_idx, dijk in enumerate(ROUTING_TYPES):
                    x_pos = pair_base_x + d_idx * bs_bar_w
                    cfg = f"BS:{bs} | BT:2 | Dijk:{dijk}"
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    rej_tot = st['rejected']

                    # Tratto singolo distanziato ('/') per non scurire la barra
                    hatch_pattern = None if dijk == 'Energy' else '/'
                    bottom = 0.0

                    for key in CAUSE_KEYS:
                        val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                        if val_pct > 0:
                            ax_bs.bar(
                                x_pos, val_pct, bottom=bottom, width=bs_bar_w,
                                color=LUMINOUS_CAUSE_COLORS[key],
                                hatch=hatch_pattern,
                                edgecolor='#2d3748',
                                linewidth=0.25,
                                zorder=3
                            )
                            bottom += val_pct

        # -----------------------------
        # 2. Colonna BT-Sweep
        # -----------------------------
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bt in enumerate(BT_VALS):
                bt_str = format_bt(bt)
                pair_base_x = c_x + bt_start_offset + g_idx * (2 * bt_bar_w + bt_pair_gap)
                for d_idx, dijk in enumerate(ROUTING_TYPES):
                    x_pos = pair_base_x + d_idx * bt_bar_w
                    cfg = f"BS:20 | BT:{bt_str} | Dijk:{dijk}"
                    rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                    st = compute_stats(rows)
                    rej_tot = st['rejected']

                    hatch_pattern = None if dijk == 'Energy' else '/'
                    bottom = 0.0

                    for key in CAUSE_KEYS:
                        val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                        if val_pct > 0:
                            ax_bt.bar(
                                x_pos, val_pct, bottom=bottom, width=bt_bar_w,
                                color=LUMINOUS_CAUSE_COLORS[key],
                                hatch=hatch_pattern,
                                edgecolor='#2d3748',
                                linewidth=0.25,
                                zorder=3
                            )
                            bottom += val_pct

        ax_bs.set_ylabel(f'Rejection Breakdown (%)\n[$\\Delta D = {dl}\\%$]', fontsize=11, fontweight='semibold')
        ax_bs.set_ylim(0, 100)
        ax_bs.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)
        ax_bt.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)

    # Assi inferiori
    for col_idx in [0, 1]:
        axes[2, col_idx].set_xticks(ar_indices)
        axes[2, col_idx].set_xticklabels([f'{ar} req/s' for ar in sorted_ars], fontsize=11, fontweight='semibold')
        axes[2, col_idx].set_xlabel('Arrival Rate ($\\lambda$)', fontsize=12, labelpad=8)

    axes[0, 0].set_title('BS-Sweep: Bars paired by $BS \\in [1, 2, 4, 6, 8, 10]$ ($BT=2.0$s)', fontsize=12, fontweight='bold', pad=12)
    axes[0, 1].set_title('BT-Sweep: Bars paired by $BT \\in [0.0 \\dots 1.0]$s ($BS=20$)', fontsize=12, fontweight='bold', pad=12)

    fig.tight_layout()
    fig.subplots_adjust(top=0.93, bottom=0.14, hspace=0.12, wspace=0.08)

    # Legende chiare sul fondo
    cause_patches = [
        mpatches.Patch(facecolor=LUMINOUS_CAUSE_COLORS[k], edgecolor='#4a5568', linewidth=0.5, label=label)
        for k, label in zip(CAUSE_KEYS, CAUSE_LABELS)
    ]
    pattern_patches = [
        mpatches.Patch(facecolor='#e2e8f0', edgecolor='#2d3748', linewidth=0.5, label='Dijkstra Energy (Solid)'),
        mpatches.Patch(facecolor='#e2e8f0', hatch='/', edgecolor='#2d3748', linewidth=0.5, label='Dijkstra Time (Hatched)')
    ]

    leg_causes = fig.legend(
        handles=cause_patches, loc='upper center', bbox_to_anchor=(0.40, 0.07),
        ncol=3, fontsize=9.5, title='Failure Causes Breakdown', title_fontsize=10.5,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )
    leg_pattern = fig.legend(
        handles=pattern_patches, loc='upper center', bbox_to_anchor=(0.78, 0.07),
        ncol=2, fontsize=9.5, title='Routing Strategy', title_fontsize=10.5,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )

    fig.suptitle(
        f'Failure Causes Evolution Across Arrival Rates ({mapping} Mapping)',
        fontsize=15, fontweight='bold', y=0.985
    )

    out_path = os.path.join(OUTPUT_DIR, f'03_Failure_Causes_{mapping}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg_causes, leg_pattern))
    plt.close()
    print(f'[OK] Salvato con successo: {out_path}')

# ==============================================================================
# 7. ESECUZIONE PIPELINE COMPLETA
# ==============================================================================
if __name__ == '__main__':
    print("\n--- AVVIO GENERAZIONE SUITE GRAFICI ---")
    for mapping in present_mappings:
        print(f"\n==========================================")
        print(f" ELABORAZIONE MAPPING: {mapping}")
        print(f"==========================================")
        generate_line_success_rate(mapping)
        generate_stacked_response_time(mapping)
        generate_rejection_causes_all_ar(mapping)

    print(f"\nCompletato con successo! Tutti i grafici si trovano in '{OUTPUT_DIR}/'.")