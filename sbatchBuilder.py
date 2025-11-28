import os
import textwrap

# === CONFIGURAZIONE ===
SIMS_SETS = "SIMS_SETS"
SIMS_IMG_RESOLUTIONS = "SIMS_IMG_RESOLUTIONS"

SBATCH_DIR = "SBATCHFILES"   # Destinazione per i file .sbatch
LOG_DIR = "SBATCH_LOGS"      # LOG SLURM

# crea le cartelle se non esistono
os.makedirs(SBATCH_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ottieni tutti i file json nelle due cartelle
sets_files = [f for f in os.listdir(SIMS_SETS) if f.endswith(".json5")]
imgres_files = [f for f in os.listdir(SIMS_IMG_RESOLUTIONS) if f.endswith(".json5")]

# === GENERAZIONE FILE SBATCH ===
for set_file in sets_files:
    for imgres_file in imgres_files:
        
        # nomi senza estensione
        set_name = os.path.splitext(set_file)[0]
        imgres_name = os.path.splitext(imgres_file)[0]

        # nome unico del job
        job_name = f"{set_name}_{imgres_name}"
        job_filename = f"{set_name}__{imgres_name}"
        sbatch_filename = f"{SBATCH_DIR}/{job_filename}.sbatch"

        # contenuto del file .sbatch
        sbatch_content = textwrap.dedent(f"""\
        #!/bin/bash
        #SBATCH --job-name={job_name}
        #SBATCH --partition=students
        #SBATCH --output={LOG_DIR}/OUT_{job_filename}.out
        #SBATCH --error={LOG_DIR}/ERR_{job_filename}.err
        
        uv run main.py {SIMS_SETS}/{set_file} {SIMS_IMG_RESOLUTIONS}/{imgres_file}
        """)

        # scrittura del file .sbatch
        with open(sbatch_filename, "w") as f:
            f.write(sbatch_content)

print(f" Creati {len(sets_files) * len(imgres_files)} file SBATCH in '{SBATCH_DIR}'")
