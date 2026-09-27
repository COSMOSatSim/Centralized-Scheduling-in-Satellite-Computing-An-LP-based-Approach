import os
import re
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ==============================================================================
# CONFIGURAZIONE RENDERING TIPOGRAFICO AD ALTA RISOLUZIONE E FONT GLOBALI
# ==============================================================================
plt.rcParams.update({
    'figure.dpi': 300,
    'font.sans-serif': 'DejaVu Sans',
    'font.size': 13.5,
    'axes.labelsize': 14.5,
    'axes.titlesize': 16.5,
    'xtick.labelsize': 13.0,
    'ytick.labelsize': 13.0,
    'legend.fontsize': 11.5,
    'legend.title_fontsize': 13.5
})

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

    # 4. Objective Mapping
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
# 4. GRAFICO 1: SUCCESS RATE LINE PLOT (OTTIMIZZATO NELL'ASPECT RATIO)
# ==============================================================================
def generate_line_success_rate(mapping):
    # Larghezza ridotta da 18 a 13.5 per riquadri più compatti ("più corti")
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(13.5, 12.5), sharex=True, sharey=True)

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
                           markersize=5.5, linewidth=2.0, alpha=0.9)

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
                           markersize=5.5, linewidth=2.0, alpha=0.9)

        ax_bs.set_ylabel(f'Success Rate (%)\n[$\\Delta D = {dl}\\%$]', fontsize=13.5, fontweight='semibold')
        ax_bs.set_ylim(-2, 105)
        ax_bt.set_ylim(-2, 105)
        ax_bs.tick_params(labelsize=12)
        ax_bt.tick_params(labelsize=12)
        ax_bs.grid(True, linestyle=':', alpha=0.55)
        ax_bt.grid(True, linestyle=':', alpha=0.55)

    axes[0, 0].set_title('Batch Size Sweep ($BS$, $BT=2.0$s)', fontsize=15.0, fontweight='bold', pad=10)
    axes[0, 1].set_title('Batch Timeout Sweep ($BT$, $BS=20$)', fontsize=15.0, fontweight='bold', pad=10)
    axes[2, 0].set_xlabel('Arrival Rate (req/sec)', fontsize=14.0, fontweight='semibold', labelpad=8)
    axes[2, 1].set_xlabel('Arrival Rate (req/sec)', fontsize=14.0, fontweight='semibold', labelpad=8)
    axes[2, 0].set_xticks(sorted_ars)
    axes[2, 1].set_xticks(sorted_ars)

    fig.tight_layout()
    fig.subplots_adjust(top=0.91, bottom=0.18, hspace=0.18, wspace=0.10)

    # Legende adattate alla larghezza più compatta
    bs_lines = [Line2D([0], [0], color=COLORS_BS[i], lw=2.2, label=f'BS={bs}') for i, bs in enumerate(BS_VALS)]
    bt_lines = [Line2D([0], [0], color=COLORS_BT[i], lw=2.2, label=f'BT={format_bt(bt)}s') for i, bt in enumerate(BT_VALS)]
    routing_lines = [
        Line2D([0], [0], color='#2b2b2b', linestyle='-', marker='o', lw=2.0, label='Dijkstra Energy'),
        Line2D([0], [0], color='#2b2b2b', linestyle='--', marker='s', lw=2.0, label='Dijkstra Time')
    ]

    leg1 = fig.legend(handles=bs_lines, loc='center', bbox_to_anchor=(0.21, 0.07), ncol=3, fontsize=10.5,
                      title='Batch Size ($BS$)', title_fontsize=12.0, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    leg2 = fig.legend(handles=routing_lines, loc='center', bbox_to_anchor=(0.50, 0.07), ncol=1, fontsize=10.5,
                      title='Routing Strategy', title_fontsize=12.0, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    leg3 = fig.legend(handles=bt_lines, loc='center', bbox_to_anchor=(0.79, 0.07), ncol=4, fontsize=10.5,
                      title='Batch Timeout ($BT$)', title_fontsize=12.0, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')

    fig.suptitle(f'Parametric Exploration of Success Rate (%) ({mapping} Mapping)', fontsize=18.0, fontweight='bold', y=0.985)

    out_path = os.path.join(OUTPUT_DIR, f'01_Line_Success_Rate_{mapping}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2, leg3))
    plt.close()
    print(f"[OK] Generato: {out_path}")

# ==============================================================================
# 5. GRAFICO 2: STACKED RESPONSE TIME (3x2 GRID)
# ==============================================================================
def generate_stacked_response_time(mapping):
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(20, 13.5), sharex=True)

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

                    ax_bs.bar(x_pos, sys_t, width=bs_bar_w, color=c, hatch=h, edgecolor='#222222', linewidth=0.25)
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

        ax_bs.set_ylabel(f'Response Time (s)\n[$\\Delta D = {dl}\\%$]', fontsize=14.5, fontweight='semibold')
        ax_bs.tick_params(labelsize=13)
        ax_bt.tick_params(labelsize=13)
        ax_bs.grid(axis='y', linestyle=':', alpha=0.55)
        ax_bt.grid(axis='y', linestyle=':', alpha=0.55)

    for col in [0, 1]:
        axes[2, col].set_xticks(ar_indices)
        axes[2, col].set_xticklabels([f'{ar}' for ar in sorted_ars], fontsize=13.0, fontweight='semibold')
        axes[2, col].set_xlabel('Arrival Rate (req/sec)', fontsize=15.0, fontweight='semibold', labelpad=8)

    axes[0, 0].set_title('Batch Size Sweep ($BS$, $BT=2.0$s)', fontsize=16.5, fontweight='bold', pad=12)
    axes[0, 1].set_title('Batch Timeout Sweep ($BT$, $BS=20$)', fontsize=16.5, fontweight='bold', pad=12)

    fig.tight_layout()
    fig.subplots_adjust(top=0.91, bottom=0.17, hspace=0.16, wspace=0.08)

    # Legende raggruppate e centrate con spaziatura ridotta
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

    l1 = fig.legend(handles=bs_patches, loc='center', bbox_to_anchor=(0.20, 0.065), ncol=3, fontsize=11.0,
                    title='Batch Size ($BS$, $BT=2.0$s)', title_fontsize=12.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l2 = fig.legend(handles=time_comp_patches, loc='center', bbox_to_anchor=(0.39, 0.065), ncol=1, fontsize=11.0,
                    title='Time Component', title_fontsize=12.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l3 = fig.legend(handles=routing_patches, loc='center', bbox_to_anchor=(0.57, 0.065), ncol=1, fontsize=11.0,
                    title='Routing Strategy', title_fontsize=12.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')
    l4 = fig.legend(handles=bt_patches, loc='center', bbox_to_anchor=(0.79, 0.065), ncol=4, fontsize=11.0,
                    title='Batch Timeout ($BT$, $BS=20$)', title_fontsize=12.5, frameon=True, facecolor='#fafafa', edgecolor='#cccccc')

    fig.suptitle(f'Parametric Response Time Decomposition ({mapping} Mapping)', fontsize=19.5, fontweight='bold', y=0.985)

    out_path = os.path.join(OUTPUT_DIR, f'02_Stacked_Response_Time_{mapping}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(l1, l2, l3, l4))
    plt.close()
    print(f"[OK] Generato: {out_path}")

# ==============================================================================
# 6. FUNZIONE REJECTION CAUSES (STILE GRAFICO 2: INDICI SOPRA LE BARRE E TABELLA IN LEGENDA)
# ==============================================================================
def generate_rejection_causes_separated(mapping, routing_strategy):
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(16.0, 12.5), sharex=True, sharey=True)

    n_ars = len(sorted_ars)
    ar_indices = np.arange(n_ars)

    # Parametri geometrici calibrati per dare massima visibilità e stacco tra cluster
    bs_bar_w = 0.108
    bs_gap = 0.014
    span_bs = len(BS_VALS) * bs_bar_w + (len(BS_VALS) - 1) * bs_gap
    bs_start = -span_bs / 2.0 + bs_bar_w / 2.0

    bt_bar_w = 0.082
    bt_gap = 0.012
    span_bt = len(BT_VALS) * bt_bar_w + (len(BT_VALS) - 1) * bt_gap
    bt_start = -span_bt / 2.0 + bt_bar_w / 2.0

    for row, dl in enumerate(DEADLINES):
        ax_bs = axes[row, 0]
        ax_bt = axes[row, 1]
        group_key = (mapping, dl)

        # ----------------------------------------------------------------------
        # 1. Colonna Sinistra: BS-Sweep (6 barre per cluster)
        # ----------------------------------------------------------------------
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bs in enumerate(BS_VALS):
                x_pos = c_x + bs_start + g_idx * (bs_bar_w + bs_gap)
                cfg = f"BS:{bs} | BT:2 | Dijk:{routing_strategy}"
                rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                rej_tot = st['rejected']

                bottom = 0.0
                for key in CAUSE_KEYS:
                    val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                    if val_pct > 0:
                        ax_bs.bar(
                            x_pos, val_pct, bottom=bottom, width=bs_bar_w,
                            color=LUMINOUS_CAUSE_COLORS[key],
                            edgecolor='#1e293b', linewidth=0.35, zorder=3
                        )
                        bottom += val_pct

                # Indice numerico 1..6 sopra ciascuna barra (presente su tutte le righe)
                ax_bs.text(
                    x_pos, 102.2, str(g_idx + 1),
                    ha='center', va='bottom', fontsize=7.2, fontweight='bold',
                    color='#334155', zorder=4
                )

        # ----------------------------------------------------------------------
        # 2. Colonna Destra: BT-Sweep (8 barre per cluster)
        # ----------------------------------------------------------------------
        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for g_idx, bt in enumerate(BT_VALS):
                x_pos = c_x + bt_start + g_idx * (bt_bar_w + bt_gap)
                cfg = f"BS:20 | BT:{format_bt(bt)} | Dijk:{routing_strategy}"
                rows = data_store.get(group_key, {}).get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                rej_tot = st['rejected']

                bottom = 0.0
                for key in CAUSE_KEYS:
                    val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                    if val_pct > 0:
                        ax_bt.bar(
                            x_pos, val_pct, bottom=bottom, width=bt_bar_w,
                            color=LUMINOUS_CAUSE_COLORS[key],
                            edgecolor='#1e293b', linewidth=0.35, zorder=3
                        )
                        bottom += val_pct

                # Indice numerico 1..8 sopra ciascuna barra (presente su tutte le righe)
                ax_bt.text(
                    x_pos, 102.2, str(g_idx + 1),
                    ha='center', va='bottom', fontsize=6.8, fontweight='bold',
                    color='#334155', zorder=4
                )

        # Configurazione assi Y e griglia leggera
        ax_bs.set_ylabel(f'Rejection Breakdown (%)\n[$\\Delta D = {dl}\\%$]', fontsize=13.0, fontweight='semibold')
        ax_bs.set_ylim(0, 108)  # Lo spazio tra 100 e 108 ospita i numeri sopra le barre
        ax_bt.set_ylim(0, 108)
        ax_bs.set_yticks([0, 20, 40, 60, 80, 100])
        ax_bt.set_yticks([0, 20, 40, 60, 80, 100])
        ax_bs.tick_params(axis='y', labelsize=11.5)
        ax_bt.tick_params(axis='y', labelsize=11.5)
        ax_bs.grid(axis='y', linestyle=':', alpha=0.55, zorder=1)
        ax_bt.grid(axis='y', linestyle=':', alpha=0.55, zorder=1)

        # Limiti orizzontali centrati sui cluster
        ax_bs.set_xlim(-0.55, n_ars - 0.45)
        ax_bt.set_xlim(-0.55, n_ars - 0.45)

    # Titoli standard dei subplot superiori
    axes[0, 0].set_title(f'BS-Sweep ($BT=2.0$s) — Dijkstra {routing_strategy}', fontsize=14.5, fontweight='bold', pad=10)
    axes[0, 1].set_title(f'BT-Sweep ($BS=20$) — Dijkstra {routing_strategy}', fontsize=14.5, fontweight='bold', pad=10)

    # Asse X inferiore pulito (solo Arrival Rate centrato sotto i cluster)
    for col in [0, 1]:
        axes[2, col].set_xticks(ar_indices)
        axes[2, col].set_xticklabels([str(ar) for ar in sorted_ars], fontsize=12.5, fontweight='semibold')
        axes[2, col].set_xlabel('Arrival Rate (req/sec)', fontsize=13.5, fontweight='semibold', labelpad=8)
        axes[2, col].tick_params(axis='x', pad=5, length=4, color='#64748b')

    # Spaziatura del canvas con margine inferiore calibrato per le legende
    fig.subplots_adjust(top=0.915, bottom=0.175, hspace=0.16, wspace=0.08)

    # --------------------------------------------------------------------------
    # LEGENDA 1 (SINISTRA): CAUSE DI RIGETTO
    # --------------------------------------------------------------------------
    cause_patches = [
        mpatches.Patch(facecolor=LUMINOUS_CAUSE_COLORS[k], edgecolor='#334155', linewidth=0.5, label=label)
        for k, label in zip(CAUSE_KEYS, CAUSE_LABELS)
    ]
    leg_causes = fig.legend(
        handles=cause_patches, loc='center', bbox_to_anchor=(0.25, 0.065),
        ncol=2, fontsize=10.0, title='Failure Causes Breakdown', title_fontsize=11.5,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )

    # --------------------------------------------------------------------------
    # LEGENDA 2 (DESTRA): MAPPA DI DECODIFICA DEI PARAMETRI (COME GRAFICO 2)
    # --------------------------------------------------------------------------
    # Tabella 4 colonne x 4 righe (ordinata per colonne da Matplotlib)
    mapping_labels = [
        # Colonna 1: BS [1..3]
        '1  [1] BS = 1',
        '2  [2] BS = 2',
        '3  [3] BS = 4',
        '',
        # Colonna 2: BS [4..6]
        '4  [4] BS = 6',
        '5  [5] BS = 8',
        '6  [6] BS = 10',
        '',
        # Colonna 3: BT [1..4]
        '1  [1] BT = 0.0s',
        '2  [2] BT = 0.05s',
        '3  [3] BT = 0.1s',
        '4  [4] BT = 0.2s',
        # Colonna 4: BT [5..8]
        '5  [5] BT = 0.4s',
        '6  [6] BT = 0.6s',
        '7  [7] BT = 0.8s',
        '8  [8] BT = 1.0s'
    ]
    mapping_handles = [mpatches.Patch(color='none', label=lbl) for lbl in mapping_labels]

    leg_mapping = fig.legend(
        handles=mapping_handles, loc='center', bbox_to_anchor=(0.71, 0.065),
        ncol=4, fontsize=9.0,
        title='Sweep Configurations: [1-6] BS-Sweep (Left) | [1-8] BT-Sweep (Right)',
        title_fontsize=11.5, frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1',
        handlelength=0, handletextpad=0, columnspacing=1.6
    )

    fig.suptitle(
        f'Failure Causes Evolution — Dijkstra {routing_strategy} ({mapping} Mapping)',
        fontsize=17.0, fontweight='bold', y=0.982
    )

    out_path = os.path.join(OUTPUT_DIR, f'03_Failure_Causes_{mapping}_Dijkstra_{routing_strategy}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg_causes, leg_mapping))
    plt.close()
    print(f'[OK] Generato: {out_path}')


# ==============================================================================
# 7. ESECUZIONE AGGIORNATA
# ==============================================================================
if __name__ == '__main__':
    print("\n--- AVVIO GENERAZIONE SUITE GRAFICI AGGIORNATA ---")
    for mapping in present_mappings:
        print(f"\n==========================================")
        print(f" ELABORAZIONE MAPPING: {mapping}")
        print(f"==========================================")
        generate_line_success_rate(mapping)
        generate_stacked_response_time(mapping)

        # Generazione separata per Dijkstra Energy e Dijkstra Time
        for r_strat in ROUTING_TYPES:
            generate_rejection_causes_separated(mapping, r_strat)

    print(f"\nCompletato con successo! Tutti i grafici si trovano in '{OUTPUT_DIR}/'.")