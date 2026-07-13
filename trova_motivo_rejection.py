import os
import csv
from collections import Counter

# Sostituisci con il nome della tua cartella se è diverso
root_folder = "results_esp_6"

# Inizializziamo il Counter per tenere traccia delle frequenze
rejection_counts = Counter()

print(f"Analisi della cartella '{root_folder}' in corso alla ricerca delle ragioni di rigetto...\n")

# Esplora tutte le cartelle e i file
for root, _, files in os.walk(root_folder):
    for file in files:
        if file.endswith(".csv") and "results" in file:
            filepath = os.path.join(root, file)
            
            try:
                with open(filepath, newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for line in reader:
                        # Controlliamo che la riga abbia abbastanza colonne
                        if len(line) > 23:
                            status = str(line[2]).strip()
                            
                            # Se la task è stata rigettata, estraiamo la motivazione
                            if status == "Rejected":
                                reason = str(line[23]).strip()
                                # Se la cella non è vuota, incrementiamo il contatore
                                if reason:
                                    rejection_counts[reason] += 1
            except Exception as e:
                print(f"Impossibile leggere il file {file}: {e}")

print("-" * 60)
print("RICERCA COMPLETATA! Cause di rigetto e numero di occorrenze:")
print("-" * 60)

if not rejection_counts:
    print("Nessuna causa di rigetto trovata. (Forse nessun task è stato rigettato o la cartella è vuota?)")
else:
    # .most_common() restituisce una lista di tuple (elemento, conteggio) ordinate dalla più frequente
    for reason, count in rejection_counts.most_common():
        print(f"[{count} volte] - {reason}")
print("-" * 60)