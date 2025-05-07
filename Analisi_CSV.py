import os
import numpy as np
import pandas as pd


'''def process_directory(directory, global_output_directory):
    for root, dirs, files in os.walk(directory):
        # escludo le cartelle plots e CSV_Aggregates
        dirs[:] = [d for d in dirs if not d.endswith("plots") and d != "CSV_Aggregates"]
        for dir_name in dirs:
            subdirectory = os.path.join(root, dir_name)

            if dir_name.startswith("DTS-simulation"):
                versione = "DTS"
            elif dir_name.startswith("Orbit-simulation"):
                versione = "Orbit-simulation"
            else:
                continue

            print(f"Elaborazione simulazione: {versione} in {subdirectory}")
            process_subdirectory(subdirectory, global_output_directory, versione)'''

def process_directory(directory, global_output_directory):
    for root, dirs, files in os.walk(directory):
        # Escludo le cartelle inutili
        dirs[:] = [d for d in dirs if not d.endswith("plots") and d != "CSV_Aggregates"]
        for dir_name in dirs:
            if dir_name.startswith("DTS-simulation"):
                versione = "DTS-simulation"
            elif dir_name.startswith("Orbit-simulation"):
                versione = "Orbit-simulation"
            else:
                continue

            subdirectory = os.path.join(root, dir_name)
            print(f"Elaborazione simulazione: {versione} in {subdirectory}")
            # Qui passo la cartella intera: process_subdirectory la camminerà tutta
            process_subdirectory(subdirectory, global_output_directory, versione)


def process_subdirectory(base_dir, global_output_directory, versione):
    # cammino ricorsivamente TUTTO il sotto-albero di base_dir
    for root, dirs, files in os.walk(base_dir):
        # (se vuoi escludere altre sottocartelle, qui puoi filtrare dirs[:] come in process_directory)
        for filename in files:
            if filename.startswith("merged_processed_files_") and not filename.endswith("plots"):
                print(f"  -> file: {os.path.join(root, filename)}")
                file_path = os.path.join(root, filename)

                # Estrazione variabili dal nome
                try:
                    AP = file_path.split(os.sep)[5].split("_")[-1][2:]
                except Exception:
                    AP = "NA"
                arrival_time = filename.split("_")[-3]
                CPU_Timeout  = filename.split("_")[-1].replace('.csv', '')

                dati = pd.read_csv(file_path)

                # Per ogni priorità faccio le due chiamate
                for priority in ("high", "low"):
                    ph, pl = save_priority_change_data(
                        dati, priority, file_path, global_output_directory,
                        AP, arrival_time, CPU_Timeout, versione
                    )
                    save_aggregated_data(
                        dati, priority, file_path, global_output_directory,
                        AP, arrival_time, CPU_Timeout, versione,
                        ph, pl
                    )
'''

def process_subdirectory(subdirectory, global_output_directory, versione):
    for filename in os.listdir(subdirectory):
        print(filename)
        if filename.startswith("merged_processed_files_") and not filename.endswith("plots"):
            print('qui')
            print('Elaborazione del file:', filename)
            file_path = os.path.join(subdirectory, filename)

            try:
                AP = file_path.split('\\')[5].split("_")[-1][2:]
            except IndexError:
                AP = "NA"
            arrival_time = file_path.split("_")[-3].replace('.csv', '')
            CPU_Timeout = file_path.split("_")[-1].replace('.csv', '')

            dati = pd.read_csv(file_path)

            # Per ogni priorità, calcolo le percentuali e salvo i CSV aggregati con queste colonne
            for priority in ("high", "low"):
                percent_high_changed, percent_low_changed = save_priority_change_data(
                    dati, priority, file_path, global_output_directory, AP, arrival_time, CPU_Timeout, versione)
                save_aggregated_data(dati, priority, file_path, global_output_directory,
                                     AP, arrival_time, CPU_Timeout, versione, percent_high_changed, percent_low_changed)
'''

def save_priority_change_data(dati, priority, file_path, output_directory, AP, arrival_time, CPU_Timeout, versione):
    print(versione)
    dati_priority = dati[dati['Task Priority'] == priority].copy()
    if dati_priority.empty:
        return 0.0, 0.0

    columns_swapped_applied = False
    if 'columns_swapped' in dati_priority.columns and dati_priority['columns_swapped'].any():
        print(f"Attenzione: columns_swapped = True in {file_path}, invertiamo temporaneamente i valori.")
        dati_priority[['Task Priority', 'original_TaskPriority']] = dati_priority[['original_TaskPriority', 'Task Priority']]
        columns_swapped_applied = True

    # Response Time minimo
    dati_priority["Time in system"] = np.maximum(dati_priority["Time in system"], dati_priority["Execution time"])

    # Calcolo percentuali di cambiamento
    total_original_high = dati_priority[dati_priority['original_TaskPriority'] == 'high']
    total_original_low  = dati_priority[dati_priority['original_TaskPriority'] == 'low']

    if not total_original_high.empty:
        high_changed = (total_original_high['original_TaskPriority'] != total_original_high['Task Priority']).sum()
        percent_high_changed = (high_changed / len(total_original_high)) * 100
    else:
        percent_high_changed = 0.0

    if not total_original_low.empty:
        low_changed = (total_original_low['original_TaskPriority'] != total_original_low['Task Priority']).sum()
        percent_low_changed = (low_changed / len(total_original_low)) * 100
    else:
        percent_low_changed = 0.0

    if columns_swapped_applied:
        dati_priority[['Task Priority', 'original_TaskPriority']] = dati_priority[['original_TaskPriority', 'Task Priority']]
        print(f"Valori ripristinati allo stato originale per {file_path}.")

    # Salvo comunque un CSV separato (opzionale)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(
        output_directory,
        f"{versione} priority_change_data_{priority}_priority_{base_name}_AP_{AP}.csv"
    )
    pd.DataFrame({
        "Task Priority": [priority],
        "AP": [AP],
        "CPU_Timeout": [CPU_Timeout],
        "Arrival Rate": [arrival_time],
        "Percent_High_Changed": [percent_high_changed],
        "Percent_Low_Changed":  [percent_low_changed]
    }).to_csv(output_file, index=False)
    print(f"Dati sui cambiamenti di priorità salvati in: {output_file}")

    return percent_high_changed, percent_low_changed


def save_aggregated_data(dati, priority, file_path, output_directory, AP, arrival_rate, CPU_Timeout, versione,
                         percent_high_changed=0.0, percent_low_changed=0.0):
    dati_priority = dati[dati['Task Priority'] == priority].copy()
    if dati_priority.empty:
        return

    # Time in system minimo rispetto a Execution time
    dati_priority["Time in system"] = np.maximum(
        dati_priority["Time in system"], dati_priority["Execution time"]
    )

    # Metriche di Response Time
    nonzero_times = dati_priority["Time in system"][dati_priority["Time in system"] > 0]
    mean_time_in_system = nonzero_times.mean() if not nonzero_times.empty else 0
    pct95_time_in_system = dati_priority["Time in system"].quantile(0.95)

    # Percentuali
    total = len(dati_priority)
    percent_tmax_exceeded = (dati_priority['TMAX_exceeded'].sum() / total * 100) if total > 0 else 0
    percent_exec_after_set = (dati_priority['Exec_after_set'].sum() / total * 100) if total > 0 else 0

    # Drop e medie stimate
    executed_tasks = dati_priority[dati_priority["Execution time"] > 0]
    dropped_tasks  = dati_priority[dati_priority["Execution time"] == 0]
    drop_count_executed = len(executed_tasks)
    drop_count = len(dropped_tasks)
    drop_rel = (drop_count / drop_count_executed) if drop_count_executed > 0 else 0

    mean_est_exec_executed = executed_tasks["estimated_execution_time"].mean() if not executed_tasks.empty else 0
    mean_est_exec_dropped  = dropped_tasks["estimated_execution_time"].mean() if not dropped_tasks.empty else 0
    mean_exec_time = executed_tasks["Execution time"].mean() if not executed_tasks.empty else 0

    # DataFrame con tutte le colonne, incluse Percent_High_Changed / Percent_Low_Changed
    aggregated_data = pd.DataFrame({
        "Priority": [priority],
        "AP": [AP],
        "CPU_Timeout": [CPU_Timeout],
        "Arrival Rate": [arrival_rate],
        "Execution time": [mean_exec_time],
        "estimated_execution_time_executed": [mean_est_exec_executed],
        "estimated_execution_time_dropped": [mean_est_exec_dropped],
        "Response Time": [mean_time_in_system],
        "RT_95th": [pct95_time_in_system],
        "TMAX_exceeded": [percent_tmax_exceeded],
        "Exec_after_set": [percent_exec_after_set],
        "drop_rel": [drop_rel],
        "Percent_High_Changed": [percent_high_changed],
        "Percent_Low_Changed": [percent_low_changed]
    })

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(
        output_directory,
        f"{versione} aggregated_data_{priority}_priority_{base_name}_AP_{AP}.csv"
    )
    aggregated_data.to_csv(output_file, index=False)
    print(f"Dati aggregati salvati in: {output_file}")


def merge_priority_change_files(root_directory, output_file):
    df_list = []
    for filename in os.listdir(root_directory):
        if filename.startswith("priority_change_data_"):
            df_list.append(pd.read_csv(os.path.join(root_directory, filename)))
    if df_list:
        pd.concat(df_list, ignore_index=True).to_csv(output_file, index=False)


'''def merge_csv_files(root_directory, output_file_high, output_file_low):
    df_high, df_low = [], []
    for filename in os.listdir(root_directory):
        if filename.startswith("aggregated_data_high_priority"):
            df_high.append(pd.read_csv(os.path.join(root_directory, filename)))
        elif filename.startswith("aggregated_data_low_priority"):
            df_low.append(pd.read_csv(os.path.join(root_directory, filename)))
    if df_high:
        pd.concat(df_high, ignore_index=True).to_csv(output_file_high, index=False)
    if df_low:
        pd.concat(df_low, ignore_index=True).to_csv(output_file_low, index=False)'''

def merge_csv_files(root_directory, output_file_high, output_file_low):
    """
    Unisce in due file (high/low) tutti i `aggregated_data_*` prodotti
    da DTS-simulation e Orbit-simulation, aggiungendo colonna Simulation.
    """
    dfs = {'high': [], 'low': []}

    for fname in os.listdir(root_directory):
        # match dei file prodotti prima da save_aggregated_data
        if fname.startswith(("DTS-simulation aggregated_data_", "Orbit-simulation aggregated_data_")):
            full_path = os.path.join(root_directory, fname)
            df = pd.read_csv(full_path)

            # ricavo la versione da fname
            sim = "DTS" if fname.startswith("DTS-simulation") else "Orbit"
            df['Simulation'] = sim

            # ricavo la priorità
            if "high_priority" in fname:
                dfs['high'].append(df)
            elif "low_priority" in fname:
                dfs['low'].append(df)

    # concat e salvataggio High
    if dfs['high']:
        combined_high = pd.concat(dfs['high'], ignore_index=True)
        combined_high.to_csv(output_file_high, index=False)
        print(f"Creato: {output_file_high}")

    # concat e salvataggio Low
    if dfs['low']:
        combined_low = pd.concat(dfs['low'], ignore_index=True)
        combined_low.to_csv(output_file_low, index=False)
        print(f"Creato: {output_file_low}")


def remove_aggregated_files(directory):
    for filename in os.listdir(directory):
        if filename.startswith("aggregated_data_"):
            os.remove(os.path.join(directory, filename))


if __name__ == "__main__":
    current_directory = os.path.dirname(os.path.abspath(__file__))
    global_output_directory = os.path.join(current_directory, "CSV_Aggregates")
    os.makedirs(global_output_directory, exist_ok=True)

    process_directory(current_directory, global_output_directory)
    merge_csv_files(global_output_directory, "data_High_priority.csv", "data_Low_priority.csv")
    merge_priority_change_files(global_output_directory, "priority_change_data.csv")
    remove_aggregated_files(global_output_directory)
    # os.rmdir(global_output_directory)
