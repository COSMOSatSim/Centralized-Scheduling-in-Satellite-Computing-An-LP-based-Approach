import os
import csv
import re
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
    'axes.titlesize': 13.0,
    'xtick.labelsize': 12.5,
    'ytick.labelsize': 12.0,
    'legend.fontsize': 11.0,
    'legend.title_fontsize': 12.5
})

# ==============================================================================
# 1. PARAMETRI, COLORI E GRIGLIA SCENARI
# ==============================================================================
root_folder = 'simulazioni_esp_9_2'  # Cartella contenente i CSV delle simulazioni di cross-sensitivity
OUTPUT_DIR = 'plots_cross_ottimizzati'
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUNSET_WEIGHTS = [2, 4, 6, 8, 10, 1000, 5000, 10000]
ALPHA_VALS = [10, 50, 1000]

# Palette luminosa per le Failure Causes
LUMINOUS_CAUSE_COLORS = {
    'deadline':       '#3B82F6',  # Blu cobalto vivo
    'insuff_cn':      '#F59E0B',  # Ambra dorato brillante
    'insuff_c':       '#10B981',  # Verde smeraldo
    'no_server':      '#EF4444',  # Rosso corallo chiaro
    'ilp_infeasible': '#8B5CF6',  # Lavanda / Viola chiaro
    'sunset':         '#94A3B8'   # Grigio perla
}
CAUSE_KEYS = ['deadline', 'insuff_cn', 'insuff_c', 'no_server', 'ilp_infeasible', 'sunset']
CAUSE_LABELS = [
    'Deadline exceeded', 'Insuff. CPU+NET', 'Insuff. CPU',
    'No server found', 'ILP Infeasible', 'Sunset'
]

# Stile e colori per Primary Weight (alpha)
ALPHA_STYLE = {
    10:   {'color': '#2563EB', 'marker': 'o', 'ls': '-',  'hatch': None, 'label': r'$\alpha = 10$'},
    50:   {'color': '#F59E0B', 'marker': 's', 'ls': '--', 'hatch': '/',  'label': r'$\alpha = 50$'},
    1000: {'color': '#10B981', 'marker': '^', 'ls': '-.', 'hatch': '\\\\', 'label': r'$\alpha = 1000$'}
}

# Configurazione dei 4 scenari disposti in griglia 2x2
SCENARIO_CONFIGS = [
    ('BS:2',  'BT:2.0',  'Dijk-Energy'),
    ('BS:2',  'BT:2.0',  'Dijk-Time'),
    ('BS:20', 'BT:0.05', 'Dijk-Energy'),
    ('BS:20', 'BT:0.05', 'Dijk-Time')
]

# ==============================================================================
# 2. PARSING CSV E METRICHE
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath):
    f_lower = filepath.lower()

    # 1. Arrival Rate
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_f = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_f)) if at_f <= 1.0 else int(round(at_f))
    else:
        ar_val = None

    # 2. Mapping Objective
    path_no_dijk = re.sub(r'dijk[a-z0-9_.\-]*', '', f_lower)
    if any(k in path_no_dijk for k in ['obj_energy', 'energy_mapping', 'opt_energy', '/energy/']):
        mapping_str = 'Energy'
    elif any(k in path_no_dijk for k in ['obj_time', 'time_mapping', 'opt_time', '/time/']):
        mapping_str = 'Time'
    elif 'energy' in path_no_dijk and 'time' not in path_no_dijk:
        mapping_str = 'Energy'
    elif 'time' in path_no_dijk:
        mapping_str = 'Time'
    else:
        mapping_str = 'Energy'

    # 3. Batching
    bs_match = re.search(r'(?:batch_size|bs)[_=](\d+)', f_lower)
    bt_match = re.search(r'(?:batch_timeout|bt)[_=]([\d.]+)', f_lower)
    bs_val = int(bs_match.group(1)) if bs_match else None
    bt_val = float(bt_match.group(1)) if bt_match else None

    # 4. Dijkstra Routing
    dijk_weights = re.search(r'dijk_(?:w_r_)?([0-9.]+)_?(?:w_e_)?([0-9.]+)', f_lower)
    if dijk_weights:
        w_r, w_e = float(dijk_weights.group(1)), float(dijk_weights.group(2))
        dijk_str = 'Dijk-Energy' if w_e > w_r else 'Dijk-Time'
    elif any(k in f_lower for k in ['dijk_energy', 'dijkstra_energy']):
        dijk_str = 'Dijk-Energy'
    else:
        dijk_str = 'Dijk-Time'

    # 5. Sunset Weight (gamma)
    sunw_match = re.search(r'(?:sunw|gamma|sunset_weight)[_=]([\d.]+)', f_lower)
    sunw_val = int(float(sunw_match.group(1))) if sunw_match else None

    # 6. Primary Weight (alpha)
    alpha_match = re.search(r'(?:alpha|pw|primary_weight|w_p)[_=]([\d.]+)', f_lower)
    alpha_val = int(float(alpha_match.group(1))) if alpha_match else None

    scenario_key = None
    if bs_val is not None and bt_val is not None:
        bt_str = "2.0" if abs(bt_val - 2.0) < 1e-4 else ("0.05" if abs(bt_val - 0.05) < 1e-4 else str(bt_val))
        scenario_key = f"{mapping_str} | BS:{bs_val} BT:{bt_str} | {dijk_str}"

    return ar_val, scenario_key, sunw_val, alpha_val

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
# 3. CARICAMENTO DATI
# ==============================================================================
print(f"Scansione ricorsiva della cartella '{root_folder}'...")
data_store = {}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith('.csv') and 'results' in file:
            filepath = os.path.join(root, file)
            ar, scenario, sunw, alpha = extract_parameters(filepath)
            if None not in (ar, scenario, sunw, alpha):
                all_ars.add(ar)
                data_store.setdefault(ar, {}).setdefault(scenario, {}).setdefault(sunw, {}).setdefault(alpha, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars)) if all_ars else [8, 10]
print(f"-> Arrival Rates rilevati: {sorted_ars}")

# ==============================================================================
# 4. GRAFICO 1: CROSS SUCCESS RATE (GRIGLIA 2x2)
# ==============================================================================
def generate_cross_success_rate(ar_target, mapping):
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15.0, 11.5), sharex=True, sharey=True)
    x_indices = np.arange(len(SUNSET_WEIGHTS))

    for idx, (bs_str, bt_str, dijk_str) in enumerate(SCENARIO_CONFIGS):
        r = idx // 2
        c = idx % 2
        ax = axes[r, c]
        scenario_key = f"{mapping} | {bs_str} {bt_str} | {dijk_str}"

        for alpha in ALPHA_VALS:
            y_vals = []
            for sunw in SUNSET_WEIGHTS:
                rows = data_store.get(ar_target, {}).get(scenario_key, {}).get(sunw, {}).get(alpha, [])
                st = compute_stats(rows)
                tot = st['completed'] + st['rejected']
                y_vals.append((st['completed'] / tot * 100.0) if tot > 0 else 0.0)

            cfg = ALPHA_STYLE[alpha]
            ax.plot(x_indices, y_vals, color=cfg['color'], linestyle=cfg['ls'],
                    marker=cfg['marker'], markersize=6.5, linewidth=2.2, alpha=0.92)

        ax.set_title(scenario_key, fontsize=13.0, fontweight='bold', pad=9)
        ax.set_ylim(-2, 105)
        ax.tick_params(axis='y', which='both', labelleft=True, labelsize=12.0)
        ax.grid(True, linestyle=':', alpha=0.6)
        if c == 0:
            ax.set_ylabel('Success Rate (%)', fontsize=14.0, fontweight='semibold')

    for c in range(2):
        axes[1, c].set_xticks(x_indices)
        axes[1, c].set_xticklabels([str(w) for w in SUNSET_WEIGHTS], fontsize=12.5, rotation=30)
        axes[1, c].set_xlabel('Sunset Weight ($\\gamma$)', fontsize=14.5, fontweight='semibold', labelpad=8)

    fig.tight_layout()
    fig.subplots_adjust(top=0.91, bottom=0.16, hspace=0.26, wspace=0.15)

    alpha_handles = [
        Line2D([0], [0], color=ALPHA_STYLE[a]['color'], linestyle=ALPHA_STYLE[a]['ls'],
               marker=ALPHA_STYLE[a]['marker'], lw=2.2, markersize=8, label=ALPHA_STYLE[a]['label'])
        for a in ALPHA_VALS
    ]
    leg = fig.legend(
        handles=alpha_handles, loc='center', bbox_to_anchor=(0.50, 0.065),
        ncol=3, fontsize=12.0, title='Primary Weight ($\\alpha$)', title_fontsize=13.0,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )

    fig.suptitle(f'Cross-Sensitivity Success Rate ($\\gamma \\times \\alpha$) — {mapping} Mapping at {ar_target} req/s',
                 fontsize=17.0, fontweight='bold', y=0.975)

    out_path = os.path.join(OUTPUT_DIR, f'01_Cross_Success_Rate_{mapping}_AR_{ar_target}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg,))
    plt.close()
    print(f"[OK] Generato Success Rate ({mapping}): {out_path}")

# ==============================================================================
# 5. GRAFICO 2: CROSS FAILURE CAUSES (GRIGLIA 2x2)
# ==============================================================================
def generate_cross_rejection_causes(ar_target, mapping):
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15.5, 12.0), sharex=True, sharey=True)

    n_sunw = len(SUNSET_WEIGHTS)
    x_indices = np.arange(n_sunw)
    bar_w = 0.22
    offsets = [-bar_w, 0.0, bar_w]

    for idx, (bs_str, bt_str, dijk_str) in enumerate(SCENARIO_CONFIGS):
        r = idx // 2
        c = idx % 2
        ax = axes[r, c]
        scenario_key = f"{mapping} | {bs_str} {bt_str} | {dijk_str}"

        for i in range(n_sunw):
            if i % 2 == 1:
                ax.axvspan(i - 0.5, i + 0.5, color='#f8fafc', zorder=0)

        for i in range(n_sunw - 1):
            ax.axvline(i + 0.5, color='#e2e8f0', linestyle='-', linewidth=0.75, zorder=1)

        for s_idx, sunw in enumerate(SUNSET_WEIGHTS):
            c_x = x_indices[s_idx]
            for a_idx, alpha in enumerate(ALPHA_VALS):
                x_pos = c_x + offsets[a_idx]
                rows = data_store.get(ar_target, {}).get(scenario_key, {}).get(sunw, {}).get(alpha, [])
                st = compute_stats(rows)
                rej_tot = st['rejected']

                hatch_pat = ALPHA_STYLE[alpha]['hatch']
                bottom = 0.0

                for key in CAUSE_KEYS:
                    val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                    if val_pct > 0:
                        ax.bar(x_pos, val_pct, bottom=bottom, width=bar_w * 0.88,
                               color=LUMINOUS_CAUSE_COLORS[key], hatch=hatch_pat,
                               edgecolor='#2d3748', linewidth=0.25, zorder=3)
                        bottom += val_pct

        ax.set_title(scenario_key, fontsize=13.0, fontweight='bold', pad=9)
        ax.set_ylim(0, 100)
        ax.tick_params(axis='y', which='both', labelleft=True, labelsize=12.0)
        ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)
        if c == 0:
            ax.set_ylabel('Rejection Breakdown (%)', fontsize=14.0, fontweight='semibold')

    for c in range(2):
        axes[1, c].set_xticks(x_indices)
        axes[1, c].set_xticklabels([str(w) for w in SUNSET_WEIGHTS], fontsize=12.5, rotation=30)
        axes[1, c].set_xlabel('Sunset Weight ($\\gamma$)', fontsize=14.5, fontweight='semibold', labelpad=8)

    fig.tight_layout()
    fig.subplots_adjust(top=0.91, bottom=0.17, hspace=0.26, wspace=0.15)

    cause_patches = [mpatches.Patch(facecolor=LUMINOUS_CAUSE_COLORS[k], edgecolor='#4a5568', linewidth=0.5, label=l)
                     for k, l in zip(CAUSE_KEYS, CAUSE_LABELS)]
    alpha_hatches = [mpatches.Patch(facecolor='#e2e8f0', edgecolor='#2d3748', linewidth=0.5,
                                    hatch=ALPHA_STYLE[a]['hatch'], label=ALPHA_STYLE[a]['label'])
                     for a in ALPHA_VALS]

    leg1 = fig.legend(
        handles=cause_patches, loc='center', bbox_to_anchor=(0.34, 0.065), ncol=3,
        fontsize=10.5, title='Failure Causes Breakdown', title_fontsize=12.0,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )
    leg2 = fig.legend(
        handles=alpha_hatches, loc='center', bbox_to_anchor=(0.76, 0.065), ncol=3,
        fontsize=10.5, title='Primary Weight Pattern ($\\alpha$)', title_fontsize=12.0,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )

    fig.suptitle(f'Cross-Sensitivity Rejection Causes ($\\gamma \\times \\alpha$) — {mapping} Mapping at {ar_target} req/s',
                 fontsize=17.0, fontweight='bold', y=0.975)

    out_path = os.path.join(OUTPUT_DIR, f'02_Cross_Failure_Causes_{mapping}_AR_{ar_target}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"[OK] Generato Rejection Causes ({mapping}): {out_path}")

# ==============================================================================
# 6. GRAFICO 3: CROSS RESPONSE TIME (GRIGLIA 2x2)
# ==============================================================================
def generate_cross_response_time(ar_target, mapping):
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15.5, 12.0), sharex=True)

    n_sunw = len(SUNSET_WEIGHTS)
    x_indices = np.arange(n_sunw)
    bar_w = 0.22
    offsets = [-bar_w, 0.0, bar_w]
    max_y = 0.0

    for idx, (bs_str, bt_str, dijk_str) in enumerate(SCENARIO_CONFIGS):
        r = idx // 2
        c = idx % 2
        ax = axes[r, c]
        scenario_key = f"{mapping} | {bs_str} {bt_str} | {dijk_str}"

        for i in range(n_sunw):
            if i % 2 == 1:
                ax.axvspan(i - 0.5, i + 0.5, color='#f8fafc', zorder=0)

        for i in range(n_sunw - 1):
            ax.axvline(i + 0.5, color='#e2e8f0', linestyle='-', linewidth=0.75, zorder=1)

        for s_idx, sunw in enumerate(SUNSET_WEIGHTS):
            c_x = x_indices[s_idx]
            for a_idx, alpha in enumerate(ALPHA_VALS):
                x_pos = c_x + offsets[a_idx]
                rows = data_store.get(ar_target, {}).get(scenario_key, {}).get(sunw, {}).get(alpha, [])
                st = compute_stats(rows)
                comp = st['completed']

                sys_t = (st['sys_time'] / comp) if comp > 0 else 0.0
                tot_t = (st['total_time'] / comp) if comp > 0 else 0.0
                wait_t = max(0.0, tot_t - sys_t)
                if tot_t > max_y:
                    max_y = tot_t

                base_c = ALPHA_STYLE[alpha]['color']
                ax.bar(x_pos, sys_t, width=bar_w * 0.88, color=base_c,
                       edgecolor='#1a202c', linewidth=0.35, zorder=3)
                ax.bar(x_pos, wait_t, bottom=sys_t, width=bar_w * 0.88, color=base_c,
                       alpha=0.38, hatch='//', edgecolor='#1a202c', linewidth=0.35, zorder=3)

        ax.set_title(scenario_key, fontsize=13.0, fontweight='bold', pad=9)
        ax.tick_params(axis='y', which='both', labelleft=True, labelsize=12.0)
        ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=2)
        if c == 0:
            ax.set_ylabel('Response Time (s)', fontsize=14.0, fontweight='semibold')

    for r in range(2):
        for c in range(2):
            axes[r, c].set_ylim(0, max_y * 1.12 if max_y > 0 else 1.0)

    for c in range(2):
        axes[1, c].set_xticks(x_indices)
        axes[1, c].set_xticklabels([str(w) for w in SUNSET_WEIGHTS], fontsize=12.5, rotation=30)
        axes[1, c].set_xlabel('Sunset Weight ($\\gamma$)', fontsize=14.5, fontweight='semibold', labelpad=8)

    fig.tight_layout()
    fig.subplots_adjust(top=0.91, bottom=0.17, hspace=0.26, wspace=0.15)

    alpha_patches = [mpatches.Patch(color=ALPHA_STYLE[a]['color'], label=ALPHA_STYLE[a]['label'])
                     for a in ALPHA_VALS]
    time_comp_patches = [
        mpatches.Patch(facecolor='#64748b', edgecolor='#1a202c', alpha=1.0, label='System Execution (Solid Bottom)'),
        mpatches.Patch(facecolor='#64748b', edgecolor='#1a202c', alpha=0.38, hatch='//', label='Network/Wait Time (Top)')
    ]

    leg1 = fig.legend(
        handles=alpha_patches, loc='center', bbox_to_anchor=(0.36, 0.065), ncol=3,
        fontsize=11.0, title='Primary Weight ($\\alpha$)', title_fontsize=12.5,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )
    leg2 = fig.legend(
        handles=time_comp_patches, loc='center', bbox_to_anchor=(0.74, 0.065), ncol=2,
        fontsize=11.0, title='Decomposition Component', title_fontsize=12.5,
        frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1'
    )

    fig.suptitle(f'Cross-Sensitivity Response Time Decomposition ($\\gamma \\times \\alpha$) — {mapping} Mapping at {ar_target} req/s',
                 fontsize=17.0, fontweight='bold', y=0.975)

    out_path = os.path.join(OUTPUT_DIR, f'03_Cross_Response_Time_{mapping}_AR_{ar_target}.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"[OK] Generato Response Time ({mapping}): {out_path}")

# ==============================================================================
# 7. ESECUZIONE SU TUTTI GLI ARRIVAL RATES E MAPPINGS
# ==============================================================================
if __name__ == '__main__':
    print("\n--- AVVIO GENERAZIONE SUITE CROSS-SENSITIVITY (6 FIGURE 2x2 PER AR) ---")
    MAPPINGS = ['Energy', 'Time']
    for ar in sorted_ars:
        print(f"\n==========================================")
        print(f" ELABORAZIONE ARRIVAL RATE: {ar} req/s")
        print(f"==========================================")
        for mapping in MAPPINGS:
            print(f" -> Mapping: {mapping}")
            generate_cross_success_rate(ar, mapping)
            generate_cross_rejection_causes(ar, mapping)
            generate_cross_response_time(ar, mapping)

    print(f"\nCompletato con successo! Tutti i grafici si trovano in '{OUTPUT_DIR}/'.")