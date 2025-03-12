import os
import numpy as np
import pandas as pd


def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            subdirectory = os.path.join(root, dir_name)
            if not dir_name.endswith("plots"):  # Escludere la cartella "plots"
                process_subdirectory(subdirectory)


def process_subdirectory(subdirectory):
    dati_finali_alta_priorita = pd.DataFrame()
    dati_finali_bassa_priorita = pd.DataFrame()

    for filename in os.listdir(subdirectory):
        if filename.startswith("merged_processed_files_") and not filename.endswith("plots"):
            print('Elaborazione del file:', filename)
            file_path = os.path.join(subdirectory, filename)
            AP = file_path.split('\\')[5].split("_")[-1][2:]
            print('AP:', AP)
            arrival_time = file_path.split("_")[-3].replace('.csv', '')
            print('Arrival Rate:', arrival_time)
            CPU_Timeout = file_path.split("_")[-1].replace('.csv', '')
            print('CPU Timeout:', CPU_Timeout)

            dati = pd.read_csv(file_path)

            # Elaborazione per alta priorità
            dati_alta_priority = dati[dati['Task Priority'] == 'high']
            dati_selezionati_alta_priorita = dati_alta_priority[
                ["Time in system", "Server Name", "Execution time", "TMAX_exceeded", "Exec_after_set"]].copy()
            dati_selezionati_alta_priorita["Arrival Rate"] = arrival_time
            dati_selezionati_alta_priorita["CPU_Timeout"] = CPU_Timeout
            dati_selezionati_alta_priorita.rename(columns={"Time in system": "Response Time"}, inplace=True)
            dati_finali_alta_priorita = pd.concat(
                [dati_finali_alta_priorita, dati_selezionati_alta_priorita], ignore_index=True)

            # Elaborazione per bassa priorità
            dati_bassa_priority = dati[dati['Task Priority'] == 'low']
            dati_selezionati_bassa_priorita = dati_bassa_priority[
                ["Time in system", "Server Name", "Execution time", "TMAX_exceeded", "Exec_after_set"]].copy()
            dati_selezionati_bassa_priorita["Arrival Rate"] = arrival_time
            dati_selezionati_bassa_priorita["CPU_Timeout"] = CPU_Timeout
            dati_selezionati_bassa_priorita.rename(columns={"Time in system": "Response Time"}, inplace=True)
            dati_finali_bassa_priorita = pd.concat(
                [dati_finali_bassa_priorita, dati_selezionati_bassa_priorita], ignore_index=True)

            # Salva i file CSV aggregati per alta e bassa priorità
            save_csv_aggregated_data(subdirectory, dati_finali_alta_priorita, "High", AP, CPU_Timeout)
            save_csv_aggregated_data(subdirectory, dati_finali_bassa_priorita, "Low", AP, CPU_Timeout)


def save_csv_aggregated_data(subdirectory, data_frame, priority, AP, CPU_Timeout):
    print("Salvataggio dati CSV aggregati")
    if data_frame.empty:
        print(f"Nessun dato disponibile per la priorità {priority}. Salto il salvataggio.")
        return

    # Conversione dei dati in formato numerico
    data_frame["Response Time"] = pd.to_numeric(data_frame["Response Time"], errors="coerce")
    data_frame["Execution time"] = pd.to_numeric(data_frame["Execution time"], errors="coerce")

    # Conversione dei valori booleani se sono salvati come stringhe
    if data_frame["TMAX_exceeded"].dtype == object:
        # Assicuriamoci di gestire eventuali variazioni di maiuscole/minuscole
        data_frame["TMAX_exceeded"] = data_frame["TMAX_exceeded"].str.lower().map({"true": 1, "false": 0})
    if data_frame["Exec_after_set"].dtype == object:
        data_frame["Exec_after_set"] = data_frame["Exec_after_set"].str.lower().map({"true": 1, "false": 0})

    # Raggruppamento per "Arrival Rate" e calcolo delle medie
    grouped = data_frame.groupby("Arrival Rate").agg({
        "Response Time": "mean",
        "Execution time": "mean",
        "TMAX_exceeded": "mean",
        "Exec_after_set": "mean"
    }).reset_index()

    # Aggiungi le colonne di contesto
    grouped["Priority"] = priority
    grouped["AP"] = AP
    grouped["CPU_Timeout"] = CPU_Timeout

    # Riordina le colonne
    grouped = grouped[
        ["Priority", "AP", "CPU_Timeout", "Arrival Rate", "Response Time", "Execution time", "TMAX_exceeded",
         "Exec_after_set"]]

    # Salva il file CSV in una cartella dedicata
    output_directory = os.path.join(subdirectory, 'CSV_Aggregates')
    os.makedirs(output_directory, exist_ok=True)
    csv_path = os.path.join(output_directory, f"aggregated_data_{priority}_priority_CPU_{CPU_Timeout}.csv")
    grouped.to_csv(csv_path, index=False)
    print(f"Dati aggregati salvati in: {csv_path}")


# Ottieni il percorso della directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Elabora tutte le cartelle nella directory corrente
for folder_name in os.listdir(current_directory):
    folder_path = os.path.join(current_directory, folder_name)
    if os.path.isdir(folder_path) and not folder_name.startswith(".idea") and not folder_name.startswith(
            ".git") and not folder_name.startswith("CPU 10_ AT ALL_senza controllo orbita"):
        process_directory(folder_path)
