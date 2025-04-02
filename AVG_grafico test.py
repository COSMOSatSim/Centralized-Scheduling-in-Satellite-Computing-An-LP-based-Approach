import os
import pandas as pd
import matplotlib.pyplot as plt

###############################################
# STEP 1: Combina i file CSV in "combined_data_AVG.csv"
###############################################

# Imposta la directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

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
    combined_csv = os.path.join(current_directory, "combined_data_AVG_NoOrbit.csv")
    combined_df.to_csv(combined_csv, index=False)
    print(f"File combinato salvato in: {combined_csv}")
else:
    print("Nessun dato disponibile per la combinazione.")

###############################################
# STEP 2: Leggi il file combinato e prepara i dati
###############################################
combined_csv = os.path.join(current_directory, "combined_data_AVG_NoOrbit.csv")
try:
    df = pd.read_csv(combined_csv)
    print(f"File {combined_csv} letto correttamente.")
except Exception as e:
    print(f"Errore nella lettura di {combined_csv}: {e}")
    df = pd.DataFrame()

# Converti Exec_after_set in percentuale
df["Exec_after_set"] = df["Exec_after_set"] * 100

# Aggiungi una nuova colonna: l'inverso di Arrival Rate
# (Assumiamo che Arrival Rate sia > 0; arrotondiamo a 2 decimali)
df["InvArrivalRate"] = df["Arrival Rate"].apply(lambda x: round(1/x, 2) if x != 0 else None)

# Imposta lo stile (usa "default" per evitare errori)
plt.style.use("default")

###############################################
# STEP 3: Grafico 1 - Average Response Time vs Arrival Rate (CPU_Timeout = 10)
###############################################
# Filtra i dati per CPU_Timeout = 10
df_rr = df[df["CPU_Timeout"] == 10].copy()

# Raggruppa per Arrival Rate e Priority e calcola la media del Response Time
df_grouped = df_rr.groupby(["Arrival Rate", "Priority"])["Response Time"].mean().reset_index()
print(df_grouped)
# Crea una tabella pivot: righe = Arrival Rate, colonne = Priority, valori = average response time
pivot_rt = df_grouped.pivot(index="Arrival Rate", columns="Priority", values="Response Time")

plt.figure(figsize=(10, 6))

# Traccia la linea per High Priority (se presente)
if "high" in pivot_rt.columns:
    plt.plot(pivot_rt.index, pivot_rt["high"], marker="o", linestyle="-", label="High Priority")
# Traccia la linea per Low Priority (se presente)
if "how" in pivot_rt.columns:
    plt.plot(pivot_rt.index, pivot_rt["low"], marker="o", linestyle="-", label="Low Priority")

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("Response Time (sec)", fontsize=14)
#plt.title("Average Response Time vs Arrival Rate (Service Time = 10)", fontsize=16)
#plt.yticks([0,10, 20, 30, 40, 50, 60, 70])
plt.legend()
plt.grid(False)

# Imposta i tick dell'asse X in base ai valori unici di Arrival Rate ordinati
arrival_rates = sorted(df_rr["Arrival Rate"].unique())
plt.xticks(arrival_rates)

output_dir = os.path.join(current_directory, "single_plot")
os.makedirs(output_dir, exist_ok=True)
plt.savefig(os.path.join(output_dir, "response_time_vs_arrival_rate_avg.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 3b: Grafico - Average % Dropped Requests vs Arrival Rate (CPU_Timeout = 10)
###############################################
df_dr = df[df["CPU_Timeout"] == 10].copy()
df_grouped_dr = df_dr.groupby(["InvArrivalRate", "Priority"])["Exec_after_set"].mean().reset_index()
df_grouped_dr["Label"] = df_grouped_dr.apply(lambda row: ("DTS-TMAX Orbit-aware")
                                            + " - " + row["Priority"], axis=1)
pivot_dr = df_grouped_dr.pivot(index="InvArrivalRate", columns="Label", values="Exec_after_set")

inv_rates_dr = sorted(df_dr["InvArrivalRate"].unique())
print(inv_rates_dr)
mapping_dr = {val: i for i, val in enumerate(inv_rates_dr)}

plt.figure(figsize=(10, 6))
for col in pivot_dr.columns:
    #plt.plot(pivot_dr.index, pivot_dr[col], marker="o", linestyle="-", label=col)
    x_positions = [mapping_dr[val] for val in pivot_dr.index]
    print(col)
    if col == "DTS-TMAX Orbit-aware - High":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#1f77b4')
    if col == "DTS-TMAX Orbit-aware - Low":
        plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col, color='#ff7f0e')
    #plt.plot(x_positions, pivot_dr[col], marker="o", linestyle="-", label=col)

plt.xlabel("Arrival Rate (task/sec)", fontsize=14)
plt.ylabel("% Dropped Requests", fontsize=14)
#plt.title(" % Dropped Requests vs Arrival Rate (CPU_Timeout = 10)", fontsize=16)
#plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
plt.legend()
plt.grid(False)
#arrival_rates_dr = sorted(df_dr["InvArrivalRate"].unique())
#plt.xticks(arrival_rates_dr)
plt.xticks(range(len(inv_rates_dr)), inv_rates_dr)

plt.savefig(os.path.join(output_dir, "dropped_requests_vs_arrival_rate_avg.png"), dpi=300, bbox_inches='tight')
plt.show()

###############################################
# STEP 4: Funzione di plotting per gli altri grafici (Grafici 2-6)
###############################################
def plot_graph(x, y, xlabel, ylabel, filename, filter_dict=None):
    plt.figure(figsize=(10, 6))

    # Filtra i dati se necessario
    df_filtered = df.copy()
    if filter_dict:
        for key, value in filter_dict.items():
            if isinstance(value, list):
                df_filtered = df_filtered[df_filtered[key].isin(value)]
            else:
                df_filtered = df_filtered[df_filtered[key] == value]

    # Se x è "AP", assicurati di avere solo i valori 5,10,15,20
    if x == "AP":
        df_filtered[x] = pd.to_numeric(df_filtered[x], errors='coerce')
        df_filtered = df_filtered[df_filtered[x].isin([5, 10, 15, 20])]
    if x == "CPU_Timeout":
        df_filtered = df_filtered.sort_values(by=x)
    # Plot per ciascuna priorità e per ogni Arrival Rate
    for priority in ["high", "low"]:
        df_priority = df_filtered[df_filtered["Priority"] == priority]
        print(df_priority)
        for rate in sorted(df_priority["Arrival Rate"].unique()):
            print(rate)
            subset = df_priority[df_priority["Arrival Rate"] == rate]
            # Se x è AP, ordina il subset per AP
            if x == "AP":
                subset = subset.sort_values(by=x)
            plt.plot(subset[x], subset[y], marker="o", linestyle="-",
                     label=f"{priority} Priority - Arrival Rate {rate}")

    plt.xlabel(xlabel, fontsize=14)
    if ylabel == "Response Time (sec)":
        plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    '''else:
        plt.yticks([0, 0.10, 0.20, 0.30, 0.40, 0.50])'''
    plt.ylabel(ylabel, fontsize=14)
    #plt.title(title, fontsize=16)

    plt.legend()
    plt.grid(False)  # Rimuove la griglia

    # Forza i tick dell'asse X se x è "AP" o "CPU_Timeout"
    if x == "AP":
        plt.xticks([5, 10, 15, 20])
    if x == "CPU_Timeout":
        plt.xticks([10, 30, 50, 70, 90, 110])

    # Salva il grafico
    output_dir = os.path.join(current_directory, "single_plot")
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.show()


###############################################
# STEP 5: Grafici 2-6
###############################################
# Grafico 2: Response Time vs AP (CPU_Timeout = 10, task/sec = 1)
plot_graph(
    x="AP", y="Response Time",
    xlabel="AP", ylabel="Response Time (sec)",
    filename="response_time_vs_AP.png",
    filter_dict={"CPU_Timeout": 10, "Arrival Rate": 2, "AP": [5, 10, 15, 20]}
)

# Grafico 3: Response Time vs CPU_Timeout (Task/sec = 1, AP = 5)
plot_graph(
    x="CPU_Timeout", y="Response Time",
    xlabel="Service Time", ylabel="Response Time (sec)",
    filename="response_time_vs_service_time.png",
    filter_dict={"AP": 5, "Arrival Rate": 2, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)


# Grafico 5: % Dropped Requests vs AP (CPU_Timeout = 10, task/sec = 1)
plot_graph(
    x="AP", y="Exec_after_set",
    xlabel="AP", ylabel="% Dropped Requests",
    filename="dropped_requests_vs_AP.png",
    filter_dict={"CPU_Timeout": 10, "Arrival Rate": 2, "AP": [5, 10, 15, 20]}
)

# Grafico 6: % Dropped Requests vs CPU_Timeout (Task/sec = 1, AP = 5)
plot_graph(
    x="CPU_Timeout", y="Exec_after_set",
    xlabel="Service Time", ylabel="% Dropped Requests",
    filename="dropped_requests_vs_service_time.png",
    filter_dict={"AP": 5, "Arrival Rate": 2, "CPU_Timeout": [10, 30, 50, 70, 90, 110]}
)
