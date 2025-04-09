import os
import pandas as pd
import matplotlib.pyplot as plt

###############################################
# STEP 1: Carica le due versioni di combined_data_AVG e combinane i dati
###############################################
cpu_timeout_value = 110
Arrival_Rate_value = 3
AP = 5

# Imposta la directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Percorsi delle due versioni (assicurati che i file siano con questi nomi)
csv_v1 = os.path.join(current_directory, "combined_data_AVG_penality.csv")
csv_v2 = os.path.join(current_directory, "combined_data_AVG_penality_utility_prima versione funzionante.csv")

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
    combined_csv = os.path.join(current_directory, "combined_data_AVG_all_versions.csv")
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
df_grouped["Label"] = df_grouped.apply(lambda row: ("DTS-TMAX Orbit-aware penality" if row["Versione"]=="V1" else "DTS-TMAX penality_utility")
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
    if col == "DTS-TMAX Orbit-aware penality - high":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware penality - low":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col, color='#ff7f0e')
    if col == "DTS-TMAX penality_utility - high":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col, color='#2ca02c')
    if col == "DTS-TMAX penality_utility - low":
        plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col, color='#d62728')
    #plt.plot(x_positions, pivot_rt[col], marker="o", linestyle="-", label=col)

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("Response Time (sec)", fontsize=14)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)

# Imposta i tick equidistanti e usa le etichette reali
plt.xticks(range(len(inv_rates)), inv_rates)

output_dir = os.path.join(current_directory, "plot")
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, "response_time_vs_arrival_rate_avg.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 3b: Grafico - Average % Dropped Requests vs Arrival Rate (CPU_Timeout = 10)
###############################################

df_dr = df[df["CPU_Timeout"] == cpu_timeout_value].copy()
df_grouped_dr = df_dr.groupby(["InvArrivalRate", "Priority", "Versione"])["Exec_after_set"].mean().reset_index()
df_grouped_dr["Label"] = df_grouped_dr.apply(lambda row: ("DTS-TMAX Orbit-aware penality" if row["Versione"]=="V1" else "DTS-TMAX penality_utility")
                                            + " - " + row["Priority"], axis=1)
pivot_dr = df_grouped_dr.pivot(index="InvArrivalRate", columns="Label", values="Exec_after_set")

inv_rates_dr = sorted(df_dr["InvArrivalRate"].unique())
mapping_dr = {val: i for i, val in enumerate(inv_rates_dr)}

plt.figure(figsize=(10, 6))
for col in pivot_dr.columns:
    x_positions = [mapping_dr[val] for val in pivot_dr.index]
    if col == "DTS-TMAX Orbit-aware penality - high":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware penality - low":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#ff7f0e')
    if col == "DTS-TMAX penality_utility - high":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#2ca02c')
    if col == "DTS-TMAX penality_utility - low":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#d62728')


plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(" % Dropped Requests vs Arrival Rate (CPU_Timeout = 10)", fontsize=16)
plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)

plt.savefig(os.path.join(output_dir, "dropped_requests_vs_arrival_rate_avg.png"), dpi=300, bbox_inches='tight')
plt.show()

pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.expand_frame_repr', False)  # Do not wrap rows
###############################################
# STEP 4: Funzione di plotting per gli altri grafici (Grafici 2-6) con confronto tra versioni
###############################################
def plot_graph(x, y, xlabel, ylabel, title, filename, filter_dict=None):
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
        print(df_version)
        for priority in ["high", "low"]:
            df_priority = df_version[df_version["Priority"] == priority]
            for rate in sorted(df_priority["InvArrivalRate"].unique()):
                subset = df_priority[df_priority["InvArrivalRate"] == rate]
                if x == "AP":
                    subset = subset.sort_values(by=x)
                # Imposta la label in base alla versione e alla priorità
                if versione == "V1":
                    label = f"DTS-TMAX Orbit-aware penality- {priority} (AR {rate})"
                    if priority == "high":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="-", label=label, color= '#1f77b4')
                    if priority == "low":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="-", label=label, color='#ff7f0e')
                else:
                    label = f"DTS-TMAX Orbit-aware penality_utility - {priority} (AR {rate})"
                    if priority == "high":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="-", label=label, color= '#2ca02c')
                    if priority == "low":
                        plt.plot(subset[x], subset[y], marker="o", linestyle="-", label=label, color='#d62728')


    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    #plt.title(title, fontsize=16)
    plt.legend()
    plt.grid(False)

    # Forza i tick dell'asse X se necessario
    if x == "AP":
        plt.xticks([5, 10, 15, 20])
    if x == "CPU_Timeout":
        plt.xticks([10, 30, 50, 70, 90, 110])
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
# Grafico 2: Response Time vs AP (CPU_Timeout = 10, task/sec = 1)

plot_graph(
    x="AP", y="Response Time",
    xlabel="AP", ylabel="Response Time (sec)",
    title=f"Response Time vs AP (CPU_Timeout = {cpu_timeout_value}, Task/sec = 1)",
    filename="response_time_vs_AP.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)

# Grafico 3: Response Time vs CPU_Timeout (Task/sec = 1, AP = 5)
plot_graph(
    x="CPU_Timeout", y="Response Time",
    xlabel="Service Time", ylabel="Response Time (sec)",
    title="Response Time vs Service Time (Task/sec = 1, AP = 5)",
    filename="response_time_vs_service_time.png",
    filter_dict={"AP": 5, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)


# Grafico 5: % Dropped Requests vs AP (CPU_Timeout = 10, task/sec = 1)
plot_graph(
    x="AP", y="Exec_after_set",
    xlabel="AP", ylabel="% Dropped Requests",
    title=f"% Dropped Requests vs AP (CPU_Timeout = {cpu_timeout_value}, Task/sec = 1)",
    filename="dropped_requests_vs_AP.png",
    filter_dict={"CPU_Timeout": cpu_timeout_value, "Arrival Rate": Arrival_Rate_value, "AP": [5, 10, 15, 20]}
)

# Grafico 6: % Dropped Requests vs CPU_Timeout (Task/sec = 1, AP = 5)
plot_graph(
    x="CPU_Timeout", y="Exec_after_set",
    xlabel="Service Time", ylabel="% Dropped Requests",
    title="% Dropped Requests vs Service Time (Task/sec = 1, AP = 5)",
    filename="dropped_requests_vs_service_time.png",
    filter_dict={"AP": AP, "Arrival Rate": Arrival_Rate_value, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)
