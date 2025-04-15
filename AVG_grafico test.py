import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Filtri
cpu_timeout_value = 110
Arrival_Rate_value = 3  # scegliere tra 0.5, 1, 1.5, 2, 2.5, 3
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
    combined_csv = os.path.join(current_directory, "combined_data_AVG_penality.csv")
    combined_df.to_csv(combined_csv, index=False)
    print(f"File combinato salvato in: {combined_csv}")
else:
    print("Nessun dato disponibile per la combinazione.")

###############################################
# STEP 2: Leggi il file combinato e prepara i dati
###############################################

combined_csv = os.path.join(current_directory, "combined_data_AVG_penality.csv")
try:
    df = pd.read_csv(combined_csv)
    print(f"File {combined_csv} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {combined_csv}: {e}")
    df = pd.DataFrame()

# Converti Exec_after_set in percentuale
df["Exec_after_set"] = df["Exec_after_set"] * 100

# Aggiungi una nuova colonna: l'inverso di Arrival Rate
df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

# Imposta lo stile (usa "default" per evitare errori)
plt.style.use("default")

###############################################
# STEP 3: Grafico 1 - Average Response Time vs Arrival Rate
###############################################
print("Elaborazione del Grafico 1: Response Time vs Arrival Rate")
df_dr = df[df["CPU_Timeout"] == cpu_timeout_value].copy()
df_grouped_dr = df_dr.groupby(["InvArrivalRate", "Priority"])["Exec_after_set"].mean().reset_index()
df_grouped_dr["Label"] = df_grouped_dr.apply(lambda row: ("DTS-TMAX Orbit-aware") + " - " + row["Priority"], axis=1)
pivot_dr = df_grouped_dr.pivot(index="InvArrivalRate", columns="Label", values="Exec_after_set")

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
plt.title(f"Response Time vs Arrival Rate - CPU Timeout = {cpu_timeout_value}", fontsize=16)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)
plt.savefig(os.path.join(output_dir, f"response time vs arrival rate CPU {cpu_timeout_value} AR {Arrival_Rate_value}.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 3b: Grafico - Average % Dropped Requests vs Arrival Rate
###############################################
print("Elaborazione del Grafico 3b: % Dropped Requests vs Arrival Rate")
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
plt.show()

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
                     label=f"{priority} Priority - Arrival Rate {rate}")

    plt.xlabel(xlabel, fontsize=14)

    if ylabel == "Response Time (sec)":
        plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.ylabel(ylabel, fontsize=14)
    plt.title(filename.split('.')[0], fontsize=16)
    plt.legend()
    plt.grid(False)
    if x == "AP":
        plt.xticks([5, 10, 15, 20])
    if x == "CPU_Timeout":
        plt.xticks([10, 30, 50, 70, 90, 110])

    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.show()

###############################################
# STEP 6: Grafico a linee - Estimated Execution Time (Executed vs Dropped)
###############################################
print("Elaborazione del Grafico 6: Estimated Execution Time (Executed vs Dropped)")
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
# Se mapping_dr è basato su df_dr definito precedentemente e contiene tutti i possibili valori,
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
plt.title(f"Estimated Execution Time (Executed vs Dropped Tasks) \n CPU Timeout = {cpu_timeout_value} AP = {AP}", fontsize=16)
# Verifica che i tuoi dati rientrino in questa scala; in caso contrario, modifica i ticks
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)
plt.legend()
plt.grid(False)

plt.savefig(os.path.join(output_dir, f"Estimated execution time VS CPU {cpu_timeout_value} AP {AP}.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 8: Grafico 6a - Estimated Execution Time vs Service Time
###############################################
print("Elaborazione del Grafico 6a: Estimated Execution Time vs Service Time")
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
    plt.xlabel("Service Time (CPU_Timeout)", fontsize=14)
    plt.ylabel("Estimated Execution Time", fontsize=14)
    plt.title(f"Estimated Execution Time vs Service Time\n(AP = {AP}, Arrival Rate = {round(1/Arrival_Rate_value, 2)})", fontsize=16)
    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.xticks(service_time_ticks)
    plt.legend()
    plt.grid(False)
    plt.savefig(os.path.join(output_dir,
                             f"Estimated Execution Time vs Service Time AP{AP} AR {Arrival_Rate_value}"),
                dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("Nessun dato per il filtro attuale per il Grafico 6a (Service Time).")

###############################################
# STEP 9: Grafico 6b - Estimated Execution Time vs AP
###############################################
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
    plt.title(f"Estimated Execution Time vs AP\n(CPU Timeout = {cpu_timeout_value}, Arrival Rate = {round(1/Arrival_Rate_value, 2)})", fontsize=16)
    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    plt.xticks(ap_values)
    plt.legend()
    plt.grid(False)
    plt.savefig(os.path.join(output_dir, f"Estimated execution time vs AP{AP} Cpu {cpu_timeout_value} AR {Arrival_Rate_value}.png"), dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("Nessun dato per il filtro per il Grafico 6b (vs AP).")

###############################################
# STEP 5: Grafici 2-6 (chiamate alla funzione plot_graph)
###############################################
plot_graph(
    x="AP", y="Response Time",
    xlabel="AP", ylabel="Response Time (sec)",
    filename=f"response time vs AP Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)

plot_graph(
    x="CPU_Timeout", y="Response Time",
    xlabel="Service Time", ylabel="Response Time (sec)",
    filename=f"response time vs service time Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)

plot_graph(
    x="AP", y="Exec_after_set",
    xlabel="AP", ylabel="% Dropped Requests",
    filename=f"dropped requests vs AP Cpu {cpu_timeout_value} AP{AP}.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)
plot_graph(
    x="CPU_Timeout", y="Exec_after_set",
    xlabel="Service Time", ylabel="% Dropped Requests",
    filename=f"dropped requests vs service time AP{AP} Cpu {cpu_timeout_value}.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)
