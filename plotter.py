import os
import csv
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

plt.rcParams['figure.dpi'] = 300

# -----------------------------
# Funzioni di utilità
# -----------------------------
def read_csv_to_2d_array(file_path):
    """Legge un CSV in una lista 2D."""
    with open(file_path, newline='', encoding='utf-8') as f:
        return [row for row in csv.reader(f) if row]

def populate_recursively(d, path):
    """
    Naviga ricorsivamente tutte le sottocartelle.
    Quando trova CSV con 'AT_' nel nome, lo legge e lo salva nel dizionario.
    """
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            d.setdefault(item, {})
            populate_recursively(d[item], item_path)
        elif item.endswith(".csv") and "AT_" in item and "results" in item:
            at_value = item.split("AT_")[1].split("_")[0]
            d[f"AT_{at_value}"] = read_csv_to_2d_array(item_path)
            
# -----------------------------
# Funzione ausiliaria per accumulare valori in modo dinamico
# -----------------------------
def add_to_collected(container, keys, values):
    """
    Naviga nel dizionario container secondo keys (lista di chiavi)
    e aggiunge i valori alla lista finale.
    """
    current = container
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current.setdefault(keys[-1], [])
    current[keys[-1]] += values


def compute_stats(lines):
    completed = 0
    rejected = 0
    deadline = 0
    insuff_cn = 0
    insuff_c = 0
    no_server = 0
    total_time = 0.0
    sys_time = 0.0

    for line in lines:
        if line[2] == "Completed":
            completed += 1
            if line[26] != "N/A":
                total_time += float(line[9]) + float(line[15]) + float(line[26])
                sys_time += float(line[9])
        elif line[2] == "Rejected":
            rejected += 1

        if line[23] == "Deadline Exceeded":
            deadline += 1
        elif line[23] == "Insufficient Energy for CPU+NET":
            insuff_cn += 1
        elif line[23] == "Insufficient Energy for CPU":
            insuff_c += 1
        elif line[23] == "No suitable server found after deadline/sunset filters":
            no_server += 1

    return completed, rejected, deadline, insuff_cn, insuff_c, no_server, total_time, sys_time




# -----------------------------
# Configurazioni
# -----------------------------
root_folder = "results_esp_4"
algoritms = ["OrbitAware_sim_SystemAP5", "DTS-base_sim_SystemAP5", "DTS-APopt_sim_SystemAP5", "ILP_sim_SystemAP5"]
algs = ["OrbitAware", "DTS-base", "DTS-APopt", "ILP-hierarchical-time", "ILP-hierarchical-energy"]
budgets = ["Energy_budget_60000"]
bud = ["60 (KJ)"]
deadline = "deadline_10"
img = ["IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0_avh_1_gh_0_gvh_1", "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0_avh_1_gh_0.5_gvh_0.5",
       "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0_avh_1_gh_1_gvh_0", "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0.5_avh_0.5_gh_0_gvh_1",
       "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0.5_avh_0.5_gh_0.5_gvh_0.5", "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_0.5_avh_0.5_gh_1_gvh_0",
       "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_1_avh_0_gh_0_gvh_1", "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_1_avh_0_gh_0.5_gvh_0.5",
       "IMG_RES_bg_0.4_bcpui_0.35_bcpudi_0.25_am_0ah_1_avh_0_gh_1_gvh_0",
       "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0_avh_1_gh_0_gvh_1", "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0_avh_1_gh_0.5_gvh_0.5",
       "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0_avh_1_gh_1_gvh_0", "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0.5_avh_0.5_gh_0_gvh_1",
       "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0.5_avh_0.5_gh_0.5_gvh_0.5", "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_0.5_avh_0.5_gh_1_gvh_0",
       "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_1_avh_0_gh_0_gvh_1","IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_1_avh_0_gh_0.5_gvh_0.5",
       "IMG_RES_bg_0_bcpui_0_bcpudi_1_am_0ah_1_avh_0_gh_1_gvh_0"]

immagini = [
    "B(0.4,0.35,0.25) A(0,0,1) G(0,1)", "B(0.4,0.35,0.25) A(0,0,1) G(0,0.5,0.5)", "B(0.4,0.35,0.25) A(0,0,1) G(1,0)",
    "B(0.4,0.35,0.25) A(0,0.5,0.5) G(0,1)", "B(0.4,0.35,0.25) A(0,0.5,0.5) G(0,0.5,0.5)", "B(0.4,0.35,0.25) A(0,0.5,0.5) G(1,0)",
    "B(0.4,0.35,0.25) A(0,1,0) G(0,1)", "B(0.4,0.35,0.25) A(0,1,0) G(0,0.5,0.5)", "B(0.4,0.35,0.25) A(0,1,0) G(1,0)",
    
    "B(0,0,1) A(0,0,1) G(0,1)", "B(0,0,1) A(0,0,1) G(0,0.5,0.5)", "B(0,0,1) A(0,0,1) G(1,0)",
    "B(0,0,1) A(0,0.5,0.5) G(0,1)", "B(0,0,1) A(0,0.5,0.5) G(0,0.5,0.5)", "B(0,0,1) A(0,0.5,0.5) G(1,0)",
    "B(0,0,1) A(0,1,0) G(0,1)", "B(0,0,1) A(0,1,0) G(0,0.5,0.5)", "B(0,0,1) A(0,1,0) G(1,0)"]
routing = "Routing_bidirectional_True"
algo = "r_algo_GREEDY"
seeds = ["seed_101", "seed_2333", "seed_5843", "seed_7843", "seed_7879", "seed_9973"]
ats = ["AT_0.1"]
arrival_rates = "10"

types = ["hierarchical"]
params = ["time", "energy"]

colors = [
    '#4E79A7', '#A0CBE8', # Blues (Scuro, Chiaro)
    '#F28E2B', '#FFBE7D', # Oranges
    '#59A14F', '#8CD17D', # Greens
    '#B6992D', '#F1CE63', # Yellow/Golds
    '#499894', '#86BCB6', # Teals
    '#E15759', '#FF9D9A', # Reds/Pinks
    '#79706E', '#BAB0AC', # Greys
    '#D37295', '#FABFD2', # Magentas
    '#B07AA1', '#D4A5A5', # Purples/Roses
    '#9D7660', '#D7B5A6'  # Browns/Tans
]

# -----------------------------
# Popola il dizionario principale con tutti i CSV
# -----------------------------
data = {}
print("Iizio Estrazione Dati...")
populate_recursively(data, root_folder)

# -----------------------------
# Dizionario per raccogliere tutti i risultati
# -----------------------------
collected = {}

print("Inizio Organizzazione Dati...")

# Per algoritmi non-ILP
for alg in algoritms:
    if alg == "ILP_sim_SystemAP5":
        continue
    for im in img:
        for b in budgets:
            for s in seeds:
                for at in ats:
                    app = data[alg][deadline][b][im][routing][s][algo][at]
                    add_to_collected(collected, [alg, deadline, b, im, at], app)

for t in types:
    for p_idx, p in enumerate(params):
        for im in img:
            for b in budgets:
                for s in seeds:
                    for at in ats:
                        app = data["ILP_sim_SystemAP5"][t][p][deadline][b][im][routing][s][algo][at]
                        add_to_collected(collected, ["ILP", t, p, deadline, b, im, at], app)
                        


print("Organizzazione Risultati...")

results = {}

for alg in algoritms:
    if alg == "ILP_sim_SystemAP5":
        continue
    results[alg] = {}

    for b in budgets:
        results[alg][b] = []

        for im in img:
            stats = compute_stats(collected[alg][deadline][b][im]["AT_0.1"])
            results[alg][b].append((im, *stats))
            
            
ilp_configs = [
    ("hierarchical", "time"),
    ("hierarchical", "energy")
]

results_ilp = {}

for t, p in ilp_configs:
    key = f"{t}_{p}"
    results_ilp[key] = {}

    for b in budgets:
        results_ilp[key][b] = []

        for im in img:
            stats = compute_stats(collected["ILP"][t][p][deadline][b][im]["AT_0.1"])
            results_ilp[key][b].append((im, *stats))
            
            

print("Creazione di results_table.txt...")

# Apri il file in scrittura (verrà creato o sovrascritto)
with open("results_table.txt", "w") as f:

    # ciclo sugli algoritmi standard
    for alg in algoritms:
        if alg == "ILP_sim_SystemAP5":
            continue
        f.write(f"\nAlgorithm: {alg}\n")

        for b in budgets:
            f.write(f"  Budget: {b}\n")

            for img_name, completed, rejected, deadline_ex, insuff_cn, insuff_c, no_server, total_time, sys_time in results[alg][b]:

                if completed > 0:
                    suc_rate = (completed / (completed + rejected))*100
                    resp_time = total_time / completed
                    sys_t = sys_time / completed
                    dead_exced = (deadline_ex / rejected)*100
                    ins_cn = (insuff_cn / rejected)*100
                    ins_c = (insuff_c / rejected)*100
                    no_ser = (no_server / rejected)*100
                else:
                    resp_time = 0
                    sys_t = 0
                    suc_rate = 0
                    dead_exced = 0
                    ins_cn = 0
                    ins_c = 0
                    no_ser = 0

                f.write(
                    f"    {img_name} -> "
                    f"Success Rate: {suc_rate:.4f}, "
                    f"Deadline Exceeded: {dead_exced:.4f}, "
                    f"Insuff CPU+NET: {ins_cn:.4f}, "
                    f"Insuff CPU: {ins_c:.4f}, "
                    f"No Server: {no_ser:.4f}, "
                    f"RespTime: {resp_time:.4f}, "
                    f"SysTime: {sys_t:.4f}\n"
                )

    # ciclo per i risultati ILP
    for config in results_ilp:
        f.write(f"\nILP configuration: {config}\n")

        for b in results_ilp[config]:
            f.write(f"  Budget: {b}\n")

            for img_name, completed, rejected, deadline_ex, insuff_cn, insuff_c, no_server, total_time, sys_time in results_ilp[config][b]:

                if completed > 0:
                    suc_rate = (completed / (completed + rejected))*100
                    resp_time = total_time / completed
                    sys_t = sys_time / completed
                    dead_exced = (deadline_ex / rejected)*100
                    ins_cn = (insuff_cn / rejected)*100
                    ins_c = (insuff_c / rejected)*100
                    no_ser = (no_server / rejected)*100
                else:
                    resp_time = 0
                    sys_t = 0
                    suc_rate = 0
                    dead_exced = 0
                    ins_cn = 0
                    ins_c = 0
                    no_ser = 0

                f.write(
                    f"    {img_name} -> "
                    f"Success Rate: {suc_rate:.4f}, "
                    f"Deadline Exceeded: {dead_exced:.4f}, "
                    f"Insuff CPU+NET: {ins_cn:.4f}, "
                    f"Insuff CPU: {ins_c:.4f}, "
                    f"No Server: {no_ser:.4f}, "
                    f"RespTime: {resp_time:.4f}, "
                    f"SysTime: {sys_t:.4f}\n"
                )
            
            
print("Creazione Grafici...")
print(results_ilp)


# --- 1. CONFIGURAZIONE INIZIALE (Una sola volta) ---
budgets = ["Energy_budget_60000"]


algorithms = list(results.keys())
ilp_keys = list(results_ilp.keys())
num_img = len(immagini)
width = 0.05

# Posizioni dei gruppi (Algos + ILP)
x_base = np.arange(len(algorithms) + len(ilp_keys))

# --- 2. CICLO DI GENERAZIONE GRAFICI ---
for budget in budgets:
    plt.figure(figsize=(28, 12))
    
    # Estraiamo il numero dal nome del budget per il titolo (es. 40000)
    energy_val = budget.split('_')[-1]
    
    for j in range(num_img):
        # Calcolo Success Rate per gli algoritmi standard
        values_alg = [results[alg][budget][j][1] / (results[alg][budget][j][1] + results[alg][budget][j][2]) 
                      for alg in algorithms]
        
        # Calcolo Success Rate per gli algoritmi ILP
        values_ilp = [results_ilp[k][budget][j][1] / (results_ilp[k][budget][j][1] + results_ilp[k][budget][j][2]) 
                      for k in ilp_keys]
        
        # Uniamo le liste per il plotting
        total_values = values_alg + values_ilp
        
        # Disegno la barra per l'immagine j-esima in tutti i gruppi
        plt.bar(x_base + j*width, total_values, width=width, label=immagini[j], color=colors[j])

    # --- 3. ABBELLIMENTO E FORMATTAZIONE ---
    plt.title(f"Comparison per algorithm at {int(energy_val)//1000}KJ", fontsize=26)
    plt.ylabel("Success Rate (%)", fontsize=26)
    plt.ylim(0, 1)
    
    # Centriamo le etichette sull'asse X
    plt.xticks(x_base + width*(num_img-1)/2, algs, fontsize=22)
    plt.yticks(np.arange(0, 1.05, 0.1), fontsize=22)
    
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    plt.legend(bbox_to_anchor=(1, 1), loc='upper left', fontsize=22)
    plt.tight_layout()
    
    # Salvataggio dinamico
    plt.savefig(f"comparison_algos_{energy_val}.png")
    plt.close()  # chiude la figura per liberare memoria




'''
# --- 1. CONFIGURAZIONE INIZIALE ---
algorithms = list(results.keys())
ilp_keys = list(results_ilp.keys())


width = 0.15
x_base = np.arange(len(algorithms) + len(ilp_keys))

# --- 2. CICLO UNICO PER TUTTE LE IMMAGINI ---
for i in range(len(immagini)):
    plt.figure(figsize=(21, 8))
    
    # Ciclo sui budget (le barre all'interno di ogni gruppo di algoritmi)
    for j in range(len(budgets)):
        curr_budget = budgets[j]
        
        # Calcolo Success Rate per algoritmi standard (usando l'indice immagine i)
        values_alg = [
            results[alg][curr_budget][i][1] / (results[alg][curr_budget][i][1] + results[alg][curr_budget][i][2]) 
            for alg in algorithms
        ]
        
        # Calcolo Success Rate per algoritmi ILP
        values_ilp = [
            results_ilp[k][curr_budget][i][1] / (results_ilp[k][curr_budget][i][1] + results_ilp[k][curr_budget][i][2]) 
            for k in ilp_keys
        ]
        
        # Unione dati e plotting della barra del budget j-esimo
        total_values = values_alg + values_ilp
        plt.bar(x_base + j*width, total_values, width=width, label=bud[j], color=colors[j])

    # --- 3. FORMATTAZIONE GRAFICA ---
    plt.title(f"Comparison per Image - {immagini[i]}", fontsize=22)
    plt.ylabel("Success Rate (%)", fontsize=22)
    plt.ylim(0, 1)
    
    # Centriamo le etichette sull'asse X
    plt.xticks(x_base + width*(len(budgets)-1)/2, algs, fontsize=18)
    plt.yticks(np.arange(0, 1.05, 0.1), fontsize=18)
    
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    plt.legend(fontsize=18)
    plt.tight_layout()
    
    # --- 4. SALVATAGGIO DINAMICO ---
    # Trasforma il nome dell'immagine in un nome file pulito
    # (es. rimuove parentesi e spazi, trasforma virgole in underscore)
    clean_name = immagini[i].replace("(", "").replace(")", "").replace(" ", "_").replace(",", "_")
    filename = f"comparison_algos_img_{clean_name}.png"
    
    plt.savefig(filename)
    plt.close()  # chiude la figura per liberare memoria
'''





# --- 1. CONFIGURAZIONE GLOBALE ---
budgets_list = ["Energy_budget_60000"]
algorithms = list(results.keys())
ilp_keys = list(results_ilp.keys())
algs_labels = ["OrbitAware", "DTS-base", "DTS-APopt", "ILP-hierarchical-time", "ILP-hierarchical-energy"]



cause_map = [
    ("Deadline exceeded", 3),
    ("Insufficient CPU+NET", 4),
    ("Insufficient CPU", 5),
    ("No server found", 6)
]

cause_colors = {
    "Deadline exceeded": "#1f77b4",
    "Insufficient CPU+NET": "#ff7f0e",
    "Insufficient CPU": "#2ca02c",
    "No server found": "#d62728"
}

# Parametri layout
width = 0.4
bar_spacing = 0.45
group_spacing = 0.8
num_img = len(immagini)

# --- 2. CICLO DI GENERAZIONE ---
for budget_key in budgets_list:
    energy_val = budget_key.split('_')[-1]
    
    # Calcolo posizioni gruppi
    x_pos = []
    current_x = 0
    for _ in range(len(algorithms) + len(ilp_keys)):
        x_pos.append(current_x)
        current_x += num_img * bar_spacing + group_spacing
    x_pos = np.array(x_pos)

    plt.figure(figsize=(28, 12))
    plt.ylim(0, 1)

    # Ciclo sulle 10 immagini
    for j in range(num_img):
        bottom = np.zeros(len(algorithms) + len(ilp_keys))

        # Ciclo sulle cause di fallimento (Stacked Bar)
        for cause_name, cause_idx in cause_map:
            values = []

            # Raccolta dati Algoritmi Standard
            for alg in algorithms:
                rejected = results[alg][budget_key][j][2]
                val = results[alg][budget_key][j][cause_idx]
                values.append(0 if rejected == 0 else val / rejected)

            # Raccolta dati ILP
            for ilp_k in ilp_keys:
                rejected = results_ilp[ilp_k][budget_key][j][2]
                val = results_ilp[ilp_k][budget_key][j][cause_idx]
                values.append(0 if rejected == 0 else val / rejected)

            # Disegno del segmento della barra
            plt.bar(
                x_pos + j * bar_spacing,
                values,
                width=width,
                bottom=bottom,
                color=cause_colors[cause_name],
                label=cause_name if j == 0 else ""
            )
            bottom += np.array(values)

    # --- 3. FORMATTAZIONE ---
    plt.title(f"Failure causes per algorithm at {int(energy_val)//1000}KJ", fontsize=26)
    plt.ylabel("Rejection rate (%)", fontsize=26)
    
    # Etichette X centrate
    plt.xticks(x_pos + (num_img - 1) / 2 * bar_spacing, algs_labels, fontsize=22)
    plt.yticks(np.arange(0, 1.05, 0.1), fontsize=22)
    plt.grid(axis="y", linestyle="--", alpha=0.6)

    # Legende
    cause_legend_patches = [mpatches.Patch(color=c, label=l) for l, c in cause_colors.items()]
    legend1 = plt.legend(handles=cause_legend_patches, loc='upper left', bbox_to_anchor=(1, 0.2), fontsize=22)
    
    img_labels = [f"{i+1}: {immagini[i]}" for i in range(num_img)]
    img_patches = [Line2D([0], [0], color='none', label=l) for l in img_labels]
    legend2 = plt.legend(handles=img_patches, loc='upper left', bbox_to_anchor=(1, 1), fontsize=22)
    
    plt.gca().add_artist(legend1)
    plt.tight_layout()

    # Salvataggio
    plt.savefig(f"rejection_causes_{energy_val}.png")
    plt.close()
   



# --- 1. CONFIGURAZIONE ---
budget = "Energy_budget_60000"
algorithms = list(results.keys())
ilp_keys = list(results_ilp.keys())
algs_total = algorithms + ilp_keys
num_img = len(immagini)


width = 0.05  # Larghezza barre
x_base = np.arange(len(algs_total)) 

fig, ax = plt.subplots(figsize=(28, 14))


max_val = 0

# --- 2. CICLO SULLE IMMAGINI ---
for j in range(num_img):
    # Dati per algoritmi standard + ILP per l'immagine j
    successes = [results[alg][budget][j][1] for alg in algorithms] + \
                [results_ilp[k][budget][j][1] for k in ilp_keys]
    
    total_r_time = [results[alg][budget][j][7] for alg in algorithms] + \
                   [results_ilp[k][budget][j][7] for k in ilp_keys]
    
    system_r_time = [results[alg][budget][j][8] for alg in algorithms] + \
                    [results_ilp[k][budget][j][8] for k in ilp_keys]

    # Calcolo medie (evitando divisioni per zero)
    y_total = [t/s if s > 0 else 0 for t, s in zip(total_r_time, successes)]
    y_system = [sys/s if s > 0 else 0 for sys, s in zip(system_r_time, successes)]
    y_diff = [max(0, t - s) for t, s in zip(y_total, y_system)]

    max_val = max(max_val, max(y_total))

    # --- DISEGNO LE BARRE SOVRAPPOSTE ---
    # Parte Bassa: System Time (Colore pieno)
    ax.bar(x_base + j*width, y_system, width=width, 
            color=colors[j], edgecolor='black', linewidth=0.3,label=f"{immagini[j]}")
    
    # Parte Alta: Wait/Extra Time (Colore sbiadito)
    ax.bar(x_base + j*width, y_diff, width=width, bottom=y_system, 
            color=colors[j], alpha=0.3, edgecolor='black', linewidth=0.3)

# --- 3. FORMATTAZIONE ASSI ---
energy_val = budget.split('_')[-1]
ax.set_title(f"Stacked Response Time per Algorithm at {int(energy_val)//1000}KJ", fontsize=26)
ax.set_ylabel("Response Time (ms)", fontsize=26)
ax.set_xticks(x_base + width*(num_img-1)/2)
ax.set_xticklabels(algs, fontsize=22)
ax.set_yticks(np.arange(0, max_val * 1.2, 0.2))
ax.tick_params(axis='both', labelsize=22)
ax.grid(axis="y", linestyle="--", alpha=0.5)
ax.set_ylim(0, max_val * 1.05)

# --- 4. GESTIONE LEGENDE ESTERNE ---

# Legenda 1: Immagini (in alto a destra)
# Aggiunto loc='upper left' e spostata leggermente più a destra (1.02)
img_legend = ax.legend(fontsize=22, loc='upper left', bbox_to_anchor=(1, 1))

# Legenda 2: Componenti (sotto la prima)
type_patches = [
    mpatches.Patch(color='gray', alpha=1.0, label='System Execution'),
    mpatches.Patch(color='gray', alpha=0.3, label='Network/Wait Time')
]
# Aggiunto loc='upper left' e allineata con la prima legenda
type_legend = ax.legend(handles=type_patches, 
                        fontsize=22, loc='upper left', bbox_to_anchor=(1, 0.2))

# Riaggiungiamo la prima legenda
ax.add_artist(img_legend)

# Salvataggio: INCLUDI bbox_extra_artists per non far tagliare la Legenda 1!
plt.savefig(f"response_time_{energy_val}.png", 
            bbox_inches='tight', 
            bbox_extra_artists=(img_legend,))
plt.close()



'''
for img_idx in range(len(immagini)):

    algorithms = list(results.keys())
    ilp = list(results_ilp.keys())

    num_img = len(budgets)
    width = 0.25

    x = np.arange(len(algorithms) + len(ilp))

    fig, ax = plt.subplots(figsize=(24,10))

    #colors = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2']
    #color_2 = ["#852085", "#50AF42", "#250B97", "#D9FF00"]

    max_value = 0  # per calcolare il massimo valore delle barre

    for j in range(len(budgets)):

        values = [
            results[alg][budgets[j]][img_idx][7] / results[alg][budgets[j]][img_idx][1]
            for alg in algorithms
        ]

        v = [
            results_ilp[ilp_key][budgets[j]][img_idx][7] / results_ilp[ilp_key][budgets[j]][img_idx][1]
            for ilp_key in ilp
        ]

        values += v

        sec_value = [
            results[alg][budgets[j]][img_idx][8] / results[alg][budgets[j]][img_idx][1]
            for alg in algorithms
        ]

        v_2 = [
            results_ilp[ilp_key][budgets[j]][img_idx][8] / results_ilp[ilp_key][budgets[j]][img_idx][1]
            for ilp_key in ilp
        ]

        sec_value += v_2

        # aggiorna il massimo
        max_value = max(max_value, max(values + sec_value))

        ax.bar(x + j*width, values, width=width, color=colors[j])
        ax.bar(x + j*width, sec_value, width=width, color=colors[j+1])

    # ---------- LEGENDA 1 ----------
    color_labels = ["Total response time"] * len(budgets) + ["Time in system"] * len(budgets)

    color_patches = [mpatches.Patch(color=c, label=l) for c, l in zip(colors, color_labels)]

    legend_colors = ax.legend(handles=color_patches, loc="best", fontsize=22)

    # ---------- LEGENDA 2 ----------
    budget_labels = [f"{i+1} = {budgets[i]}" for i in range(len(budgets))]

    budget_handles = [Line2D([0],[0], linestyle="none", label=l) for l in budget_labels]

    legend_budget = ax.legend(
        handles=budget_handles,
        loc="upper center",
        fontsize=22,
        handlelength=0
    )

    ax.add_artist(legend_colors)

    # ---------- ASSI ----------
    ax.set_xticks(x + width*(len(budgets)-1)/2)
    ax.set_xticklabels(algs, fontsize=22)

    # altezza massima del grafico (30% più alto del massimo valore)
    ymax = max_value * 1.3

    # tick ogni 0.1 ms
    ticks = np.arange(0, ymax + 0.1, 0.15)  # aggiungo 0.1 per includere ymax
    ticks = np.round(ticks, 2)  # arrotonda per evitare float strani

    ax.set_yticks(ticks)
    ax.set_yticklabels(ticks, fontsize=22)

    ax.set_ylabel("Response time (ms)", fontsize=26)
    ax.set_title(f"Comparison per Image - {immagini[img_idx]}", fontsize=26)

    # ---------- IMPOSTA LIMITE ASSE Y ----------
    ax.set_ylim(0, max_value * 1.3)  # 30% più alto del massimo
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    safe_name = immagini[img_idx].replace("(", "").replace(")", "").replace(",", "_").replace(" ", "")
    plt.savefig(f"{safe_name}.png")
    plt.close()
'''
print("Esecuzione Completata")