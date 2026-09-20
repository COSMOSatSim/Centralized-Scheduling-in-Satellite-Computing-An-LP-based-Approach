import os
import csv
import re
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# ==========================================
# 1. PARAMETRI E COLORAZIONI
# ==========================================
root_folder = "simulazioni_esp_8"  # Cartella con le simulazioni complete

BS_VALUES = [1, 2, 4, 6, 8, 10]
BT_VALUES = [0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]

# Palette graduate per i parametri di sweep
BS_COLORS = {1: "#1a2a6c", 2: "#275efe", 4: "#00a896", 6: "#02c39a", 8: "#a8dadc", 10: "#ffd166"}
BT_COLORS = {0.0: "#2b0938", 0.05: "#5c1363", 0.1: "#8c2981", 0.2: "#b73779", 
             0.4: "#d85a63", 0.6: "#ed7e50", 0.8: "#fca636", 1.0: "#f0f921"}

DEADLINES = [10, 20, 30]
ROUTINGS = ["Energy", "Time"]
MAPPINGS = ["ENERGY", "TIME"]

# ==========================================
# 2. FUNZIONI DI PARSING & STATISTICHE
# ==========================================
def read_csv_to_2d_array(filepath):
    with open(filepath, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def extract_metadata(filepath):
    f_low = filepath.lower()
    
    ar_m = re.search(r'(?:arr_rate|at)[_=]([\d.]+)', f_low)
    if not ar_m: return None
    at = float(ar_m.group(1))
    ar = int(round(1.0 / at)) if at <= 1.0 else int(round(at))

    dl_m = re.search(r'deadline_(\d+)', f_low)
    dl = int(dl_m.group(1)) if dl_m else None

    bs_m = re.search(r'batch_size[_=](\d+)', f_low)
    bt_m = re.search(r'batch_timeout[_=]([\d.]+)', f_low)
    bs = int(bs_m.group(1)) if bs_m else None
    bt = float(bt_m.group(1)) if bt_m else None

    dijk_m = re.search(r'dijk[_=]([0-9.]+)[_=]([0-9.]+)', f_low)
    if dijk_m:
        routing = "Energy" if float(dijk_m.group(2)) > float(dijk_m.group(1)) else "Time"
    else:
        routing = "Time"

    mapping = None
    if "obj_energy" in f_low or "/energy/" in f_low:
        mapping = "ENERGY"
    elif "obj_time" in f_low or "/time/" in f_low:
        mapping = "TIME"

    return ar, dl, bs, bt, routing, mapping

def compute_times(lines):
    comp = 0
    tot_t, sys_t = 0.0, 0.0
    for l in lines:
        if len(l) <= 26: continue
        if str(l[2]).strip() == "Completed" and str(l[26]).strip() != "N/A":
            comp += 1
            tot_t += float(l[9]) + float(l[15]) + float(l[26])
            sys_t += float(l[9])
    
    if comp == 0:
        return 0.0, 0.0
    return sys_t / comp, max(0.0, (tot_t - sys_t) / comp)

# ==========================================
# 3. RACCOLTA DATI
# ==========================================
print("Estrazione metriche temporali dai log di simulazione...")
data = {m: {dl: {"BS": {}, "BT": {}} for dl in DEADLINES} for m in MAPPINGS}
all_ars = set()

for root, _, files in os.walk(root_folder):
    for f in files:
        if f.endswith(".csv") and "results" in f:
            fp = os.path.join(root, f)
            meta = extract_metadata(fp)
            if not meta: continue
            ar, dl, bs, bt, rout, mapping = meta
            if dl not in DEADLINES or mapping not in MAPPINGS: continue
            all_ars.add(ar)

            rows = read_csv_to_2d_array(fp)
            s_t, w_t = compute_times(rows)

            # Raggruppamento Sweep BS (BT fisso a 2.0s)
            if bt == 2.0 and bs in BS_VALUES:
                k = (bs, rout)
                if k not in data[mapping][dl]["BS"]: data[mapping][dl]["BS"][k] = {}
                data[mapping][dl]["BS"][k][ar] = (s_t, w_t)

            # Raggruppamento Sweep BT (BS fisso a 20)
            if bs == 20 and bt in BT_VALUES:
                k = (bt, rout)
                if k not in data[mapping][dl]["BT"]: data[mapping][dl]["BT"][k] = {}
                data[mapping][dl]["BT"][k][ar] = (s_t, w_t)

sorted_ars = sorted(list(all_ars))

# ==========================================
# 4. GENERAZIONE GRAFICI (PER OGNI MAPPING)
# ==========================================
os.makedirs("plots_stacked_sweeps", exist_ok=True)

for mapping in MAPPINGS:
    fig, axes = plt.subplots(3, 2, figsize=(20, 14), sharex=True)
    fig.suptitle(f"Parametric Response Time Decomposition ({mapping} Mapping)", fontsize=16, fontweight='bold', y=0.98)

    for r_idx, dl in enumerate(DEADLINES):
        # ----------------- Colonna Sinistra: BS Sweep -----------------
        ax_left = axes[r_idx, 0]
        configs_bs = [(b, rt) for b in BS_VALUES for rt in ROUTINGS]
        n_cfg_bs = len(configs_bs)
        step_bs = 0.85 / n_cfg_bs
        w_bs = step_bs * 0.90
        x_base_bs = np.arange(len(sorted_ars)) * (n_cfg_bs * step_bs + 0.5)
        offsets_bs = np.linspace(-(n_cfg_bs * step_bs)/2 + step_bs/2, (n_cfg_bs * step_bs)/2 - step_bs/2, n_cfg_bs)

        for i, (b_val, rt) in enumerate(configs_bs):
            s_vals, w_vals = [], []
            for ar in sorted_ars:
                st, wt = data[mapping][dl]["BS"].get((b_val, rt), {}).get(ar, (0.0, 0.0))
                s_vals.append(st)
                w_vals.append(wt)
            
            c = BS_COLORS[b_val]
            h = "//" if rt == "Time" else ""
            
            # System execution in basso (opaca), Wait/Network in alto (traslucida)
            ax_left.bar(x_base_bs + offsets_bs[i], s_vals, width=w_bs, color=c, edgecolor='black', linewidth=0.2, hatch=h)
            ax_left.bar(x_base_bs + offsets_bs[i], w_vals, width=w_bs, bottom=s_vals, color=c, alpha=0.35, 
                        edgecolor='black', linewidth=0.2, hatch=h)

        for x in x_base_bs[:-1]:
            ax_left.axvline(x + (n_cfg_bs * step_bs)/2 + 0.25, color='gray', linestyle=':', alpha=0.4)

        ax_left.set_ylabel(f"Response Time (ms)\n[$\\Delta D = {dl}\\%$]", fontsize=10)
        ax_left.grid(axis='y', linestyle='--', alpha=0.3)
        if r_idx == 0:
            ax_left.set_title("Batch Size Sweep ($BS$, $BT=2.0\\text{s}$)", fontsize=12, fontweight='bold')

        # ----------------- Colonna Destra: BT Sweep -----------------
        ax_right = axes[r_idx, 1]
        configs_bt = [(t, rt) for t in BT_VALUES for rt in ROUTINGS]
        n_cfg_bt = len(configs_bt)
        step_bt = 0.85 / n_cfg_bt
        w_bt = step_bt * 0.90
        x_base_bt = np.arange(len(sorted_ars)) * (n_cfg_bt * step_bt + 0.5)
        offsets_bt = np.linspace(-(n_cfg_bt * step_bt)/2 + step_bt/2, (n_cfg_bt * step_bt)/2 - step_bt/2, n_cfg_bt)

        for i, (t_val, rt) in enumerate(configs_bt):
            s_vals, w_vals = [], []
            for ar in sorted_ars:
                st, wt = data[mapping][dl]["BT"].get((t_val, rt), {}).get(ar, (0.0, 0.0))
                s_vals.append(st)
                w_vals.append(wt)
            
            c = BT_COLORS[t_val]
            h = "//" if rt == "Time" else ""
            
            ax_right.bar(x_base_bt + offsets_bt[i], s_vals, width=w_bt, color=c, edgecolor='black', linewidth=0.2, hatch=h)
            ax_right.bar(x_base_bt + offsets_bt[i], w_vals, width=w_bt, bottom=s_vals, color=c, alpha=0.35, 
                         edgecolor='black', linewidth=0.2, hatch=h)

        for x in x_base_bt[:-1]:
            ax_right.axvline(x + (n_cfg_bt * step_bt)/2 + 0.25, color='gray', linestyle=':', alpha=0.4)

        ax_right.grid(axis='y', linestyle='--', alpha=0.3)
        if r_idx == 0:
            ax_right.set_title("Batch Timeout Sweep ($BT$, $BS=20$)", fontsize=12, fontweight='bold')

    axes[2, 0].set_xticks(x_base_bs)
    axes[2, 0].set_xticklabels(sorted_ars, fontsize=10)
    axes[2, 0].set_xlabel("Arrival Rate (req/sec)", fontsize=11)

    axes[2, 1].set_xticks(x_base_bt)
    axes[2, 1].set_xticklabels(sorted_ars, fontsize=10)
    axes[2, 1].set_xlabel("Arrival Rate (req/sec)", fontsize=11)
# ==============================================================================
    # IMPOSTAZIONE SPAZI E LEGENDE SU SINGOLA RIGA (PARAMETRI ESPLICITI)
    # ==============================================================================
    # 1. Regolazione margini: riserva la fascia inferiore per la riga di legende
    plt.tight_layout()
    fig.subplots_adjust(bottom=0.09, top=0.94, hspace=0.15, wspace=0.12)

    # 2. Elementi grafici delle 4 legende
    leg_bs = [mpatches.Patch(color=BS_COLORS[b], label=f"BS={b}") for b in BS_VALUES]
    leg_bt = [mpatches.Patch(color=BT_COLORS[t], label=f"BT={t}s") for t in BT_VALUES]
    leg_comp = [
        mpatches.Patch(facecolor='gray', edgecolor='black', alpha=1.0, label='Execution (Bottom)'),
        mpatches.Patch(facecolor='gray', edgecolor='black', alpha=0.35, label='Wait/Net (Top)')
    ]
    leg_rout = [
        mpatches.Patch(facecolor='white', edgecolor='black', hatch='', label='Dijkstra-Energy'),
        mpatches.Patch(facecolor='white', edgecolor='black', hatch='//', label='Dijkstra-Time')
    ]

    # Quota verticale comune per allinearle tutte alla stessa altezza
    y_pos = 0.042

    # Box 1: Batch Size (allineato a sinistra)
    l_bs = fig.legend(
        handles=leg_bs,
        loc='center',
        bbox_to_anchor=(0.15, y_pos),
        ncol=6,
        title="Batch Size ($BS$, $BT=2.0\\text{s}$)",
        title_fontsize=9.5,
        fontsize=8.5,
        frameon=True,
        facecolor='white',
        edgecolor='#cccccc'
    )

    # Box 2: Time Component (centro-sinistra)
    l_comp = fig.legend(
        handles=leg_comp,
        loc='center',
        bbox_to_anchor=(0.38, y_pos),
        ncol=2,
        title="Time Component",
        title_fontsize=9.5,
        fontsize=8.5,
        frameon=True,
        facecolor='white',
        edgecolor='#cccccc'
    )

    # Box 3: Routing Strategy (centro-destra)
    l_rout = fig.legend(
        handles=leg_rout,
        loc='center',
        bbox_to_anchor=(0.53, y_pos),
        ncol=2,
        title="Routing Strategy",
        title_fontsize=9.5,
        fontsize=8.5,
        frameon=True,
        facecolor='white',
        edgecolor='#cccccc'
    )

    # Box 4: Batch Timeout (allineato a destra)
    l_bt = fig.legend(
        handles=leg_bt,
        loc='center',
        bbox_to_anchor=(0.83, y_pos),
        ncol=8,
        title="Batch Timeout ($BT$, $BS=20$)",
        title_fontsize=9.5,
        fontsize=8.5,
        frameon=True,
        facecolor='white',
        edgecolor='#cccccc'
    )

    # 3. Salvataggio con inclusione di tutte e quattro le legende
    save_path = f"plots_stacked_sweeps/02_Stacked_Response_Time_{mapping}.png"
    plt.savefig(save_path, bbox_inches='tight', bbox_extra_artists=(l_bs, l_comp, l_rout, l_bt))
    plt.close()
    print(f"Salvato con successo: {save_path}")