import os
import glob
import subprocess
import sys
from multiprocessing import Pool, cpu_count

# Percorso della cartella contenente i file generati
# Assicurati che questo percorso sia corretto
CONFIG_DIR = os.path.join(os.getcwd(), "SIMS_SETS")


def run_simulation(config_path):
    """
    Funzione eseguita da ogni worker.
    """
    file_name = os.path.basename(config_path)
    print(f"--> [START] Avvio simulazione per: {file_name}")

    try:
        subprocess.run([sys.executable, "main.py", config_path], check=True)

        print(f"<-- [END] Completata: {file_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! [ERROR] Errore nella simulazione {file_name}: {e}")
        return False
    except Exception as ex:
        print(f"!!! [ERROR] Eccezione generica in {file_name}: {ex}")
        return False


def main():
    # 1. Trova tutti i file .json5 nella cartella
    json_files = glob.glob(os.path.join(CONFIG_DIR, "*.json5"))

    if not json_files:
        print(f"Nessun file .json5 trovato in: {CONFIG_DIR}")
        return

    print(f"Trovati {len(json_files)} file di configurazione.")

    # 2. Imposta i processi (lascia 2 core liberi per il sistema)
    num_processes = max(1, cpu_count() - 2)
    print(f"Avvio esecuzione parallela su {num_processes} processi...")

    # 3. Avvia il pool
    with Pool(processes=num_processes) as pool:
        pool.map(run_simulation, json_files)

    print("\n--- TUTTE LE SIMULAZIONI COMPLETATE ---")


if __name__ == "__main__":
    main()