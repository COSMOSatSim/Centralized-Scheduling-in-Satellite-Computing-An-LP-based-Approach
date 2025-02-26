import os
import time
import csv
import pandas as pd

current_directory = os.path.dirname(os.path.abspath(__file__))


def stampa_statistiche(df, output_name):
    """
    Calcola alcune statistiche sul DataFrame e salva i risultati sia in un file di testo
    che in un CSV.
    """
    csv_directory = os.path.join(current_directory, 'Tmax result', 'statistic')
    os.makedirs(csv_directory, exist_ok=True)

    # Statistiche sui task
    numero_totale_task = len(df)
    numero_task_scartati = len(df[df['TMAX_exceeded'] == True])
    percentuale_task_scartati_totale = (numero_task_scartati / numero_totale_task) * 100

    # Statistiche su 'Num Hops'
    statistiche_num_hops_totale = df['Num Hops'].describe()
    gruppi_priorita = df.groupby('Task Priority')
    statistiche_num_hops_per_priorita = gruppi_priorita['Num Hops'].describe()
    statistiche_per_priorita = gruppi_priorita['TMAX_exceeded'].apply(lambda x: (x.sum() / len(x)) * 100)

    # Statistiche raggruppate per priorità e server
    gruppi_priorita_server = df.groupby(['Task Priority', 'Server Name'])
    num_richieste_servite_per_server = gruppi_priorita_server['TMAX_exceeded'].apply(lambda x: (x == False).sum())
    num_richieste_arrivate_totale_per_server = gruppi_priorita_server['Server Name'].count()

    # Statistiche per richieste ad alta priorità
    num_richieste_high = len(df[df['Task Priority'] == 'high'])
    num_richieste_high_time_exceeded = len(df[(df['Task Priority'] == 'high') & (df['Time in system'] > 0.5)])
    if num_richieste_high != 0:
        percentuale_richieste_high_time_exceeded = (num_richieste_high_time_exceeded / num_richieste_high) * 100
    else:
        percentuale_richieste_high_time_exceeded = 0

    # Scrittura dei risultati in un file di testo
    file_output_txt = os.path.join(csv_directory, f"statistiche_{output_name}.txt")
    with open(file_output_txt, mode='w') as f:
        f.write("Percentuale di task scartati (totale): {:.2f}%\n\n".format(percentuale_task_scartati_totale))
        f.write("Statistiche per ogni server e priorità:\n")
        f.write("Percentuale di task scartati per priorità:\n")
        for priorita, percentuale in statistiche_per_priorita.items():
            f.write(f" - {priorita}: {percentuale:.2f}%\n")
        f.write("\nStatistiche sui 'Num Hops' (totale):\n")
        f.write(str(statistiche_num_hops_totale) + "\n")
        f.write("\nStatistiche sui 'Num Hops' per priorità:\n")
        f.write(str(statistiche_num_hops_per_priorita) + "\n")
        f.write(
            "\nPercentuale di richieste ad alta priorità che hanno superato il valore di 'Time in system' di 0.5: {:.2f}%\n".format(
                percentuale_richieste_high_time_exceeded))

    '''# Stampa a video
    print("Percentuale di task scartati (totale): {:.2f}%".format(percentuale_task_scartati_totale))
    print("\nStatistiche per ogni server e priorità:")
    for priorita, percentuale in statistiche_per_priorita.items():
        print(f" - {priorita}: {percentuale:.2f}%")
    print("\nStatistiche sui 'Num Hops' (totale):")
    print(statistiche_num_hops_totale)
    print("\nStatistiche sui 'Num Hops' per priorità:")
    print(statistiche_num_hops_per_priorita)
    print(
        "\nPercentuale di richieste ad alta priorità che hanno superato il valore di 'Time in system' di 0.5: {:.2f}%".format(
            percentuale_richieste_high_time_exceeded))'''

    # Salva anche le statistiche in un file CSV
    crea_file_csv(df, os.path.join(csv_directory, f"statistiche_{output_name}.csv"))


def crea_file_csv(df, file_path):
    """
    Crea un file CSV con alcune statistiche raggruppate per 'Server Name' e 'Task Priority'.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Server', 'Priorità', 'Numero di richieste arrivate',
                         'Numero di richieste servite', 'Numero di richieste scartate',
                         'Percentuale di richieste servite', 'Lunghezza media della coda'])

        gruppi_priorita_server = df.groupby(['Server Name', 'Task Priority'])
        num_richieste_arrivate_per_server = gruppi_priorita_server.size()
        num_richieste_servite_per_server = gruppi_priorita_server['TMAX_exceeded'].apply(lambda x: (x == False).sum())
        num_richieste_scartate_per_server = gruppi_priorita_server['TMAX_exceeded'].apply(lambda x: (x == True).sum())
        percentuale_richieste_servite_per_server = (num_richieste_servite_per_server / num_richieste_arrivate_per_server) * 100
        lunghezza_media_coda_per_server = gruppi_priorita_server['Queue length'].mean()

        for (server, priorita), num_richieste_arrivate in num_richieste_arrivate_per_server.items():
            num_richieste_servite = num_richieste_servite_per_server[server, priorita]
            num_richieste_scartate = num_richieste_scartate_per_server[server, priorita]
            percentuale_richieste_servite = percentuale_richieste_servite_per_server[server, priorita]
            lunghezza_media_coda = lunghezza_media_coda_per_server[server, priorita]
            writer.writerow([server, priorita, num_richieste_arrivate, num_richieste_servite,
                             num_richieste_scartate, percentuale_richieste_servite, lunghezza_media_coda])


def filtro_csv(folder_path):
    """
    Scansiona ricorsivamente la cartella folder_path per trovare file CSV e, per ciascuno,
    esegue operazioni di controllo e stampa statistiche.
    """
    csv_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(folder_path)
        for file in files
        if file.endswith(".csv") and not file.startswith("merged_processed_files")
           and not file.startswith("boxplot_data") and not file.startswith("server_name_")
           and not file.startswith("stats_by_arrival")
    ]

    csv_directory = os.path.join(current_directory, 'Tmax result')
    os.makedirs(csv_directory, exist_ok=True)

    for file_path in csv_files:
        print("Processing file:", file_path)
        filename = os.path.basename(file_path)
        parts = filename.split("_")
        if len(parts) < 2:
            print("Nome file non valido:", filename)
            continue

        # Il primo elemento viene considerato come AP; il resto viene usato per creare il nome filtrato
        AP = folder_path.split("\\")[5].split("_")[-1]
        filtered = "_".join(parts[1:])
        filtered_output = f"{AP}_tmax_{filtered}"
        print("Elaboro il file:", filtered_output)

        try:
            df = pd.read_csv(file_path, encoding='latin1')
        except Exception as e:
            print(f"Errore durante la lettura del file {file_path}: {e}")
            continue

        if 'TMAX_exceeded' not in df.columns:
            print(f"Attenzione: 'TMAX_exceeded' non trovato in {file_path}")
            continue

        # Chiamata alla funzione di statistiche
        stampa_statistiche(df, filtered_output)


print("Controllo se ci sono colonne da rimuovere da Tmax")
time.sleep(5)

# Scansiona le cartelle nella directory corrente (escludendo quelle che iniziano con "Merged_priority")
for folder_name in os.listdir(current_directory):
    folder_path = os.path.join(current_directory, folder_name)
    if os.path.isdir(folder_path) and not folder_name.startswith("Merged_priority"):
        print("Folder path:", folder_path)
        for subfolder_name in os.listdir(folder_path):
            subfolder_path = os.path.join(folder_path, subfolder_name)
            if os.path.isdir(subfolder_path):
                filtro_csv(subfolder_path)
