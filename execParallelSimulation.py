import os
import subprocess

# cartella di destinazione per i file .sbatch
sbatch_dir = "SBATCHFILES"
# cartella dove Slurm deve salvare i log
log_dir = "SBATCH_LOGS"
# percorso assoluto del progetto
project_dir = "/home/vsalvatore/CLUSTER_SEC/SEC-Cluster"

# crea le cartelle se non esistono
os.makedirs(sbatch_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
# Lista tutti i file che finiscono con .sbatch
sbatch_files = [
    os.path.join(sbatch_dir, f)
    for f in os.listdir(sbatch_dir)
    if f.endswith(".sbatch")
]

print(f"Trovati {len(sbatch_files)} file .sbatch nella cartella '{sbatch_dir}'.")

# Lancia ogni file sbatch
for sbatch_file in sbatch_files:
    print(f"Lancio {sbatch_file}...")
    try:
        result = subprocess.run(
            ["sbatch", sbatch_file],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout.strip())  # stampa l'output di sbatch (es. job ID)
    except subprocess.CalledProcessError as e:
        print(f"Errore eseguendo {sbatch_file}: {e.stderr.strip()}")
