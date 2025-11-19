import os
import subprocess
import time

# === PARAMETRI CONFIGURABILI ===
SBATCH_DIR = "SBATCHFILES"
MAX_JOBS = 5             # numero massimo di job attivi contemporaneamente
CHECK_INTERVAL = 30      # ogni quanti secondi controllare lo stato

USER = os.getenv("USER") # utente corrente per squeue

# === RACCOLTA FILE ===
sbatch_files = [
    os.path.join(SBATCH_DIR, f)
    for f in sorted(os.listdir(SBATCH_DIR))
    if f.endswith(".sbatch")
]

print(f"Trovati {len(sbatch_files)} file .sbatch nella cartella '{SBATCH_DIR}'.")

def count_active_jobs():
    """Conta i job attivi (R o PD) per l'utente corrente."""
    result = subprocess.run(
        ["squeue", "-u", USER],
        capture_output=True,
        text=True
    )
    # Tolgo la riga di intestazione
    lines = result.stdout.strip().split("\n")
    return max(0, len(lines) - 1)

# === ESECUZIONE A BLOCCHI ===
for i, sbatch_file in enumerate(sbatch_files, start=1):
    # Controlla quanti job sono già attivi
    while count_active_jobs() >= MAX_JOBS:
        print(f" - Raggiunto limite ({MAX_JOBS}) - attendo {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

    print(f"Lancio job {i}/{len(sbatch_files)}: {sbatch_file}")
    try:
        result = subprocess.run(
            ["sbatch", sbatch_file],
            check=True,
            capture_output=True,
            text=True
        )
        print("->", result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Errore eseguendo {sbatch_file}: {e.stderr.strip()}")

print("Tutti i job sono stati inviati.")
