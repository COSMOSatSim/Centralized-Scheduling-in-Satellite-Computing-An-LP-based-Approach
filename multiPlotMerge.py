import os
import pandas as pd
import matplotlib.pyplot as plt

###############################################
# STEP 1: Carica le due versioni di combined_data_AVG e combinane i dati
###############################################
cpu_timeout_value = 110
Arrival_Rate_value = 0.5
AP = 5
version = 'Plot'
# Imposta la directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Percorsi delle due versioni (assicurati che i file siano con questi nomi)
csv_v1 = os.path.join(current_directory, "combined_data_AVG_NO_penality.csv")
csv_v2 = os.path.join(current_directory, "combined_data_AVG_penality.csv")

try:
    df_v1 = pd.read_csv(csv_v1)
    df_v1["Versione"] = "V1"
    print(f"File {csv_v1} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {csv_v1}: {e}")
    df_v1 = pd.DataFrame()

try:
    df_v2 = pd.read_csv(csv_v2)
    df_v2["Versione"] = "V2"
    print(f"File {csv_v2} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {csv_v2}: {e}")
    df_v2 = pd.DataFrame()

# Unisci i due DataFrame
if not df_v1.empty or not df_v2.empty:
    df = pd.concat([df_v1, df_v2], ignore_index=True)
    combined_csv = os.path.join(current_directory, "combined_data_AVG_all_versions2.csv")
    df.to_csv(combined_csv, index=False)
    print(f"File combinato salvato in: {combined_csv}")
else:
    print("Nessun dato disponibile per la combinazione.")
    df = pd.DataFrame()

###############################################
# STEP 2: Prepara i dati
###############################################
# Converti Exec_after_set in percentuale
df["Exec_after_set"] = df["Exec_after_set"] * 100

# Aggiungi una nuova colonna: l'inverso di Arrival Rate
# (Assumiamo che Arrival Rate sia > 0; arrotondiamo a 2 decimali)
df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

# Imposta lo stile (usa "default" per evitare errori)
plt.style.use("default")

###############################################
# STEP 3: Grafico 1 - Average Response Time vs Arrival Rate
###############################################
# Filtra i dati per CPU_Timeout

df_rr = df[df["CPU_Timeout"] == cpu_timeout_value].copy()

# Raggruppa per Arrival Rate, Priority e Versione e calcola la media del Response Time
df_grouped = df_rr.groupby(["InvArrivalRate", "Priority", "Versione"])["Execution time"].mean().reset_index()
#df_grouped["Label"] = df_grouped["Priority"] + " " + df_grouped["Versione"]
df_grouped["Label"] = df_grouped.apply(lambda row: ("DTS-TMAX Orbit-aware" if row["Versione"]=="V2" else "DTS-TMAX")
                                       + " - " + row["Priority"], axis=1)
# Crea una tabella pivot: righe = Arrival Rate, colonne = Label, valori = average Response Time
pivot_rt = df_grouped.pivot(index="InvArrivalRate", columns="Label", values="Execution time")

# Per ottenere tick equidistanti, creiamo una mappatura categorica
inv_rates = sorted(df_rr["InvArrivalRate"].unique())
mapping = {val: i for i, val in enumerate(inv_rates)}

plt.figure(figsize=(10, 6))
for col in pivot_rt.columns:
    #plt.plot(pivot_rt.index, pivot_rt[col], marker="o", linestyle="-", label=col)
    # Sostituisci i valori dell'indice con le posizioni equidistanti
    x_positions = [mapping[val] for val in pivot_rt.index]
    print(col)
    if col == "DTS-TMAX Orbit-aware - high":
        plt.plot(x_positions, pivot_rt[col], marker="*", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware - low":
        plt.plot(x_positions, pivot_rt[col], marker="*", linestyle="-", label=col, color='#ff7f0e')
    if col == "DTS-TMAX - high":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="--", label=col, color='#2ca02c')
    if col == "DTS-TMAX - low":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="--", label=col, color='#d62728')
    #plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col)

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("Response Time (sec)", fontsize=14)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali
plt.title(" response_time_vs_arrival_rate ", fontsize=16)

# Imposta i tick equidistanti e usa le etichette reali
plt.xticks(range(len(inv_rates)), inv_rates)

output_dir = os.path.join(current_directory, "plot")
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, f"response time vs arrival rate CPU {cpu_timeout_value} AP {AP}.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 3b: Grafico - Average % Dropped Requests vs Arrival Rate (CPU_Timeout = 10)
###############################################

df_dr = df[df["CPU_Timeout"] == cpu_timeout_value].copy()
df_grouped_dr = df_dr.groupby(["InvArrivalRate", "Priority", "Versione"])["Exec_after_set"].mean().reset_index()
df_grouped_dr["Label"] = df_grouped_dr.apply(lambda row: ("DTS-TMAX Orbit-aware" if row["Versione"]=="V2" else "DTS-TMAX")
                                            + " - " + row["Priority"], axis=1)
pivot_dr = df_grouped_dr.pivot(index="InvArrivalRate", columns="Label", values="Exec_after_set")

inv_rates_dr = sorted(df_dr["InvArrivalRate"].unique())
mapping_dr = {val: i for i, val in enumerate(inv_rates_dr)}
'''
plt.figure(figsize=(10, 6))
for col in pivot_dr.columns:
    x_positions = [mapping_dr[val] for val in pivot_dr.index]
    if col == "DTS-TMAX Orbit-aware - high":
        plt.plot(x_positions, pivot_dr[col], marker="*", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware - low":
        plt.plot(x_positions, pivot_dr[col], marker="*", linestyle="-", label=col, color='#ff7f0e')
    if col == "DTS-TMAX - high":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="--", label=col, color='#2ca02c')
    if col == "DTS-TMAX - low":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="--", label=col, color='#d62728')

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
plt.title(f" % Dropped Requests vs Arrival Rate (CPU_Timeout = {cpu_timeout_value})", fontsize=16)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)

plt.savefig(os.path.join(output_dir, f"dropped requests vs arrival rate CPU {cpu_timeout_value} AP {AP}.png"), dpi=300, bbox_inches='tight')
plt.show()

pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.expand_frame_repr', False)  # Do not wrap rows'''
###############################################
# STEP 4: Funzione di plotting per gli altri grafici (Grafici 2-6) con confronto tra versioni
###############################################
def plot_graph(x, y, xlabel, ylabel, filename, filter_dict=None):
    print(f"Elaborazione del grafico: {filename}")
    plt.figure(figsize=(10, 6))

    # Filtra i dati se necessario
    df_filtered = df.copy()
    if filter_dict:
        for key, value in filter_dict.items():
            if isinstance(value, list):
                df_filtered = df_filtered[df_filtered[key].isin(value)]
            else:
                df_filtered = df_filtered[df_filtered[key] == value]

    # Se x è "Arrival Rate", usa la colonna trasformata "InvArrivalRate"
    # Se x è "AP", limita i valori a 5, 10, 15, 20
    if x == "AP":
        df_filtered[x] = pd.to_numeric(df_filtered[x], errors="coerce")
        df_filtered = df_filtered[df_filtered[x].isin([5, 10, 15, 20])]
    if x == "CPU_Timeout":
        df_filtered = df_filtered.sort_values(by=x)

    # Per ogni Versione, per ogni priorità e per ogni Arrival Rate, traccia la linea
    for versione in sorted(df_filtered["Versione"].unique()):
        df_version = df_filtered[df_filtered["Versione"] == versione]
        for priority in ["high", "low"]:
            df_priority = df_version[df_version["Priority"] == priority]
            for rate in sorted(df_priority["InvArrivalRate"].unique()):
                subset = df_priority[df_priority["InvArrivalRate"] == rate]
                if x == "AP":
                    subset = subset.sort_values(by=x)
                # Imposta la label in base alla versione e alla priorità
                if versione == "V2":
                    label = f"DTS-TMAX Orbit-aware - {priority} (AR {rate})"
                    if priority == "high":
                        plt.plot(subset[x], subset[y], marker="*", linestyle="-", label=f"{priority.capitalize()} Priority - Arrival Rate {rate}", color= '#1f77b4')
                    if priority == "low":
                        plt.plot(subset[x], subset[y], marker="*", linestyle="-", label=f"{priority.capitalize()} Priority - Arrival Rate {rate}", color='#ff7f0e')
                else:
                    label = f"DTS-TMAX - {priority} (AR {rate})"
                    if priority == "high":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="--", label=f"{priority.capitalize()} Priority - Arrival Rate {rate}", color= '#2ca02c')
                    if priority == "low":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="--", label=f"{priority.capitalize()} Priority - Arrival Rate {rate}", color='#d62728')


    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)

    #plt.title(title, fontsize=16)
    plt.legend()
    plt.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

    # Forza i tick dell'asse X se necessario
    if x == "AP" and y != "Exec_after_set":
        plt.xticks([5, 10, 15, 20])
        plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    elif x == "AP" and y == "Exec_after_set":
        plt.xticks([5, 10, 15, 20])
        plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    if x == "CPU_Timeout":
        plt.xticks([10, 30, 50, 70, 90, 110])
        plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])


    if x == "InvArrivalRate":
        inv_rates = sorted(df_filtered["InvArrivalRate"].unique())
        plt.xticks(inv_rates)

    output_dir = os.path.join(current_directory, "plot")
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
    plt.show()

###############################################
# STEP 5: Grafici 2-6 con confronto tra versioni
###############################################
plot_graph(
    x="AP", y="Response Time",
    xlabel="AP", ylabel="Response Time (sec)",
    filename=f"response time vs AP Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)
plot_graph(
    x="AP", y="RT_95th",
    xlabel="AP", ylabel=r"$95^{\mathrm{th}}$ % of $\,\mathrm{Response\ Time}$",
    filename=f"RT_95th vs AP Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)

plot_graph(
    x="CPU_Timeout", y="Response Time",
    xlabel="Service Time", ylabel="Average Response time (sec)",
    filename=f"Average Response time vs service time Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)
plot_graph(
    x="CPU_Timeout", y="RT_95th",
    xlabel="Service Time", ylabel=r"$95^{\mathrm{th}}$ % of $\,\mathrm{Response\ Time}$",
    filename=f"RT_95th vs service time Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)

plot_graph(
    x="AP", y="drop_rel",
    xlabel="AP", ylabel="% Dropped Requests",
    filename=f"dropped requests vs AP Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)

plot_graph(
    x="CPU_Timeout", y="drop_rel",
    xlabel="Service Time", ylabel="% Dropped Requests",
    filename=f"dropped requests vs service time AP{AP} Cpu {cpu_timeout_value}.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)


def plot_priority_changes(current_directory, output_dir, cpu_timeout_value, AP, mapping_dr, inv_rates_dr, Arrival_Rate_value):
    df = pd.read_csv(os.path.join(current_directory, "combined_data_AVG_all_versions.csv"))
    df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

    # 1) Percentage of Change vs InvArrivalRate
    df_ir = df[(df["CPU_Timeout"] == cpu_timeout_value) & (df["AP"] == AP)].sort_values("InvArrivalRate")
    fig, ax = plt.subplots(figsize=(10,6))
    for prio, col in [("high","Percent_High_Changed"),("low","Percent_Low_Changed")]:
        sub = df_ir[df_ir["Priority"] == prio]
        if not sub.empty:
            x = [mapping_dr[v] for v in sub["InvArrivalRate"]]
            y = sub[col]
            ax.plot(x, y, marker="o", linestyle="-",
                    label=f"{prio.capitalize()} Priority – Arrival Rate {round(1/Arrival_Rate_value, 2)}", alpha=0.8)

        # Per ogni Versione, per ogni priorità e per ogni Arrival Rate, traccia la linea
        for versione in sorted(df["Versione"].unique()):
            df_version = df[df["Versione"] == versione]
            for priority in ["high", "low"]:
                df_priority = df_version[df_version["Priority"] == priority]
                for rate in sorted(df_priority["InvArrivalRate"].unique()):
                    subset = df_priority[df_priority["InvArrivalRate"] == rate]
                    if df["AP"] == AP:
                        subset = subset.sort_values(by=x)
                    # Imposta la label in base alla versione e alla priorità
                    if versione == "V2":
                        label = f"DTS-TMAX Orbit-aware - {priority} (AR {rate})"
                        if priority == "high":
                            plt.plot(subset[x], subset[y], marker="*", linestyle="-", label=label, color='#1f77b4')
                        if priority == "low":
                            plt.plot(subset[x], subset[y], marker="*", linestyle="-", label=label, color='#ff7f0e')
                    else:
                        label = f"DTS-TMAX - {priority} (AR {rate})"
                        if priority == "high":
                            plt.plot(subset[x], subset[y], marker="o", linestyle="--", label=label, color='#2ca02c')
                        if priority == "low":
                            plt.plot(subset[x], subset[y], marker="o", linestyle="--", label=label, color='#d62728')

    ax.set_xticks(range(len(inv_rates_dr)))
    ax.set_xticklabels(inv_rates_dr)
    ax.set_yticks(range(0,101,10))
    ax.set_xlabel("Arrival Rate (task/sec)", fontsize=14)
    ax.set_ylabel("Percentage of Change", fontsize=14)
    #ax.set_title(f"Percentage of Change vs Arrival Rate\nCPU Timeout = {cpu_timeout_value}, AP = {AP}")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend()
    ax.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

    fname = f"percentage_change_vs_arrival_CPU{cpu_timeout_value}_AP{AP}.png"
    fig.savefig(os.path.join(output_dir, version + fname), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

    # 2) Percentage of Change vs Service Time
    df_ct = df[(df["InvArrivalRate"] == round(1/Arrival_Rate_value, 2)) & (df["AP"] == AP)]
    cpu_vals = sorted(df_ct["CPU_Timeout"].unique())
    fig, ax = plt.subplots(figsize=(10,6))
    for prio, col in [("high","Percent_High_Changed"),("low","Percent_Low_Changed")]:
        grp = df_ct[df_ct["Task Priority"] == prio].groupby("CPU_Timeout")[col].mean()
        if not grp.empty:
            y = [grp.get(ct,0) for ct in cpu_vals]
            ax.plot(cpu_vals, y, marker="o", linestyle="-",
                    label=f"{prio.capitalize()} Priority – Arrival Rate {round(1/Arrival_Rate_value, 2)}", alpha=0.8)
    ax.set_xticks(cpu_vals)
    ax.set_yticks(range(0,101,10))
    ax.set_xlabel("Service Time", fontsize=14)
    ax.set_ylabel("Percentage of Change", fontsize=14)
    #ax.set_title(f"Percentage of Change vs Service Time\nAP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend()
    ax.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

    fname = f"percentage_change_vs_service_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"
    fig.savefig(os.path.join(output_dir, version + fname), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

    # 3) Percentage of Change vs AP
    df_ap = df[(df["CPU_Timeout"] == cpu_timeout_value) & (df["InvArrivalRate"] == round(1/Arrival_Rate_value, 2))]
    ap_vals = sorted(df_ap["AP"].unique())
    inv_rates = sorted(df_ap["InvArrivalRate"].unique())
    fig, ax = plt.subplots(figsize=(10,6))
    for prio in ["high","low"]:
        col = "Percent_High_Changed" if prio=="high" else "Percent_Low_Changed"
        dfp = df_ap[df_ap["Task Priority"] == prio]
        for rate in inv_rates:
            sub = dfp[dfp["InvArrivalRate"] == rate].sort_values("AP")
            if not sub.empty:
                ax.plot(sub["AP"], sub[col], marker="o", linestyle="-",
                        label=f"{prio.capitalize()} Priority – Arrival Rate {rate}", alpha=0.8)
    ax.set_xticks(ap_vals)
    ax.set_yticks(range(0,101,10))
    ax.set_xlabel("AP", fontsize=14)
    ax.set_ylabel("Percentage of Change", fontsize=14)
    #ax.set_title(f"Percentage of Change vs AP\nCPU Timeout = {cpu_timeout_value}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend()
    ax.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

    fname = f"percentage_change_vs_AP_CPU{cpu_timeout_value}_AR{round(1/Arrival_Rate_value, 2)}.png"
    fig.savefig(os.path.join(output_dir, version + fname), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

#plot_priority_changes(current_directory, output_dir, cpu_timeout_value, AP, mapping_dr, inv_rates_dr, Arrival_Rate_value )

###############################################
# STEP X: Stacked bar – % Dropped Requests (high, low, total) vs CPU_Timeout
###############################################
print("Elaborazione dello Stacked Bar: % Dropped (high, low, total) vs Service Time")

# 1) Filtra df su AP e Arrival Rate correnti
df_stack = df[(df["AP"] == AP) & (df["InvArrivalRate"] == round(1/Arrival_Rate_value, 2))].copy()

# 2) Raggruppa e calcola media drop_rel per Priority e CPU_Timeout
agg_stack = (
    df_stack
    .groupby(["CPU_Timeout", "Priority"])["drop_rel"]
    .mean()
    .unstack(fill_value=0)
)

# 3) Calcola la componente totale
agg_stack["total"] = agg_stack.get("high", 0) + agg_stack.get("low", 0)

# 4) Plot stacked bar
cpu_vals = sorted(agg_stack.index)
high_vals = agg_stack.loc[cpu_vals, "high"] if "high" in agg_stack else [0]*len(cpu_vals)
low_vals  = agg_stack.loc[cpu_vals, "low"]  if "low"  in agg_stack else [0]*len(cpu_vals)
tot_vals  = agg_stack.loc[cpu_vals, "total"]

plt.figure(figsize=(10,6))

# prima low, poi high, poi total sopra (o come preferisci l’ordine)
plt.bar(cpu_vals, low_vals,  label=f"Low Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}")
plt.bar(cpu_vals, high_vals, bottom=low_vals, label=f"High Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}")
#plt.bar(cpu_vals, tot_vals,  bottom=(low_vals+high_vals), alpha=0.3, label="Total")

plt.xlabel("Service Time", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(f"Stacked % Dropped Requests vs Service Time\nAP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}", fontsize=16)
plt.xticks(cpu_vals)
plt.yticks(range(0, 101, 10))
plt.ylim(0, 100)
plt.legend()

plt.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

# Salvataggio
fname = f"stacked_drop_rel_vs_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"

plt.savefig(os.path.join(output_dir, version + fname), dpi=300, bbox_inches='tight')

plt.show()

###############################################
# STEP Xb: Stacked area plot – % Dropped Requests vs CPU_Timeout
###############################################
print("Elaborazione dello Stacked Area Plot: % Dropped Requests vs Service Time")

plt.figure(figsize=(10,6))

# Crea l'area impilata per low e high
plt.stackplot(
    cpu_vals,
    low_vals,
    high_vals,
    #tot_vals,
    labels=[f"Low Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}", f"High Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}"],
    alpha=0.6
)
tot = tot_vals+low_vals+high_vals
plt.plot(cpu_vals, tot_vals, marker="o", linestyle="--", label="Total", color="black")
plt.xlabel("Service Time", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(f"Stacked Area Plot % Dropped Requests\nAP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}", fontsize=16)
plt.xticks(cpu_vals)
plt.yticks(range(0, 101, 10))
plt.ylim(0, 100)
plt.legend()
plt.grid(True, axis='y', linestyle='--', linewidth=0.7)  # solo linee orizzontali

# Salvataggio
fname = f"stacked_area_drop_rel_vs_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"
plt.savefig(os.path.join(output_dir, version + fname), dpi=300, bbox_inches='tight')
plt.show()

