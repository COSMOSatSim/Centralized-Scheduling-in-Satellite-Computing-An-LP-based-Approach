import os
import csv
import re
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# Configurazione rendering tipografico ad alta risoluzione
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# ==============================================================================
# 1. PARAMETRI GENERALI, ALGORITMI E STILI (ENGLISH)
# ==============================================================================
CANDIDATE_FOLDERS = [
    'simulazioni_esp_10_2'
]

root_folder = None
for cand in CANDIDATE_FOLDERS:
    if os.path.exists(cand):
        has_csv = False
        for _, _, files in os.walk(cand):
            if any(f.endswith('.csv') and 'result' in f.lower() for f in files):
                has_csv = True
                break
        if has_csv:
            root_folder = cand
            break

if root_folder is None:
    root_folder = 'simulazioni_esp_10'

OUTPUT_DIR = 'plots_workload_2x2'
os.makedirs(OUTPUT_DIR, exist_ok=True)

ARRIVAL_RATES = [2, 3, 4, 6, 8, 10]
ENERGY_BUDGETS = [40, 80]

BETA_PROFILES = [
    ('(0, 1, 0)', 'CPU-Intensive - Beta (0, 1, 0)'),
    ('(0, 0, 1)', 'Data-Intensive - Beta (0, 0, 1)'),
    ('(0.4, 0.35, 0.25)', 'Mixed Workload - Beta (0.4, 0.35, 0.25)')
]

ALPHA_PROFILES = [
    ('(0.3, 0.5, 0.2)', 'Alpha (0.3, 0.5, 0.2) [Std]'),
    ('(0, 0.7, 0.3)',   'Alpha (0, 0.7, 0.3) [L-heavy]'),
    ('(0, 0.3, 0.7)',   'Alpha (0, 0.3, 0.7) [VL-heavy]'),
    ('(0, 1, 0)',       'Alpha (0, 1, 0) [Pure L]')
]

ALGO_ORDER = [
    'DTS-base',
    'DTS-Optimal',
    'Orbit-aware',
    'ILP-Hierarchical (Time)',
    'ILP-Hierarchical (Energy)',
    'ILP-Centr (BS20, BT0.05, Time)',
    'ILP-Centr (BS20, BT0.05, Energy)',
    'ILP-Centr (BS2, BT2, Time)',
    'ILP-Centr (BS2, BT2, Energy)'
]

ALGO_STYLE: Dict[str, Dict[str, Any]] = {
    'DTS-base':                         {'color': '#F59E0B', 'marker': 'o', 'linestyle': '-',  'ls': '-',  'light': '#FDE68A'},
    'DTS-Optimal':                      {'color': '#2563EB', 'marker': 's', 'linestyle': '-',  'ls': '-',  'light': '#BAE6FD'},
    'Orbit-aware':                      {'color': '#10B981', 'marker': '^', 'linestyle': '-',  'ls': '-',  'light': '#A7F3D0'},
    'ILP-Hierarchical (Time)':          {'color': '#8B5CF6', 'marker': 'v', 'linestyle': '--', 'ls': '--', 'light': '#DDD6FE'},
    'ILP-Hierarchical (Energy)':        {'color': '#D946EF', 'marker': '<', 'linestyle': '--', 'ls': '--', 'light': '#F5D0FE'},
    'ILP-Centr (BS20, BT0.05, Time)':   {'color': '#EF4444', 'marker': 'D', 'linestyle': '-.', 'ls': '-.', 'light': '#FECACA'},
    'ILP-Centr (BS20, BT0.05, Energy)': {'color': '#EA580C', 'marker': 'p', 'linestyle': '-.', 'ls': '-.', 'light': '#FED7AA'},
    'ILP-Centr (BS2, BT2, Time)':       {'color': '#06B6D4', 'marker': 'P', 'linestyle': ':',  'ls': ':',  'light': '#CFFAFE'},
    'ILP-Centr (BS2, BT2, Energy)':     {'color': '#64748B', 'marker': 'X', 'linestyle': ':',  'ls': ':',  'light': '#E2E8F0'}
}

ALGO_STYLE['OrbitAware'] = ALGO_STYLE['Orbit-aware']
ALGO_STYLE['DTS-APopt'] = ALGO_STYLE['DTS-Optimal']
ALGO_STYLE['DTS-opt'] = ALGO_STYLE['DTS-Optimal']
ALGO_STYLE['ILP-Hierarchical-Time'] = ALGO_STYLE['ILP-Hierarchical (Time)']
ALGO_STYLE['ILP-Hierarchical-Energy'] = ALGO_STYLE['ILP-Hierarchical (Energy)']

DEFAULT_ALGO_STYLE: Dict[str, Any] = {
    'color': '#64748B', 'marker': 'o', 'linestyle': '-', 'ls': '-', 'light': '#E2E8F0'
}

LUMINOUS_CAUSE_COLORS = {
    'deadline':       '#3B82F6',  # Blu cobalto vivo
    'insuff_cn':      '#F59E0B',  # Ambra dorato brillante
    'insuff_c':       '#10B981',  # Verde smeraldo
    'no_server':      '#EF4444',  # Rosso corallo chiaro
    'ilp_infeasible': '#8B5CF6',  # Lavanda / Violetto
    'sunset':         '#94A3B8'   # Grigio perla chiaro
}
CAUSE_KEYS = ['deadline', 'insuff_cn', 'insuff_c', 'no_server', 'ilp_infeasible', 'sunset']
CAUSE_LABELS = [
    'Deadline exceeded', 'Insuff. CPU+NET', 'Insuff. CPU',
    'No server found', 'ILP Infeasible', 'Sunset'
]

# ==============================================================================
# 2. PARSING CSV E METRICHE
# ==============================================================================
def read_csv_to_2d_array(file_path: str) -> List[List[str]]:
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def parse_workload_beta(path_str: str) -> Optional[str]:
    p = path_str.lower()
    if any(k in p for k in ['0.4_0.35_0.25', 'bg_0.4', 'b(0.4', 'beta_(0.4', 'beta_0.4']):
        return '(0.4, 0.35, 0.25)'
    if any(k in p for k in ['bcpui_1', 'bcpui_1.0', '0_1_0', '0.0_1.0_0.0', 'b(0, 1, 0)', 'beta_(0, 1, 0)']):
        return '(0, 1, 0)'
    if any(k in p for k in ['bcpudi_1', 'bcpudi_1.0', '0_0_1', '0.0_0.0_1.0', 'b(0, 0, 1)', 'beta_(0, 0, 1)']):
        return '(0, 0, 1)'
    return None

def parse_workload_alpha(path_str: str) -> Optional[str]:
    p = path_str.lower()
    if any(k in p for k in ['ah_1.0_avh_0', 'ah_1_avh_0', 'a(0, 1, 0)', 'alpha_(0, 1, 0)', 'pure l', 'pure_l']):
        return '(0, 1, 0)'
    if any(k in p for k in ['0.3_0.5_0.2', 'am_0.3', 'a(0.3', 'alpha_(0.3', 'std']):
        return '(0.3, 0.5, 0.2)'
    if any(k in p for k in ['0.7_0.3', 'ah_0.7', 'a(0, 0.7', 'alpha_(0, 0.7', 'l-heavy', 'l_heavy']):
        return '(0, 0.7, 0.3)'
    if any(k in p for k in ['0.3_0.7', 'ah_0.3_avh_0.7', 'a(0, 0.3', 'alpha_(0.3', 'vl-heavy', 'vl_heavy']):
        return '(0, 0.3, 0.7)'
    return None

def extract_parameters(filepath: str) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str], Optional[str]]:
    f_lower = filepath.lower()

    ar_match = re.search(r'(?:arrival_time|arr_rate|arrival_rate|at|ar)[_=]([\d.]+)', f_lower)
    if ar_match:
        val = float(ar_match.group(1))
        ar_val = int(round(1.0 / val)) if val <= 0.6 else int(round(val))
    else:
        ar_val = None

    eb_match = re.search(r'(?:energy_budget|budget|eb)[_=](\d+)', f_lower)
    if eb_match:
        val_eb = int(eb_match.group(1))
        eb_val = int(val_eb / 1000) if val_eb >= 1000 else val_eb
    else:
        eb_val = 40 if ('40k' in f_lower or '40000' in f_lower) else (80 if ('80k' in f_lower or '80000' in f_lower) else None)

    beta_val = parse_workload_beta(f_lower)
    alpha_val = parse_workload_alpha(f_lower)

    path_no_eb = re.sub(r'energy_budget_\d+|budget_\d+', '', f_lower)
    algo_val = None
    if 'orbit' in f_lower:
        algo_val = 'Orbit-aware'
    elif 'dts' in f_lower and any(k in f_lower for k in ['opt', 'apopt']):
        algo_val = 'DTS-Optimal'
    elif 'dts' in f_lower and 'base' in f_lower:
        algo_val = 'DTS-base'
    elif 'hierarchical' in f_lower:
        if any(k in path_no_eb for k in ['/time/', '_time', 'hierarchical_time', 'hierarchical-time']):
            algo_val = 'ILP-Hierarchical (Time)'
        else:
            algo_val = 'ILP-Hierarchical (Energy)'
    elif any(k in f_lower for k in ['centr', 'ilp_centralized', 'ilp-centralized', 'ilp_sim_systemap']):
        is_time = any(k in path_no_eb for k in ['obj_time', '/time/', 'opt_time'])
        is_bs20 = any(k in f_lower for k in ['bs_20', 'bs20', 'batch_size_20'])
        if is_bs20:
            algo_val = 'ILP-Centr (BS20, BT0.05, Time)' if is_time else 'ILP-Centr (BS20, BT0.05, Energy)'
        else:
            algo_val = 'ILP-Centr (BS2, BT2, Time)' if is_time else 'ILP-Centr (BS2, BT2, Energy)'

    return ar_val, eb_val, beta_val, alpha_val, algo_val

def compute_stats(lines: List[List[str]]) -> Dict[str, Any]:
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
print(f"Scansione cartella: '{root_folder}'...")
data_store: Dict[Any, Any] = {}

for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith('.csv') and 'result' in file.lower():
            filepath = os.path.join(root, file)
            ar, eb, beta, alpha, algo = extract_parameters(filepath)
            if None not in (ar, eb, beta, alpha, algo):
                data_store.setdefault(beta, {}).setdefault(eb, {}).setdefault(alpha, {}).setdefault(algo, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

# Calcolo offset per i 3 micro-cluster
bar_w = 0.080
sub_gap = 0.038
offsets_9 = []
curr_x = 0.0
for idx in range(9):
    offsets_9.append(curr_x)
    curr_x += bar_w
    if idx == 2 or idx == 4:
        curr_x += sub_gap
total_span = curr_x
offsets_9 = np.array(offsets_9) - (total_span / 2.0) + (bar_w / 2.0)

# ==============================================================================
# 4. GRAFICO 1: SUCCESS RATE (LEGENDA ADERENTE SENZA SPAZIO BIANCO)
# ==============================================================================
def generate_workload_success_rate(beta_key: str, beta_label: str):
    clean_name = re.sub(r'[^\w]+', '_', beta_key).strip('_')

    for eb in ENERGY_BUDGETS:
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(14, 8.5), sharex=True, sharey=True)
        ax_flat = axes.flatten()

        for c_idx, (a_key, a_lbl) in enumerate(ALPHA_PROFILES):
            ax = ax_flat[c_idx]

            for algo in ALGO_ORDER:
                y_vals = []
                for ar in ARRIVAL_RATES:
                    rows = data_store.get(beta_key, {}).get(eb, {}).get(a_key, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    tot = st['completed'] + st['rejected']
                    y_vals.append((st['completed'] / tot * 100.0) if tot > 0 else 0.0)

                cfg = ALGO_STYLE.get(algo, DEFAULT_ALGO_STYLE)
                ls_val: Any = cast(Any, cfg.get('linestyle', cfg.get('ls', '-')))

                ax.plot(
                    ARRIVAL_RATES, y_vals,
                    color=cfg.get('color', '#333333'),
                    linestyle=ls_val,
                    marker=cfg.get('marker', 'o'),
                    markersize=6.5,
                    linewidth=2.0,
                    alpha=0.92,
                    label=algo
                )

            ax.set_title(a_lbl, fontsize=11.5, fontweight='bold', pad=8)
            ax.set_ylim(-2, 105)
            ax.grid(True, linestyle='--', alpha=0.45)
            if c_idx % 2 == 0:
                ax.set_ylabel('Success Rate (%)', fontsize=11.5, fontweight='semibold')
            if c_idx >= 2:
                ax.set_xticks(ARRIVAL_RATES)
                ax.set_xticklabels([f'{ar}' for ar in ARRIVAL_RATES], fontsize=10.5)
                ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11.5, labelpad=5)

        fig.tight_layout()
        # Bottom a 0.14: posizionamento aderente all'asse orizzontale
        fig.subplots_adjust(top=0.91, bottom=0.14, hspace=0.20, wspace=0.08)

        handles = []
        for a in ALGO_ORDER:
            cfg = ALGO_STYLE.get(a, DEFAULT_ALGO_STYLE)
            ls_val_leg: Any = cast(Any, cfg.get('linestyle', cfg.get('ls', '-')))
            handles.append(
                Line2D([0], [0],
                       color=cfg.get('color', '#333333'),
                       linestyle=ls_val_leg,
                       marker=cfg.get('marker', 'o'),
                       lw=2.0,
                       markersize=7.0,
                       label=a)
            )

        leg = fig.legend(
            handles=handles, loc='upper center', bbox_to_anchor=(0.5, 0.065),
            ncol=5, fontsize=9.2, title='Evaluated Algorithms', title_fontsize=10.5,
            frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
        )

        fig.suptitle(f'Success Rate ({eb} kJ Budget) - {beta_label}', fontsize=14, fontweight='bold', y=0.975)

        out_path = os.path.join(OUTPUT_DIR, f'01_Success_Rate_Beta_{clean_name}_{eb}kJ.png')
        plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg,))
        plt.close()
        print(f"[OK] Generato Success Rate: {out_path}")

# ==============================================================================
# 5. GRAFICO 2: REJECTION CAUSES (LEGENDE AFFIANCATE SIDE-BY-SIDE)
# ==============================================================================
def generate_workload_rejection_causes(beta_key: str, beta_label: str):
    clean_name = re.sub(r'[^\w]+', '_', beta_key).strip('_')
    ar_indices = np.arange(len(ARRIVAL_RATES))

    for eb in ENERGY_BUDGETS:
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15, 8.8), sharex=True, sharey=True)
        ax_flat = axes.flatten()

        for c_idx, (a_key, a_lbl) in enumerate(ALPHA_PROFILES):
            ax = ax_flat[c_idx]

            for i in range(len(ARRIVAL_RATES)):
                if i % 2 == 1:
                    ax.axvspan(i - 0.5, i + 0.5, color='#F8FAFC', zorder=0)

            for i in range(len(ARRIVAL_RATES) - 1):
                ax.axvline(i + 0.5, color='#E2E8F0', linestyle='-', linewidth=0.75, zorder=1)

            for a_idx, ar in enumerate(ARRIVAL_RATES):
                c_x = ar_indices[a_idx]
                for alg_idx, algo in enumerate(ALGO_ORDER):
                    x_pos = c_x + offsets_9[alg_idx]
                    rows = data_store.get(beta_key, {}).get(eb, {}).get(a_key, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    rej_tot = st['rejected']
                    bottom = 0.0

                    for key in CAUSE_KEYS:
                        val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                        if val_pct > 0:
                            ax.bar(
                                x_pos, val_pct, bottom=bottom, width=bar_w * 0.90,
                                color=LUMINOUS_CAUSE_COLORS[key],
                                edgecolor='#1E293B',
                                linewidth=0.25,
                                zorder=3
                            )
                            bottom += val_pct

                    # Numero identificativo (1-9) stampato nitido sopra la barra
                    if rej_tot > 0:
                        ax.text(
                            x_pos, 102.2, f'{alg_idx + 1}',
                            ha='center', va='bottom',
                            fontsize=5.8, fontweight='bold',
                            color='#0F172A', zorder=4
                        )

            ax.set_title(a_lbl, fontsize=11.5, fontweight='bold', pad=8)
            ax.set_ylim(0, 114)
            ax.set_yticks([0, 20, 40, 60, 80, 100])
            ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)
            if c_idx % 2 == 0:
                ax.set_ylabel('Rejection Breakdown (%)', fontsize=11.5, fontweight='semibold')
            if c_idx >= 2:
                ax.set_xticks(ar_indices)
                ax.set_xticklabels([f'{ar}' for ar in ARRIVAL_RATES], fontsize=10.5)
                ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11.5, labelpad=5)

        fig.tight_layout()
        # Bottom a 0.15: spazio ideale per le due legende affiancate
        fig.subplots_adjust(top=0.91, bottom=0.15, hspace=0.20, wspace=0.08)

        cause_patches = [
            mpatches.Patch(facecolor=LUMINOUS_CAUSE_COLORS[k], edgecolor='#475569', linewidth=0.5, label=l)
            for k, l in zip(CAUSE_KEYS, CAUSE_LABELS)
        ]
        order_patches = [
            Line2D([0], [0], marker=f'${i+1}$', color='none', markeredgecolor='#0F172A',
                   markerfacecolor='#F1F5F9', markersize=8.5, label=f'[{i+1}] {algo}')
            for i, algo in enumerate(ALGO_ORDER)
        ]

        # LEGENDE AFFIANCATE: Sinistra (Cause) e Destra (Algoritmi) alla stessa quota Y
        leg1 = fig.legend(
            handles=cause_patches, loc='upper center', bbox_to_anchor=(0.28, 0.068),
            ncol=3, fontsize=9.0, title='Failure Causes Breakdown', title_fontsize=10.0,
            frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
        )
        leg2 = fig.legend(
            handles=order_patches, loc='upper center', bbox_to_anchor=(0.74, 0.068),
            ncol=3, fontsize=8.5, title='Algorithm Bar Clusters [Heuristics (1-3) | Hierarchical (4-5) | Centralized (6-9)]',
            title_fontsize=9.8, frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
        )

        fig.suptitle(f'Rejection Causes ({eb} kJ Budget) - {beta_label}', fontsize=14, fontweight='bold', y=0.975)

        out_path = os.path.join(OUTPUT_DIR, f'03_Rejection_Causes_Beta_{clean_name}_{eb}kJ.png')
        plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
        plt.close()
        print(f"[OK] Generato Rejection Causes: {out_path}")

# ==============================================================================
# 6. GRAFICO 3: RESPONSE TIME (LEGENDE ISOLATE E NUMERI SCAGLIONATI)
# ==============================================================================
def generate_workload_response_time(beta_key: str, beta_label: str):
    clean_name = re.sub(r'[^\w]+', '_', beta_key).strip('_')
    ar_indices = np.arange(len(ARRIVAL_RATES))

    for eb in ENERGY_BUDGETS:
        max_y = 0.0
        # Canvas allargato a 15.5 pollici per garantire aria alle legende laterali
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15.5, 9.2), sharex=True, sharey=True)
        ax_flat = axes.flatten()

        for c_idx, (a_key, a_lbl) in enumerate(ALPHA_PROFILES):
            ax = ax_flat[c_idx]

            for i in range(len(ARRIVAL_RATES)):
                if i % 2 == 1:
                    ax.axvspan(i - 0.5, i + 0.5, color='#F8FAFC', zorder=0)

            for i in range(len(ARRIVAL_RATES) - 1):
                ax.axvline(i + 0.5, color='#E2E8F0', linestyle='-', linewidth=0.75, zorder=1)

            for a_idx, ar in enumerate(ARRIVAL_RATES):
                c_x = ar_indices[a_idx]
                for alg_idx, algo in enumerate(ALGO_ORDER):
                    x_pos = c_x + offsets_9[alg_idx]
                    rows = data_store.get(beta_key, {}).get(eb, {}).get(a_key, {}).get(algo, {}).get(ar, [])
                    st = compute_stats(rows)
                    comp = st['completed']

                    sys_t = (st['sys_time'] / comp) if comp > 0 else 0.0
                    tot_t = (st['total_time'] / comp) if comp > 0 else 0.0
                    wait_t = max(0.0, tot_t - sys_t)
                    if tot_t > max_y:
                        max_y = tot_t

                    cfg = ALGO_STYLE.get(algo, DEFAULT_ALGO_STYLE)

                    # Barra inferiore solida (Execution)
                    ax.bar(
                        x_pos, sys_t, width=bar_w * 0.90,
                        color=cfg['color'], edgecolor='#0F172A', linewidth=0.35, zorder=3
                    )
                    # Barra superiore chiara opaca (Wait/Net)
                    ax.bar(
                        x_pos, wait_t, bottom=sys_t, width=bar_w * 0.90,
                        color=cfg['light'], edgecolor='#0F172A', linewidth=0.35, zorder=3
                    )

                    # Scaglionamento verticale per evitare che i numeri si fondano
                    if comp > 0 and tot_t > 0:
                        v_offset = 0.020 if (alg_idx % 2 == 0) else 0.045
                        ax.text(
                            x_pos, tot_t + v_offset, f'{alg_idx + 1}',
                            ha='center', va='bottom',
                            fontsize=5.0, fontweight='bold',
                            color='#0F172A', zorder=4
                        )

            ax.set_title(a_lbl, fontsize=11.5, fontweight='bold', pad=8)
            ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)
            if c_idx % 2 == 0:
                ax.set_ylabel('Response Time (s)', fontsize=11.5, fontweight='semibold')
            if c_idx >= 2:
                ax.set_xticks(ar_indices)
                ax.set_xticklabels([f'{ar}' for ar in ARRIVAL_RATES], fontsize=10.5)
                ax.set_xlabel('Arrival Rate (req/sec)', fontsize=11.5, labelpad=5)

        # Margine superiore esteso per accogliere lo scaglionamento dei numerini
        for ax in ax_flat:
            ax.set_ylim(0, max_y * 1.22 if max_y > 0 else 1.0)

        fig.tight_layout()
        # Spazio calibrato sul fondo per evitare sovrapposizioni con l'asse X
        fig.subplots_adjust(top=0.91, bottom=0.17, hspace=0.22, wspace=0.08)

        algo_patches = [
            mpatches.Patch(color=ALGO_STYLE.get(a, DEFAULT_ALGO_STYLE)['color'], label=f'[{i+1}] {a}')
            for i, a in enumerate(ALGO_ORDER)
        ]
        comp_patches = [
            mpatches.Patch(facecolor='#475569', edgecolor='#0F172A', linewidth=0.5, label='System Execution (Solid Bottom)'),
            mpatches.Patch(facecolor='#CBD5E1', edgecolor='#0F172A', linewidth=0.5, label='Network / Queuing Delay (Opaque Tint Top)')
        ]

        # Ancoraggi asimmetrici: Sinistra (upper left) e Destra (upper right) con gap centrale garantito
        leg1 = fig.legend(
            handles=algo_patches, loc='upper left', bbox_to_anchor=(0.04, 0.075),
            ncol=5, fontsize=8.2, title='Evaluated Algorithms (Numbered 1-9)', title_fontsize=9.2,
            frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
        )
        leg2 = fig.legend(
            handles=comp_patches, loc='upper right', bbox_to_anchor=(0.96, 0.075),
            ncol=1, fontsize=8.2, title='Latency Breakdown', title_fontsize=9.2,
            frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
        )

        fig.suptitle(f'Response Time Decomposition ({eb} kJ Budget) - {beta_label}', fontsize=14, fontweight='bold', y=0.975)

        out_path = os.path.join(OUTPUT_DIR, f'02_Response_Time_Beta_{clean_name}_{eb}kJ.png')
        plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
        plt.close()
        print(f"[OK] Generato Response Time: {out_path}")
# ==============================================================================
# 7. ESECUZIONE PIPELINE
# ==============================================================================
if __name__ == '__main__':
    print("--- AVVIO GENERAZIONE PLOT WORKLOAD BENCHMARK (LEGENDE CALIBRATE) ---")
    for beta_key, beta_label in BETA_PROFILES:
        if beta_key in data_store:
            print(f"\nElaborazione scenario: {beta_label}")
            generate_workload_success_rate(beta_key, beta_label)
            generate_workload_rejection_causes(beta_key, beta_label)
            generate_workload_response_time(beta_key, beta_label)
        else:
            print(f"[SKIP] Dati non trovati per {beta_label}")

    print(f"\nGenerazione completata con successo! File salvati in: '{OUTPUT_DIR}/'.")