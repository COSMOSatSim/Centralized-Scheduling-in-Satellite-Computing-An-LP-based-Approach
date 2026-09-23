import os
import csv
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# High-resolution rendering settings
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

# ==============================================================================
# 1. PATHS, EXPERIMENTAL SETTINGS & STYLES (STRICTLY IN ENGLISH)
# ==============================================================================
path_pre  = 'simulazioni_esp_8_2'   # Baseline directory (Pre-Optimization)
path_post = 'simulazioni_esp_11_2'  # Calibrated directory (Post-Optimization)
OUTPUT_DIR = 'plots_confronto_ottimizzati'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_DL = 10  # Nominal evaluation deadline (Delta D = 10%)
MAPPINGS = ['Energy', 'Time']

CONFIG_ORDER = [
    'BS:2 | BT:2 [Pre-Opt]',
    'BS:2 | BT:2 [Post-Opt]',
    'BS:20 | BT:0.05 [Pre-Opt]',
    'BS:20 | BT:0.05 [Post-Opt]'
]

# Style definitions for Success Rate (Line Plot) and Failure Causes patterns
CONFIG_STYLES = {
    'BS:2 | BT:2 [Pre-Opt]': {
        'color': '#1E40AF',  # Deep Navy Blue
        'marker': 's',
        'ls': '--',
        'hatch': '//',
        'label': 'BS:2 | BT:2 [Pre-Opt]'
    },
    'BS:2 | BT:2 [Post-Opt]': {
        'color': '#0284C7',  # Vivid Sky Blue
        'marker': 'o',
        'ls': '-',
        'hatch': None,
        'label': 'BS:2 | BT:2 [Post-Opt]'
    },
    'BS:20 | BT:0.05 [Pre-Opt]': {
        'color': '#C2410C',  # Dark Rust
        'marker': '^',
        'ls': '--',
        'hatch': '\\\\',
        'label': 'BS:20 | BT:0.05 [Pre-Opt]'
    },
    'BS:20 | BT:0.05 [Post-Opt]': {
        'color': '#F59E0B',  # Warm Amber
        'marker': 'D',
        'ls': '-',
        'hatch': None,
        'label': 'BS:20 | BT:0.05 [Post-Opt]'
    }
}

# Luminous Palette for Failure Causes (High contrast, non-dark)
LUMINOUS_CAUSE_COLORS = {
    'deadline':       '#3B82F6',  # Bright Cobalt Blue
    'insuff_cn':      '#F59E0B',  # Golden Amber
    'insuff_c':       '#10B981',  # Emerald Green
    'no_server':      '#EF4444',  # Coral Red
    'ilp_infeasible': '#8B5CF6',  # Bright Lavender / Violet
    'sunset':         '#94A3B8'   # Slate / Pearl Grey
}
CAUSE_KEYS = ['deadline', 'insuff_cn', 'insuff_c', 'no_server', 'ilp_infeasible', 'sunset']
CAUSE_LABELS = [
    'Deadline exceeded',
    'Insuff. CPU+NET',
    'Insuff. CPU',
    'No server found',
    'ILP Infeasible',
    'Sunset'
]

# Solid opaque color pairs for Stacked Response Time (Zero washed-out effect)
RT_BAR_STYLES = {
    'BS:2 | BT:2 [Pre-Opt]': {
        'exec_color': '#1E40AF',  # Navy Blue solid
        'wait_color': '#93C5FD',  # Light Sky Blue opaque
        'hatch': '//',            # Hatched baseline
        'edge': '#0F172A',
        'label': 'BS:2 | BT:2 [Pre-Opt]'
    },
    'BS:2 | BT:2 [Post-Opt]': {
        'exec_color': '#0284C7',  # Cerulean Blue solid
        'wait_color': '#BAE6FD',  # Ice Blue opaque
        'hatch': None,            # Smooth solid calibrated
        'edge': '#0F172A',
        'label': 'BS:2 | BT:2 [Post-Opt]'
    },
    'BS:20 | BT:0.05 [Pre-Opt]': {
        'exec_color': '#9A3412',  # Rust Amber solid
        'wait_color': '#FDBA74',  # Peach opaque
        'hatch': '//',            # Hatched baseline
        'edge': '#0F172A',
        'label': 'BS:20 | BT:0.05 [Pre-Opt]'
    },
    'BS:20 | BT:0.05 [Post-Opt]': {
        'exec_color': '#D97706',  # Warm Amber solid
        'wait_color': '#FDE68A',  # Bright Sun opaque
        'hatch': None,            # Smooth solid calibrated
        'edge': '#0F172A',
        'label': 'BS:20 | BT:0.05 [Post-Opt]'
    }
}

# ==============================================================================
# 2. PARSING & STATISTICAL METRICS
# ==============================================================================
def read_csv_to_2d_array(file_path):
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_parameters(filepath, tag):
    f_lower = filepath.lower()

    # 1. Arrival Rate
    ar_match = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_lower)
    if ar_match:
        at_f = float(ar_match.group(1))
        ar_val = int(round(1.0 / at_f)) if at_f <= 1.0 else int(round(at_f))
    else:
        ar_val = None

    # 2. Deadline
    dl_match = re.search(r'deadline[_=](\d+)', f_lower)
    dl_val = int(dl_match.group(1)) if dl_match else None

    # 3. Routing (Restricted to Dijkstra-Time)
    dijk_weights = re.search(r'dijk_(?:w_r_)?([0-9.]+)_?(?:w_e_)?([0-9.]+)', f_lower)
    if dijk_weights:
        w_r, w_e = float(dijk_weights.group(1)), float(dijk_weights.group(2))
        is_dijk_time = (w_r > w_e)
    else:
        is_dijk_time = 'time' in f_lower and 'energy' not in f_lower.split('dijk')[-1]

    if not is_dijk_time:
        return None, None, None, None

    # 4. Objective Mapping
    path_clean = re.sub(r'energy_budget_\d+|batch_timeout_[\d.]+|bt_[\d.]+', '', f_lower)
    if any(k in path_clean for k in ['obj_energy', 'energy_mapping', 'opt_energy', '/energy/', '\\\\energy\\\\']):
        mapping_str = 'Energy'
    elif any(k in path_clean for k in ['obj_time', 'time_mapping', 'opt_time', '/time/', '\\\\time\\\\']):
        mapping_str = 'Time'
    elif 'energy' in path_clean and 'time' not in path_clean:
        mapping_str = 'Energy'
    elif 'time' in path_clean:
        mapping_str = 'Time'
    else:
        mapping_str = 'Energy'

    # 5. Batch Size and Timeout
    bs_match = re.search(r'(?:batch_size|bs)[_=](\d+)', f_lower)
    bt_match = re.search(r'(?:batch_timeout|bt)[_=]([\d.]+)', f_lower)
    bs_val = int(bs_match.group(1)) if bs_match else None
    bt_val = float(bt_match.group(1)) if bt_match else None

    cfg_label = None
    if bs_val == 2 and bt_val is not None and abs(bt_val - 2.0) < 0.1:
        cfg_label = f"BS:2 | BT:2 [{tag}]"
    elif bs_val == 20 and bt_val is not None and abs(bt_val - 0.05) < 0.02:
        cfg_label = f"BS:20 | BT:0.05 [{tag}]"

    return ar_val, dl_val, mapping_str, cfg_label

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
# 3. DATA LOADING
# ==============================================================================
print("Scanning experimental datasets...")
data_store = {}
all_ars = set()

for path_dir, tag in [(path_pre, 'Pre-Opt'), (path_post, 'Post-Opt')]:
    if not os.path.exists(path_dir):
        print(f"[WARNING] Path not found: {path_dir}")
        continue
    for root, _, files in os.walk(path_dir):
        for file in files:
            if file.endswith('.csv') and 'results' in file:
                filepath = os.path.join(root, file)
                ar, dl, mapping, cfg = extract_parameters(filepath, tag)
                if ar is not None and dl == TARGET_DL and cfg is not None:
                    all_ars.add(ar)
                    data_store.setdefault(mapping, {}).setdefault(cfg, {}).setdefault(ar, []).extend(read_csv_to_2d_array(filepath))

sorted_ars = sorted(list(all_ars)) if all_ars else [2, 3, 4, 6, 8, 10]
print(f"-> Validated Arrival Rates: {sorted_ars}")

# ==============================================================================
# 4. PLOT 1: SUCCESS RATE COMPARISON (CONTINUOUS LINE PLOT 1x2)
# ==============================================================================
def generate_confronto_success_rate():
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(18, 7.5), sharey=True)

    for col_idx, mapping in enumerate(MAPPINGS):
        ax = axes[col_idx]

        for cfg in CONFIG_ORDER:
            st_cfg = CONFIG_STYLES[cfg]
            y_vals = []
            for ar in sorted_ars:
                rows = data_store.get(mapping, {}).get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                tot = st['completed'] + st['rejected']
                y_vals.append((st['completed'] / tot * 100.0) if tot > 0 else 0.0)

            ax.plot(
                sorted_ars, y_vals,
                color=st_cfg['color'], linestyle=st_cfg['ls'],
                marker=st_cfg['marker'], markersize=7, linewidth=2.0,
                alpha=0.92, label=st_cfg['label']
            )

        ax.set_title(f'{mapping} Mapping', fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel('Arrival Rate (req/sec)', fontsize=12, labelpad=6)
        ax.set_xticks(sorted_ars)
        ax.set_ylim(-2, 105)
        ax.grid(True, linestyle='--', alpha=0.5)

    axes[0].set_ylabel('Success Rate (%)', fontsize=12, fontweight='semibold')

    fig.tight_layout()
    fig.subplots_adjust(top=0.88, bottom=0.17, wspace=0.08)

    handles = [
        Line2D([0], [0], color=CONFIG_STYLES[c]['color'], linestyle=CONFIG_STYLES[c]['ls'],
               marker=CONFIG_STYLES[c]['marker'], lw=2.0, markersize=8, label=CONFIG_STYLES[c]['label'])
        for c in CONFIG_ORDER
    ]
    leg = fig.legend(
        handles=handles, loc='upper center', bbox_to_anchor=(0.5, 0.07),
        ncol=4, fontsize=10.5, title='Evaluated Configurations (Dijkstra-Time)',
        title_fontsize=11.5, frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
    )

    fig.suptitle(
        f'Success Rate Comparison: Pre- vs. Post-Optimization (Dijkstra-Time, $\\Delta D = {TARGET_DL}\\%$)',
        fontsize=15, fontweight='bold', y=0.97
    )

    out_path = os.path.join(OUTPUT_DIR, '01_Confronto_Success_Rate_DijkTime.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg,))
    plt.close()
    print(f"[OK] Saved Success Rate: {out_path}")

# ==============================================================================
# 5. PLOT 2: FAILURE CAUSES BREAKDOWN (LUMINOUS STACKED BARS 1x2)
# ==============================================================================
def generate_confronto_rejection_causes():
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(20, 8), sharey=True)

    n_ars = len(sorted_ars)
    ar_indices = np.arange(n_ars)
    n_cfg = len(CONFIG_ORDER)

    bar_w = 0.18
    span = n_cfg * bar_w
    offsets = np.linspace(-span / 2.0 + bar_w / 2.0, span / 2.0 - bar_w / 2.0, n_cfg)

    for col_idx, mapping in enumerate(MAPPINGS):
        ax = axes[col_idx]

        # Subtle zebra striping for arrival rates
        for i in range(n_ars):
            if i % 2 == 1:
                ax.axvspan(i - 0.5, i + 0.5, color='#F8FAFC', zorder=0)

        for i in range(n_ars - 1):
            ax.axvline(i + 0.5, color='#E2E8F0', linestyle='-', linewidth=0.75, zorder=1)

        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for c_idx, cfg in enumerate(CONFIG_ORDER):
                x_pos = c_x + offsets[c_idx]
                rows = data_store.get(mapping, {}).get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                rej_tot = st['rejected']

                hatch_pat = CONFIG_STYLES[cfg]['hatch']
                bottom = 0.0

                for key in CAUSE_KEYS:
                    val_pct = (st[key] / rej_tot * 100.0) if rej_tot > 0 else 0.0
                    if val_pct > 0:
                        ax.bar(
                            x_pos, val_pct, bottom=bottom, width=bar_w * 0.90,
                            color=LUMINOUS_CAUSE_COLORS[key],
                            hatch=hatch_pat,
                            edgecolor='#2D3748',
                            linewidth=0.30,
                            zorder=3
                        )
                        bottom += val_pct

        ax.set_title(f'{mapping} Mapping', fontsize=13, fontweight='bold', pad=10)
        ax.set_xticks(ar_indices)
        ax.set_xticklabels([f'{ar}' for ar in sorted_ars], fontsize=11)
        ax.set_xlabel('Arrival Rate (req/sec)', fontsize=12, labelpad=6)
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)

    axes[0].set_ylabel('Rejection Breakdown (%)', fontsize=12, fontweight='semibold')

    fig.tight_layout()
    fig.subplots_adjust(top=0.88, bottom=0.18, wspace=0.08)

    cause_patches = [
        mpatches.Patch(facecolor=LUMINOUS_CAUSE_COLORS[k], edgecolor='#4A5568', linewidth=0.5, label=l)
        for k, l in zip(CAUSE_KEYS, CAUSE_LABELS)
    ]
    pattern_patches = [
        mpatches.Patch(facecolor='#E2E8F0', edgecolor='#2D3748', linewidth=0.5,
                       hatch=CONFIG_STYLES[c]['hatch'], label=CONFIG_STYLES[c]['label'])
        for c in CONFIG_ORDER
    ]

    leg1 = fig.legend(
        handles=cause_patches, loc='upper center', bbox_to_anchor=(0.38, 0.08),
        ncol=3, fontsize=9.5, title='Failure Causes Breakdown', title_fontsize=10.5,
        frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
    )
    leg2 = fig.legend(
        handles=pattern_patches, loc='upper center', bbox_to_anchor=(0.78, 0.08),
        ncol=2, fontsize=9.5, title='Evaluated Configurations (Pattern)', title_fontsize=10.5,
        frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
    )

    fig.suptitle(
        f'Failure Causes Evolution: Pre- vs. Post-Optimization (Dijkstra-Time, $\\Delta D = {TARGET_DL}\\%$)',
        fontsize=15, fontweight='bold', y=0.97
    )

    out_path = os.path.join(OUTPUT_DIR, '02_Confronto_Failure_Causes_DijkTime.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"[OK] Saved Failure Causes: {out_path}")

# ==============================================================================
# 6. PLOT 3: RESPONSE TIME DECOMPOSITION (SOLID/OPAQUE STACKED BARS 1x2)
# ==============================================================================
def generate_confronto_response_time():
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(20, 8), sharey=True)

    n_ars = len(sorted_ars)
    ar_indices = np.arange(n_ars)
    n_cfg = len(CONFIG_ORDER)

    bar_w = 0.18
    span = n_cfg * bar_w
    offsets = np.linspace(-span / 2.0 + bar_w / 2.0, span / 2.0 - bar_w / 2.0, n_cfg)
    max_y = 0.0

    for col_idx, mapping in enumerate(MAPPINGS):
        ax = axes[col_idx]

        for i in range(n_ars):
            if i % 2 == 1:
                ax.axvspan(i - 0.5, i + 0.5, color='#F8FAFC', zorder=0)

        for i in range(n_ars - 1):
            ax.axvline(i + 0.5, color='#E2E8F0', linestyle='-', linewidth=0.75, zorder=1)

        for a_idx, ar in enumerate(sorted_ars):
            c_x = ar_indices[a_idx]
            for c_idx, cfg in enumerate(CONFIG_ORDER):
                x_pos = c_x + offsets[c_idx]
                rows = data_store.get(mapping, {}).get(cfg, {}).get(ar, [])
                st = compute_stats(rows)
                comp = st['completed']

                sys_t = (st['sys_time'] / comp) if comp > 0 else 0.0
                tot_t = (st['total_time'] / comp) if comp > 0 else 0.0
                wait_t = max(0.0, tot_t - sys_t)
                if tot_t > max_y:
                    max_y = tot_t

                style = RT_BAR_STYLES[cfg]

                # Bottom Segment: System Execution Time (Solid & Saturated)
                ax.bar(
                    x_pos, sys_t, width=bar_w * 0.90,
                    color=style['exec_color'],
                    hatch=style['hatch'],
                    edgecolor=style['edge'],
                    linewidth=0.4,
                    zorder=3
                )
                # Top Segment: Network / Queuing Delay (Opaque Tint, Zero bleeding)
                ax.bar(
                    x_pos, wait_t, bottom=sys_t, width=bar_w * 0.90,
                    color=style['wait_color'],
                    hatch=style['hatch'],
                    edgecolor=style['edge'],
                    linewidth=0.4,
                    zorder=3
                )

        ax.set_title(f'{mapping} Mapping', fontsize=13, fontweight='bold', pad=10)
        ax.set_xticks(ar_indices)
        ax.set_xticklabels([f'{ar}' for ar in sorted_ars], fontsize=11)
        ax.set_xlabel('Arrival Rate (req/sec)', fontsize=12, labelpad=6)
        ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=2)

    axes[0].set_ylabel('Response Time (s)', fontsize=12, fontweight='semibold')
    axes[0].set_ylim(0, max_y * 1.15 if max_y > 0 else 1.0)
    axes[1].set_ylim(0, max_y * 1.15 if max_y > 0 else 1.0)

    fig.tight_layout()
    fig.subplots_adjust(top=0.88, bottom=0.18, wspace=0.08)

    cfg_patches = [
        mpatches.Patch(
            facecolor=RT_BAR_STYLES[c]['exec_color'],
            edgecolor=RT_BAR_STYLES[c]['edge'],
            hatch=RT_BAR_STYLES[c]['hatch'],
            linewidth=0.5,
            label=RT_BAR_STYLES[c]['label']
        )
        for c in CONFIG_ORDER
    ]
    comp_patches = [
        mpatches.Patch(facecolor='#475569', edgecolor='#0F172A', linewidth=0.5, label='System Execution (Bottom, Solid)'),
        mpatches.Patch(facecolor='#CBD5E1', edgecolor='#0F172A', linewidth=0.5, label='Network / Queuing Delay (Top, Tinted)')
    ]

    leg1 = fig.legend(
        handles=cfg_patches, loc='upper center', bbox_to_anchor=(0.38, 0.08),
        ncol=2, fontsize=9.5, title='Evaluated Configurations (Dijkstra-Time)', title_fontsize=10.5,
        frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
    )
    leg2 = fig.legend(
        handles=comp_patches, loc='upper center', bbox_to_anchor=(0.78, 0.08),
        ncol=2, fontsize=9.5, title='Latency Component Breakdown', title_fontsize=10.5,
        frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1'
    )

    fig.suptitle(
        f'Response Time Decomposition: Pre- vs. Post-Optimization (Dijkstra-Time, $\\Delta D = {TARGET_DL}\\%$)',
        fontsize=15, fontweight='bold', y=0.97
    )

    out_path = os.path.join(OUTPUT_DIR, '03_Confronto_Response_Time_DijkTime.png')
    plt.savefig(out_path, bbox_inches='tight', bbox_extra_artists=(leg1, leg2))
    plt.close()
    print(f"[OK] Saved Response Time: {out_path}")

# ==============================================================================
# 7. EXECUTION PIPELINE
# ==============================================================================
if __name__ == '__main__':
    print("\n--- RUNNING PRE VS POST OPTIMIZATION PLOT PIPELINE ---")
    generate_confronto_success_rate()
    generate_confronto_rejection_causes()
    generate_confronto_response_time()
    print(f"\nCompleted successfully! Generated plots saved in: '{OUTPUT_DIR}/'.")