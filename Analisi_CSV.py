import os
import numpy as np
import pandas as pd


def process_directory(directory, global_output_directory):
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.endswith("plots") and d != "CSV_Aggregates"]
        for dir_name in dirs:
            subdirectory = os.path.join(root, dir_name)
            process_subdirectory(subdirectory, global_output_directory)


def process_subdirectory(subdirectory, global_output_directory):
    for filename in os.listdir(subdirectory):
        if filename.startswith("merged_processed_files_") and not filename.endswith("plots"):
            print('Elaborazione del file:', filename)
            file_path = os.path.join(subdirectory, filename)

            try:
                AP = file_path.split('\\')[5].split("_")[-1][2:]
            except IndexError:
                AP = "NA"
            arrival_time = file_path.split("_")[-3].replace('.csv', '')
            CPU_Timeout = file_path.split("_")[-1].replace('.csv', '')

            dati = pd.read_csv(file_path)

            save_aggregated_data(dati, "high", file_path, global_output_directory, AP, arrival_time, CPU_Timeout)
            save_aggregated_data(dati, "low", file_path, global_output_directory, AP, arrival_time, CPU_Timeout)


def save_aggregated_data(dati, priority, file_path, output_directory, AP, arrival_time, CPU_Timeout):
    dati_priority = dati[dati['Task Priority'] == priority].copy()  # Copia per evitare SettingWithCopyWarning
    if dati_priority.empty:
        return

    # Assicuriamoci che "Time in system" sia sempre >= "Execution time"
    dati_priority["Time in system"] = np.maximum(dati_priority["Time in system"], dati_priority["Execution time"])

    nonzero_times = dati_priority["Execution time"][dati_priority["Execution time"] > 0]
    mean_exec_time = nonzero_times.mean() if not nonzero_times.empty else 0

    nonzero_times_system = dati_priority["Time in system"][dati_priority["Time in system"] > 0]
    mean_time_in_system = nonzero_times_system.mean()

    percent_tmax_exceeded = (dati_priority['TMAX_exceeded'].sum() / len(dati_priority) * 100) if len(dati_priority) > 0 else 0
    percent_exec_after_set = (dati_priority['Exec_after_set'].sum() / len(dati_priority) * 100) if len(dati_priority) > 0 else 0

    aggregated_data = pd.DataFrame({
        "Priority": [priority],
        "AP": [AP],
        "CPU_Timeout": [CPU_Timeout],
        "Arrival Rate": [arrival_time],
        "Execution time": [mean_exec_time],
        "Response Time": [mean_time_in_system],
        "TMAX_exceeded": [percent_tmax_exceeded],
        "Exec_after_set": [percent_exec_after_set]
    })

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(output_directory, f"aggregated_data_{priority}_priority_{base_name}.csv")
    aggregated_data.to_csv(output_file, index=False)
    print(f"Dati aggregati salvati in: {output_file}")


def merge_csv_files(root_directory, output_file_high, output_file_low):
    df_high, df_low = [], []

    for filename in os.listdir(root_directory):
        file_path = os.path.join(root_directory, filename)
        if filename.startswith("aggregated_data_high_priority"):
            df_high.append(pd.read_csv(file_path))
        elif filename.startswith("aggregated_data_low_priority"):
            df_low.append(pd.read_csv(file_path))

    if df_high:
        pd.concat(df_high, ignore_index=True).to_csv(output_file_high, index=False)
    if df_low:
        pd.concat(df_low, ignore_index=True).to_csv(output_file_low, index=False)


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
    remove_aggregated_files(global_output_directory)
    os.rmdir(global_output_directory)
