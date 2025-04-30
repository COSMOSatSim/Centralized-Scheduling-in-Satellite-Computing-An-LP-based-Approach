import os
import pandas as pd
import matplotlib.pyplot as plt

# Filtri
cpu_timeout_value = 110
Arrival_Rate_value = 0.5  # scegliere tra 0.5, 1, 1.5, 2, 2.5, 3
AP = 5

###############################################
# STEP 1: Combina i file CSV in "combined_data_AVG.csv"
###############################################

# Imposta la directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Salva il grafico
output_dir = os.path.join(current_directory, "single_plot")
os.makedirs(output_dir, exist_ok=True)

# Percorsi dei file di input
high_csv = os.path.join(current_directory, "data_High_priority.csv")
low_csv = os.path.join(current_directory, "data_Low_priority.csv")

# Leggi i due file CSV
try:
    df_high = pd.read_csv(high_csv)
    print(f"File {high_csv} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {high_csv}: {e}")
    df_high = pd.DataFrame()

try:
    df_low = pd.read_csv(low_csv)
    print(f"File {low_csv} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {low_csv}: {e}")
    df_low = pd.DataFrame()

# Combina i due DataFrame se non sono vuoti
if not df_high.empty or not df_low.empty:
    combined_df = pd.concat([df_high, df_low], ignore_index=True)
    combined_csv = os.path.join(current_directory, "combined_data_AVG_NO_penality.csv")
    combined_df.to_csv(combined_csv, index=False)
    print(f"File combinato salvato in: {combined_csv}")
else:
    print("Nessun dato disponibile per la combinazione.")

###############################################
# STEP 2: Leggi il file combinato e prepara i dati
###############################################

combined_csv = os.path.join(current_directory, "combined_data_AVG_NO_penality.csv")
try:
    df = pd.read_csv(combined_csv)
    print(f"File {combined_csv} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {combined_csv}: {e}")
    df = pd.DataFrame()

# Converti drop_rel in percentuale
df["drop_rel"] = df["drop_rel"] * 100

# Aggiungi una nuova colonna: l'inverso di Arrival Rate
df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

# Imposta lo stile (usa "default" per evitare errori)
plt.style.use("default")


###############################################
# STEP 3: Grafico 1 - Average Response Time vs Arrival Rate
###############################################
print("Elaborazione del Grafico 1: Response Time vs Arrival Rate")
df_dr = df[df["CPU_Timeout"] == cpu_timeout_value].copy()
df_grouped_dr = df_dr.groupby(["InvArrivalRate", "Priority"])["drop_rel"].mean().reset_index()
df_grouped_dr["Label"] = df_grouped_dr.apply(lambda row: ("DTS-TMAX Orbit-aware") + " - " + row["Priority"], axis=1)
pivot_dr = df_grouped_dr.pivot(index="InvArrivalRate", columns="Label", values="drop_rel")

# Valori unici ordinati di InvArrivalRate
inv_rates_dr = sorted(df_dr["InvArrivalRate"].unique())
mapping_dr = {val: i for i, val in enumerate(inv_rates_dr)}

# Tabella pivot per response time
pivot_rt = df_dr.pivot_table(index="InvArrivalRate", columns="Priority", values="Response Time", aggfunc="mean")

plt.figure(figsize=(10, 6))

# Mappa le posizioni X in base al mapping
x_positions = [mapping_dr[val] for val in pivot_rt.index]

# Traccia la linea per High Priority (se presente)
if "high" in pivot_rt.columns:
    plt.plot(x_positions, pivot_rt["high"], marker="o", linestyle="-", label="High Priority")
# Traccia la linea per Low Priority (se presente)
if "low" in pivot_rt.columns:
    plt.plot(x_positions, pivot_rt["low"], marker="o", linestyle="-", label="Low Priority")

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("Response Time (sec)", fontsize=14)
#plt.title(f"Response Time vs Arrival Rate - CPU Timeout = {cpu_timeout_value}", fontsize=16)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)
plt.savefig(os.path.join(output_dir, f"response time vs arrival rate CPU {cpu_timeout_value} AR {Arrival_Rate_value}.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 3b: Grafico - Average % Dropped Requests vs Arrival Rate
###############################################
'''print("Elaborazione del Grafico 3b: % Dropped Requests vs Arrival Rate")
plt.figure(figsize=(10, 6))
for col in pivot_dr.columns:
    x_positions = [mapping_dr[val] for val in pivot_dr.index]
    if col == "DTS-TMAX Orbit-aware - high":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware - low":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#ff7f0e')

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
plt.title(f"% Dropped Requests vs Arrival Rate (CPU_Timeout = {cpu_timeout_value})", fontsize=16)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)

plt.savefig(os.path.join(output_dir, f"dropped requests vs arrival rate avg CPU {cpu_timeout_value}.png"), dpi=300, bbox_inches='tight')
plt.show()'''
###############################################
# STEP 4: Funzione di plotting per gli altri grafici (Grafici 2-6)
###############################################
def plot_graph(x, y, xlabel, ylabel, filename, filter_dict=None):
    print(f"Elaborazione del grafico: {filename}")
    plt.figure(figsize=(10, 6))

    df_filtered = df.copy()
    if filter_dict:
        for key, value in filter_dict.items():
            if isinstance(value, list):
                df_filtered = df_filtered[df_filtered[key].isin(value)]
            else:
                df_filtered = df_filtered[df_filtered[key] == value]

    # Se x è "AP", assicura di avere solo i valori 5,10,15,20
    if x == "AP":
        df_filtered[x] = pd.to_numeric(df_filtered[x], errors='coerce')
        df_filtered = df_filtered[df_filtered[x].isin([5, 10, 15, 20])]
    if x == "CPU_Timeout":
        df_filtered = df_filtered.sort_values(by=x)
    # Plot per ciascuna priorità e per ogni InvArrivalRate
    for priority in ["high", "low"]:
        df_priority = df_filtered[df_filtered["Priority"] == priority]
        for rate in sorted(df_priority["InvArrivalRate"].unique()):
            subset = df_priority[df_priority["InvArrivalRate"] == rate]
            if x == "AP":
                subset = subset.sort_values(by=x)
            plt.plot(subset[x], subset[y], marker="o", linestyle="-",
                     label=f"{priority.capitalize()} Priority - Arrival Rate {rate}")

    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.xlabel(xlabel, fontsize=14)
    #r"$95^{\mathrm{th}}$ perc. di Response Time"
    plt.ylabel(ylabel, fontsize=14)
    #plt.title(filename.split('.')[0], fontsize=16)
    plt.legend()
    plt.grid(False)
    if x == "AP":
        plt.xticks([5, 10, 15, 20])
    if x == "CPU_Timeout":
        plt.xticks([10, 30, 50, 70, 90, 110])

    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.show()

###############################################
# STEP 5: Grafico a linee - Estimated Execution Time (Executed vs Dropped)
###############################################
'''print("Elaborazione del Grafico 6: Estimated Execution Time (Executed vs Dropped)")
# Filtra per CPU_Timeout e per un AP specifico (es. AP = 5)
df_plot = df[(df["CPU_Timeout"] == cpu_timeout_value) & (df["AP"] == AP)].copy()

# Raggruppa per InvArrivalRate e Priority e calcola la media delle colonne di interesse
agg_df = df_plot.groupby(["InvArrivalRate", "Priority"])[["estimated_execution_time_executed", "estimated_execution_time_dropped"]].mean().reset_index()
# Ordina in base a InvArrivalRate
agg_df = agg_df.sort_values(by="InvArrivalRate")

# Crea le pivot table per avere, per ogni InvArrivalRate, i valori per ciascuna Priority
pivot_exec = agg_df.pivot(index="InvArrivalRate", columns="Priority", values="estimated_execution_time_executed").sort_index()
pivot_drop = agg_df.pivot(index="InvArrivalRate", columns="Priority", values="estimated_execution_time_dropped").sort_index()

plt.figure(figsize=(10, 6))
# Usa i valori dell'indice ordinato per creare x_positions
# qui estraiamo le posizioni corrispondenti a quelli effettivamente presenti nelle pivot.
x_positions = [mapping_dr[val] for val in pivot_exec.index]

if "high" in pivot_exec.columns:
    plt.plot(x_positions, pivot_exec["high"], marker="o", linestyle="-", label="High - Executed", alpha=0.8)
    plt.plot(x_positions, pivot_drop["high"], marker="o", linestyle="--", label="High - Dropped", alpha=0.8)
if "low" in pivot_exec.columns:
    plt.plot(x_positions, pivot_exec["low"], marker="o", linestyle="-", label="Low - Executed", alpha=0.8)
    plt.plot(x_positions, pivot_drop["low"], marker="o", linestyle="--", label="Low - Dropped", alpha=0.8)

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("Estimated Execution Time", fontsize=14)
#plt.title(f"Estimated Execution Time (Executed vs Dropped Tasks) \n CPU Timeout = {cpu_timeout_value} AP = {AP}", fontsize=16)
# Verifica che i tuoi dati rientrino in questa scala; in caso contrario, modifica i ticks
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)
plt.legend()
plt.grid(False)

plt.savefig(os.path.join(output_dir, f"Estimated execution time VS CPU {cpu_timeout_value} AP {AP}.png"), dpi=300, bbox_inches='tight')
plt.show()'''
###############################################
# STEP 6: Grafico 6a - Estimated Execution Time vs Service Time
###############################################
'''print("Elaborazione del Grafico 6a: Estimated Execution Time vs Service Time")
df_service = df[(df["InvArrivalRate"] == round(1/Arrival_Rate_value, 2)) & (df["AP"] == AP)].copy()
if not df_service.empty:
    agg_service = df_service.groupby(["CPU_Timeout", "Priority"])[
        ["estimated_execution_time_executed", "estimated_execution_time_dropped"]].mean().reset_index()
    pivot_service_exec = agg_service.pivot(index="CPU_Timeout", columns="Priority",
                                           values="estimated_execution_time_executed")
    pivot_service_drop = agg_service.pivot(index="CPU_Timeout", columns="Priority",
                                           values="estimated_execution_time_dropped")
    service_time_ticks = [10, 30, 50, 70, 90, 110]
    plt.figure(figsize=(10, 6))
    for priority in ["high", "low"]:
        if priority in pivot_service_exec.columns:
            y_exec = pivot_service_exec.reindex(service_time_ticks)[priority]
            y_drop = pivot_service_drop.reindex(service_time_ticks)[priority]
            plt.plot(service_time_ticks, y_exec,
                     marker="o", linestyle="-", label=f"{priority.capitalize()} - Executed", alpha=0.8)
            plt.plot(service_time_ticks, y_drop,
                     marker="o", linestyle="--", label=f"{priority.capitalize()} - Dropped", alpha=0.8)
    plt.xlabel("Service Time", fontsize=14)
    plt.ylabel("Estimated Execution Time", fontsize=14)
    #plt.title(f"Estimated Execution Time vs Service Time\n(AP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)})", fontsize=16)
    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.xticks(service_time_ticks)
    plt.legend()
    plt.grid(False)
    AR = '0,5'
    if Arrival_Rate_value == '0.5': AR = '0,5'
    plt.savefig(os.path.join(output_dir,
                             f"Estimated Execution Time vs Service Time AP{AP} AR {AR}"),
                dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("Nessun dato per il filtro attuale per il Grafico 6a (Service Time).")
'''
###############################################
# STEP 7: Grafico 6b - Estimated Execution Time vs AP
###############################################
'''
print("Elaborazione del Grafico 6b: Estimated Execution Time vs AP")
df_ap = df[(df["CPU_Timeout"] == cpu_timeout_value) & (df["InvArrivalRate"] == round(1/Arrival_Rate_value, 2))].copy()
if not df_ap.empty:
    agg_ap = df_ap.groupby(["AP", "Priority"])[["estimated_execution_time_executed", "estimated_execution_time_dropped"]].mean().reset_index()
    pivot_ap_exec = agg_ap.pivot(index="AP", columns="Priority", values="estimated_execution_time_executed")
    pivot_ap_drop = agg_ap.pivot(index="AP", columns="Priority", values="estimated_execution_time_dropped")
    ap_values = sorted(df_ap["AP"].unique())
    plt.figure(figsize=(10, 6))
    for priority in ["high", "low"]:
        if priority in pivot_ap_exec.columns:
            plt.plot(ap_values,
                     pivot_ap_exec.reindex(ap_values)[priority],
                     marker="o", linestyle="-", label=f"{priority.capitalize()} - Executed", alpha=0.8)
            plt.plot(ap_values,
                     pivot_ap_drop.reindex(ap_values)[priority],
                     marker="o", linestyle="--", label=f"{priority.capitalize()} - Dropped", alpha=0.8)
    plt.xlabel("AP", fontsize=14)
    plt.ylabel("Estimated Execution Time", fontsize=14)
    #plt.title(f"Estimated Execution Time vs AP\n(CPU Timeout = {cpu_timeout_value}, Arrival Rate = {round(1/Arrival_Rate_value, 2)})", fontsize=16)
    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.xticks(ap_values)
    plt.legend()
    plt.grid(False)
    plt.savefig(os.path.join(output_dir, f"Estimated execution time vs AP{AP} Cpu {cpu_timeout_value} AR {Arrival_Rate_value}.png"), dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("Nessun dato per il filtro per il Grafico 6b (vs AP).")
'''
###############################################
# STEP 8: Grafici 2-6 (chiamate alla funzione plot_graph)
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
'''
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
)'''


def plot_priority_changes(current_directory, output_dir, cpu_timeout_value, AP, mapping_dr, inv_rates_dr, Arrival_Rate_value):
    df = pd.read_csv(os.path.join(current_directory, "priority_change_data.csv"))
    df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

    # 1) Percentage of Change vs InvArrivalRate
    df_ir = df[(df["CPU_Timeout"] == cpu_timeout_value) & (df["AP"] == AP)].sort_values("InvArrivalRate")
    fig, ax = plt.subplots(figsize=(10,6))
    for prio, col in [("high","Percent_High_Changed"),("low","Percent_Low_Changed")]:
        sub = df_ir[df_ir["Task Priority"] == prio]
        if not sub.empty:
            x = [mapping_dr[v] for v in sub["InvArrivalRate"]]
            y = sub[col]
            ax.plot(x, y, marker="o", linestyle="-",
                    label=f"{prio.capitalize()} Priority – Arrival Rate {round(1/Arrival_Rate_value, 2)}", alpha=0.8)
    ax.set_xticks(range(len(inv_rates_dr)))
    ax.set_xticklabels(inv_rates_dr)
    ax.set_yticks(range(0,101,10))
    ax.set_xlabel("Arrival Rate (task/sec)", fontsize=14)
    ax.set_ylabel("Percentage of Change", fontsize=14)
    #ax.set_title(f"Percentage of Change vs Arrival Rate\nCPU Timeout = {cpu_timeout_value}, AP = {AP}")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend()
    ax.grid(False)
    fname = f"percentage_change_vs_arrival_CPU{cpu_timeout_value}_AP{AP}.png"
    fig.savefig(os.path.join(output_dir, fname), dpi=300, bbox_inches="tight")
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
    ax.grid(False)
    fname = f"percentage_change_vs_service_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"
    fig.savefig(os.path.join(output_dir, fname), dpi=300, bbox_inches="tight")
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
    ax.grid(False)
    fname = f"percentage_change_vs_AP_CPU{cpu_timeout_value}_AR{round(1/Arrival_Rate_value, 2)}.png"
    fig.savefig(os.path.join(output_dir, fname), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

plot_priority_changes(current_directory, output_dir, cpu_timeout_value, AP, mapping_dr, inv_rates_dr, Arrival_Rate_value )

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
plt.bar(cpu_vals, tot_vals,  bottom=(low_vals+high_vals), alpha=0.3, label="Total")

plt.xlabel("Service Time", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(f"Stacked % Dropped Requests vs Service Time\nAP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}", fontsize=16)
plt.xticks(cpu_vals)
plt.yticks(range(0, 101, 10))
plt.ylim(0, 100)
plt.legend()
plt.grid(False)

# Salvataggio
fname = f"stacked_drop_rel_vs_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"
plt.savefig(os.path.join(output_dir, fname), dpi=300, bbox_inches='tight')
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
    tot_vals,
    labels=[f"Low Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}", f"High Priority - Arrival Rate {round(1/Arrival_Rate_value, 2)}"],
    alpha=0.6
)
tot = tot_vals+low_vals+high_vals
plt.plot(cpu_vals, tot, marker="o", linestyle="--", label="Total", color="black")
plt.xlabel("Service Time", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(f"Stacked Area Plot % Dropped Requests\nAP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)}", fontsize=16)
plt.xticks(cpu_vals)
plt.yticks(range(0, 101, 10))
plt.ylim(0, 100)
plt.legend()
plt.grid(False)

# Salvataggio
fname = f"stacked_area_drop_rel_vs_CPU{cpu_timeout_value}_AP{AP}_AR{round(1/Arrival_Rate_value, 2)}.png"
plt.savefig(os.path.join(output_dir, fname), dpi=300, bbox_inches='tight')
plt.show()
