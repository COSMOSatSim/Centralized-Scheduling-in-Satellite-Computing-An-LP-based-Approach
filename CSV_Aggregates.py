import os
import pandas as pd

# Definisci i valori di CPU che ti interessano
cpu_filter = {'10', '30', '50', '70', '90', '110'}

# Ottieni il percorso della directory corrente
current_directory = os.path.dirname(os.path.abspath(__file__))

# Lista per raccogliere i file CSV aggregati per alta e bassa priorità
high_files = []
low_files = []

# Cammina nella directory corrente e nelle sue sottocartelle per trovare le cartelle CSV_Aggregates
for root, dirs, files in os.walk(current_directory):
    # Considera solo le cartelle che si chiamano CSV_Aggregates
    if os.path.basename(root) == "CSV_Aggregates":
        for file in files:
            if file.startswith("aggregated_data_") and file.endswith(".csv"):
                # Il nome del file è nel formato:
                # aggregated_data_{Priority}_priority_CPU_{CPU_Timeout}.csv
                # Dividiamo il nome per estrarre Priority e CPU_Timeout
                parts = file.split("_")
                # Esempio: ["aggregated", "data", "High", "priority", "CPU", "10.csv"]
                if len(parts) >= 6:
                    priority_part = parts[2].lower()  # "high" o "low"
                    cpu_part = parts[-1].replace(".csv", "")  # es. "10"
                    if cpu_part in cpu_filter:
                        full_path = os.path.join(root, file)
                        if priority_part == "high":
                            high_files.append(full_path)
                        elif priority_part == "low":
                            low_files.append(full_path)

# Combina e salva i file per alta priorità
if high_files:
    df_high = pd.concat([pd.read_csv(f) for f in high_files], ignore_index=True)
    output_high = os.path.join(current_directory, "data_High_priority.csv")
    df_high.to_csv(output_high, index=False)
    print(f"File combinato per alta priorità salvato in: {output_high}")
else:
    print("Nessun file trovato per alta priorità con CPU 10, 50 o 110.")

# Combina e salva i file per bassa priorità
if low_files:
    df_low = pd.concat([pd.read_csv(f) for f in low_files], ignore_index=True)
    output_low = os.path.join(current_directory, "data_Low_priority.csv")
    df_low.to_csv(output_low, index=False)
    print(f"File combinato per bassa priorità salvato in: {output_low}")
else:
    print("Nessun file trovato per bassa priorità con CPU 10, 50 o 110.")
