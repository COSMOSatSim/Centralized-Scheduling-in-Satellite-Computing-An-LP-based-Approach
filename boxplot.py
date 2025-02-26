import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            subdirectory = os.path.join(root, dir_name)
            if not dir_name.endswith("plots") :  # Escludere la cartella "plots"
                process_subdirectory(subdirectory)
                #print(subdirectory)

def process_subdirectory(subdirectory):
    dati_finali_alta_priorita = pd.DataFrame()
    dati_finali_bassa_priorita = pd.DataFrame()

    for filename in os.listdir(subdirectory):
        if filename.startswith("merged_processed_files_") and not filename.endswith("plots"):
            print('elaborazione del file: ',filename )
            file_path = os.path.join(subdirectory, filename)
            AP = file_path.split('\\')[5].split("_")[-1][2:]
            print('AP',AP)
            arrival_time = file_path.split("_")[-3].replace('.csv', '')
            print('AR',arrival_time)
            CPU_Timeout = file_path.split("_")[-1].replace('.csv', '')
            #print('CPU',CPU_Timeout)
            request_distribution = file_path.split("\\")[6].split('result_')[1].split('_request_distribution')[0]
            typology = file_path.split("\\")[6].split('_')[-1]
            priority_combination = file_path.split("\\")[7].split('Merged_priority_')[1]

            dati = pd.read_csv(file_path)

            dati_alta_priority = dati[dati['Task Priority'] == 'high']
            dati_selezionati_alta_priorita = dati_alta_priority[["Queue length", "Time in queue", "Time in system", "Server Name"]].copy()
            dati_selezionati_alta_priorita["Arrival Rate"] = arrival_time
            #dati_selezionati_alta_priorita["CPU_Timeout"] = CPU_Timeout
            dati_selezionati_alta_priorita.rename(columns={"Time in system": "Response Time"}, inplace=True)
            dati_finali_alta_priorita = pd.concat([dati_finali_alta_priorita, dati_selezionati_alta_priorita], ignore_index=True)

            dati_bassa_priority = dati[dati['Task Priority'] == 'low']
            dati_selezionati_bassa_priorita = dati_bassa_priority[["Queue length", "Time in queue", "Time in system", "Server Name"]].copy()
            dati_selezionati_bassa_priorita["Arrival Rate"] = arrival_time
            #dati_selezionati_bassa_priorita["CPU_Timeout"] = CPU_Timeout
            dati_selezionati_bassa_priorita.rename(columns={"Time in system": "Response Time"}, inplace=True)
            dati_finali_bassa_priorita = pd.concat([dati_finali_bassa_priorita, dati_selezionati_bassa_priorita], ignore_index=True)
            print(dati_finali_bassa_priorita)

            save_boxplots(subdirectory, dati_finali_alta_priorita, "High", request_distribution,typology,priority_combination, AP )
            save_boxplots(subdirectory, dati_finali_bassa_priorita, "Low", request_distribution,typology,priority_combination, AP )


def save_boxplots(subdirectory, data_frame, priority, request_distribution, typology, priority_combination, AP):
    print("Save BoxPlot")
    figure_count = 0

    # Check if the DataFrame is empty to avoid plotting errors.
    if data_frame.empty:
        print(f"No data available for {priority} priority. Skipping boxplot creation.")
        return

    # Dictionary for storing boxplot data
    boxplot_data = {'Priority': [], 'Request Distribution': [], 'Typology': [], 'Priority Combination': [],
                    'Arrival Rate': [], 'Mean': [], '25': [], '75': [], 'AP': []}

    for column in data_frame.columns:
        print(column)
        if column == "Response Time":  # Only calculate for Response Time
            # Calculate the boxplot statistics grouped by "Arrival Rate"
            boxplot_values = data_frame.groupby("Arrival Rate")[column].describe(percentiles=[0.25, 0.75])

            # If grouping yields no results, skip plotting for this column
            if boxplot_values.empty:
                print(f"No groups found for {column} based on 'Arrival Rate'. Skipping.")
                continue

            # Add calculated values to the dictionary
            boxplot_data['Priority'].extend([priority] * len(boxplot_values))
            boxplot_data['Request Distribution'].extend([request_distribution] * len(boxplot_values))
            boxplot_data['Typology'].extend([typology] * len(boxplot_values))
            boxplot_data['Priority Combination'].extend([priority_combination] * len(boxplot_values))
            boxplot_data['AP'].extend([AP] * len(boxplot_values))
            #boxplot_data['CPU_Timeout'].extend([CPU_Timeout] * len(boxplot_values))
            boxplot_data['Arrival Rate'].extend(boxplot_values.index.tolist())
            boxplot_data['Mean'].extend(boxplot_values['mean'].tolist())
            boxplot_data['25'].extend(boxplot_values['25%'].tolist())
            boxplot_data['75'].extend(boxplot_values['75%'].tolist())

            if figure_count >= 1:
                plt.close('all')
                figure_count = 0

            plt.figure(figsize=(10, 6))
            data_frame.boxplot(column, by="Arrival Rate", showfliers=False, grid=False, patch_artist=False)
            plt.xlabel("Arrival Rate (req/sec)")
            plt.ylabel(f"{column} (sec.)")
            plt.title('')
            plt.suptitle('')
            # Special tick adjustment condition
            if column == "Response Time" and priority == "High":
                if (
                "OK_simulation result-open-System 9edge\\simulation result_33_33_33_request_distribution_latency_7_centralized\\Merged_priority_20_0_80") in subdirectory:
                    plt.yticks([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
            plots_directory = os.path.join(subdirectory, 'Boxplots')
            os.makedirs(plots_directory, exist_ok=True)
            plt.savefig(os.path.join(plots_directory, f"BoxPlot_{column}_{priority}_priority.png"))
            plt.close()
            figure_count += 1

    # Save the boxplot statistics to a CSV file
    boxplot_df = pd.DataFrame(boxplot_data)
    boxplot_csv_path = os.path.join(subdirectory, f"boxplot_data_{priority}_priority.csv")
    boxplot_df.to_csv(boxplot_csv_path, index=False)


# Ottieni il percorso della directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Cerca tutte le cartelle nella directory corrente
for folder_name in os.listdir(current_directory):
    folder_path = os.path.join(current_directory, folder_name)
    if os.path.isdir(folder_path) and not folder_name.startswith(".idea")and not folder_name.startswith(".git"): # or folder_name.startswith("simulation result-close"):
        # Esegui il processo sulla directory specificata
        process_directory(folder_path)

