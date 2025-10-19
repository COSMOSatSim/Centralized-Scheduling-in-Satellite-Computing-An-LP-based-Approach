import os
import textwrap

# === CONFIGURAZIONE ===
seeds = [13, 23, 33, 43, 53, 63, 73, 83, 93, 103, 113]
algorithms = ["GREEDY", "BATMAN", "DINAMICO", "DSR"]
routing_intervals = [1, 0.1]
apBIDIR = [True, False]

# seeds = [13, 23]
# algorithms = ["GREEDY"]
# routing_intervals = [1, 0.1]
# apBIDIR = [True, False]


algodict = {
    "GREEDY":"G",
    "BATMAN":"B", 
    "DINAMICO":"D", 
    "DSR":"R"
}

# cartella di destinazione per i file .sbatch
sbatch_dir = "SBATCHFILES"
# cartella dove Slurm deve salvare i log
log_dir = "SBATCH_LOGS"
# percorso assoluto del progetto
project_dir = "/home/vsalvatore/CLUSTER_SEC/SEC-Cluster"

# crea le cartelle se non esistono
os.makedirs(sbatch_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)

# === GENERAZIONE FILE SBATCH ===
for seed in seeds:
    for algorithm in algorithms:
        for interval in routing_intervals:
            for apb in apBIDIR:
                apb_str = "True" if apb else "False"
                job_name = f"{algodict[algorithm]}{seed}{interval}{apb_str}"
                job_filenam = f"{algorithm}_S{seed}_I{interval}_AP{apb_str}"
                sbatch_filename = f"{sbatch_dir}/{job_filenam}.sbatch"

                # contenuto del file .sbatch
                sbatch_content = textwrap.dedent(f"""\
                #!/bin/bash
                #SBATCH --job-name={job_name}
                #SBATCH --partition=students
                #SBATCH --output={log_dir}/{job_filenam}.out
                #SBATCH --error={log_dir}/{job_filenam}.err


                python3 main_cluster.py {seed} {algorithm} {interval} {apb}
                """)

                # scrittura del file .sbatch
                with open(sbatch_filename, "w") as f:
                    f.write(sbatch_content)