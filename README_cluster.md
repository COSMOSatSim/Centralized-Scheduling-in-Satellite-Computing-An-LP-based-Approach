
# 🚀 Guida alla Pipeline di Simulazione (Slurm + uv)

Questa repository contiene una pipeline automatizzata per generare migliaia di configurazioni di rete e simularle in parallelo su un cluster Slurm utilizzando `uv` come gestore di pacchetti e ambienti Python.

## 📋 Prerequisiti
* **Slurm**: Il cluster deve avere Slurm installato e configurato.
* **uv**: Assicurati che `uv` sia nel tuo PATH (esegui `uv --version` per verificare).
* **Python**: Gli script utilizzano `json5` per gestire i file di configurazione.

---

## 🏗️ Struttura della Pipeline

La pipeline si divide in tre fasi principali:
1. **Generazione Config**: Creazione di tutte le combinazioni di parametri.
2. **Preparazione Input**: Creazione delle liste di file per l'esecuzione parallela.
3. **Sottomissione (Job Array)**: Lancio dei job sul cluster.



---

## 🛠️ Step 1: Generazione Configurazioni (`configsGenerator.py`)
Il primo script genera i file `.json5` incrociando i parametri (Seed, Algoritmi, Budget Energetico, ecc.).

**Cosa fa:**
- Crea le cartelle `SIMS_SETS/` e `SIMS_IMG_RESOLUTIONS/`.
- Genera i file di configurazione basandosi su `config.json5` e `img_resolution.json5`.
- **Fondamentale:** Crea i file `sims_sets_list.txt` e `img_resolutions_list.txt` che servono come indice per il Job Array.

**Come lanciarlo:**
```bash
sbatch 0_run_generator.sh
```
*(Oppure direttamente: `uv run configsGenerator.py` se sei sul nodo di login e il calcolo è leggero).*

---

## 📂 Step 2: Preparazione Job (`sbatchBuilder.py`)
Questo script (opzionale se usi gli Array) crea file `.sbatch` individuali per ogni singola simulazione nella cartella `SBATCHFILES/`.

**Come lanciarlo:**
```bash
sbatch 1_run_builder.sh
```

---

## ⚡ Step 3: Esecuzione Massiva (Job Array)
Questo è il metodo più efficiente per far girare migliaia di simulazioni senza intasare il sistema. Utilizziamo due script: **A** (il lanciatore) e **B** (l'esecutore).

### Script A: `A_submit_dynamic_array.sh`
È un manager che conta quante righe ci sono nelle liste generate allo Step 1 e sottomette lo script B con il parametro `--array`.
* **Comando:** `bash A_submit_dynamic_array.sh`
* **Configurazione:** È impostato per far girare **15 job alla volta** (`%15`).

### Script B: `B_run_simulations_array.sh`
È il "lavoratore" che gira sui nodi del cluster.
1. Legge il suo ID univoco (`$SLURM_ARRAY_TASK_ID`).
2. Preleva la riga corrispondente da `sims_sets_list.txt` e `img_resolutions_list.txt`.
3. Esegue la simulazione: `uv run main.py <set_file> <img_res_file>`.

---

## 📊 Monitoraggio e Debug

### Controllare lo stato dei Job
Per vedere i tuoi job in coda o in esecuzione:
```bash
squeue -u $USER
```

### Leggere i Log
I log di output e di errore vengono salvati automaticamente in:
- `SBATCH_LOGS/OUT_jobid_taskid.out` (Standard output)
- `SBATCH_LOGS/ERR_jobid_taskid.err` (Errori e stacktrace Python)

### Cancellare i Job
Se ti accorgi di un errore e vuoi fermare tutto l'array:
```bash
scancel -u $USER
```

---

## 📝 Note Tecniche
- **Ambiente Virtuale**: Lo script B attiva automaticamente il venv in `/home/casalicchio/bagini/.venv`.
- **Efficienza**: `uv run` garantisce che ogni job utilizzi le dipendenze corrette in modo ultra-veloce.
- **Limiti**: Il limite di 15 job simultanei è impostato per rispettare le policy della partizione `department_only` o `students`.

