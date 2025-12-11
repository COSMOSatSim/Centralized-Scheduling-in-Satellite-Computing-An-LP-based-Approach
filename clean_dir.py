import os
import glob

# === CONFIGURAZIONE ===
# Definisci il pattern da cercare (tutti i file che finiscono con .out)
FILE_PATTERN = "*.out"
# Directory di esecuzione (la cartella corrente)
DIRECTORY = "."

print(f"--- Pulizia file di output ({FILE_PATTERN}) nella directory '{DIRECTORY}' ---")

# Usa glob per trovare tutti i file che corrispondono al pattern
files_to_delete = glob.glob(os.path.join(DIRECTORY, FILE_PATTERN))

if not files_to_delete:
    print("Nessun file .out trovato da eliminare.")
else:
    print(f"Trovati {len(files_to_delete)} file da eliminare.")
    
    # Conferma di sicurezza (opzionale ma consigliata)
    confirmation = input("Sei sicuro di voler eliminare questi file? (s/n): ")
    
    if confirmation.lower() == 's':
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                # Rimuovi il file
                os.remove(file_path)
                deleted_count += 1
                # print(f"Eliminato: {file_path}") # Rimuovi il commento se vuoi vedere l'elenco completo
            except OSError as e:
                print(f"Errore nell'eliminazione di {file_path}: {e}")

        print(f"\n--- Pulizia completata. Eliminati {deleted_count} file. ---")
    else:
        print("\nOperazione annullata dall'utente. Nessun file è stato eliminato.")