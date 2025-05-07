import os
import pandas as pd
import csv_filter

pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.expand_frame_repr', False)  # Do not wrap rows


def remove_processed_files(folder_path):
    # Scansiona tutte le cartelle e sottocartelle alla ricerca di file con la dicitura "processed"
    processed_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(folder_path)
        for file in files
        if "processed" in file and "merged_processed_files" not in file
    ]

    # Rimuovi tutti i file con la dicitura "processed"
    for processed_file in processed_files:
        os.remove(processed_file)
        print(f"Removed obsolete processed file: {processed_file}")


def process_csv(file_path):
    # Estrai il suffisso del file (es. "0.1" da "simulation_results_10_30_60_exponential_42_0.2_processed_0.1.csv")
    file_suffix = os.path.splitext(os.path.basename(file_path))[0].split('_')[-3]

    # Estrai la combinazione di priorità e il valore della CPU
    CPU_combination = os.path.splitext(os.path.basename(file_path))[0].split('_')[-1]
    #priority_combination = '20_0_80'

    # Escludi i file che contengono la dicitura "processed" nel nome
    if "processed" in os.path.basename(file_path):
        return None, None, None, None

    # Leggi il file CSV
    df = pd.read_csv(file_path)
    required_columns = ['TMAX_exceeded', 'Arrival time in system']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Colonna mancante {col} nel file {file_path}")

    # Ordina il DataFrame in base alla colonna "Arrival time in system"
    df = df.sort_values(by="Arrival time in system")

    if 'TMAX_exceeded' not in df.columns:
        raise ValueError("Colonna TMAX_exceeded non trovata nel CSV")

    # Filtra le righe dove il valore della colonna 'TMAX_exceeded' è True
    righe_da_salvare = df[df['TMAX_exceeded'] == True]

    # Se ci sono righe da salvare, rimuovile dal DataFrame originale
    if not righe_da_salvare.empty:
        df = df[df['TMAX_exceeded'] == False]
        # Sovrascrivi il file originale con le righe rimosse
        #df.to_csv(file_path, index=False)
    else:
        print(f"Nessuna riga da salvare trovata per il file {file_path}")

    # Rinomina il file aggiungendo un suffisso e la combinazione di priorità
    base_name = os.path.basename(file_path)
    file_name, _ = os.path.splitext(base_name)
    new_file_name = f"{file_name}_processed.csv"

    # Salva il DataFrame nel nuovo file CSV
    output_path = os.path.join(os.path.dirname(file_path), new_file_name)
    df.to_csv(output_path, index=False, mode='w')
    print(f"Processed: {file_path, base_name} -> {new_file_name}")

    return pd.read_csv(output_path), file_suffix, CPU_combination


def process_all_csv_files(folder_path):
    # Rimuovi tutti i file con la dicitura "processed" prima di procedere
    remove_processed_files(folder_path)

    # Scansiona tutte le cartelle e sottocartelle alla ricerca di file CSV
    csv_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(folder_path)
        for file in files
        if file.endswith(".csv") and not file.startswith("merged_processed_files")
           and not file.startswith("boxplot_data") and not file.startswith("server_name_")
           and "statistiche" not in file
    ]

    total_files = len(csv_files)
    processed_files_count = 0
    grouped_dataframes = {}

    # Processa ogni file CSV
    for file_path in csv_files:
        inverti_colonne_csv(file_path, "Task Priority", "original_TaskPriority", file_path)

        processed_df, file_suffix, CPU = process_csv(file_path)
        # Rimuovo la stampa del DataFrame: non viene più visualizzato il contenuto
        # print(processed_df, priority_combination, file_suffix, CPU)

        if processed_df is not None  and file_suffix is not None:
            group_key = (file_suffix, CPU)
            if group_key not in grouped_dataframes:
                grouped_dataframes[group_key] = pd.DataFrame()
            grouped_dataframes[group_key] = pd.concat([grouped_dataframes[group_key], processed_df])

            processed_files_count += 1
            progress_percentage = (processed_files_count / total_files) * 100
            print(f"Processing CSV Files: {progress_percentage:.2f}% ({processed_files_count}/{total_files} files processed)")

    # Salva i DataFrame raggruppati in file CSV separati
    for (file_suffix, CPU) in grouped_dataframes:
        priority_folder_path = os.path.join(folder_path, f"Merged_priority")
        os.makedirs(priority_folder_path, exist_ok=True)

        df = grouped_dataframes[(file_suffix, CPU)]
        output_file_name = f"merged_processed_files_AT_{file_suffix}_CPU_{CPU}.csv"
        merged_file_path = os.path.join(priority_folder_path, output_file_name)

        df.to_csv(merged_file_path, index=False, mode='w')
        print(f"\nMerged Processed Files: {merged_file_path}")

        remove_processed_files(folder_path)


current_directory = os.path.dirname(os.path.abspath(__file__))
exec("csv_filter")


def inverti_colonne_csv(file_input, colonna_1, colonna_2, file_output):
    """
    Inverte due colonne in un file CSV solo la prima volta.
    Aggiunge un flag 'columns_swapped' per evitare inversioni multiple.
    """
    try:
        df = pd.read_csv(file_input)

        # Controllo esistenza colonne
        if colonna_1 not in df.columns:
            raise ValueError(f"La colonna '{colonna_1}' non esiste nel file CSV.")
        if colonna_2 not in df.columns:
            print(f"Colonna '{colonna_2}' non trovata. Il file non verrà elaborato.")
            return

        # Se esiste già la colonna 'columns_swapped' e il valore è True, salta
        if 'columns_swapped' in df.columns and df['columns_swapped'].iloc[0] == True:
            print(f"Inversione già eseguita in precedenza su '{file_input}'. Salto.")
            return

        # Inversione delle colonne
        df[[colonna_1, colonna_2]] = df[[colonna_2, colonna_1]]

        # Aggiungi la colonna di flag
        df['columns_swapped'] = True

        # Salva
        df.to_csv(file_output, index=False)
        print(f"Invertite le colonne '{colonna_1}' e '{colonna_2}' in '{file_output}'. Flag aggiunto.")

    except Exception as e:
        print(f"Errore: {e}")


for folder_name in os.listdir(current_directory):
    folder_path = os.path.join(current_directory, folder_name)
    if os.path.isdir(folder_path) and not folder_name.startswith("Merged_priority"):
        print('folder path', folder_path)
        for subfolder_name in os.listdir(folder_path):
            subfolder_path = os.path.join(folder_path, subfolder_name)
            if os.path.isdir(subfolder_path):
                print('subfolder path', subfolder_path)
                process_all_csv_files(subfolder_path)
