#!/bin/bash

# ==============================================================================
# Direttive Slurm (SENZA --array, viene fornito esternamente)
# ==============================================================================
#SBATCH --job-name=Sims_Array
#SBATCH --partition=students

# prima che le variabili Bash vengano definite.
#SBATCH --output=SBATCH_LOGS/OUT_%A_%a.out
#SBATCH --error=SBATCH_LOGS/ERR_%A_%a.err

# ==============================================================================
# 1. PREPARAZIONE E ATTIVAZIONE AMBIENTE
# ==============================================================================

# Definisci la directory del tuo ambiente virtuale. 
# Uso il percorso /home/vsalvatore/SECMotionModel/ come directory principale del progetto.
# ADATTA QUESTO PERCORSO se il tuo ambiente non si chiama .venv o si trova altrove.
VENV_DIR="/home/vsalvatore/SECMotionModel/.venv"

# 1.1. Crea la cartella dei log (Garanzia che esista quando il task inizia)
mkdir -p SBATCH_LOGS

# 1.2. Verifica e Attiva l'ambiente virtuale
if [ -d "$VENV_DIR" ]; then
    echo "Trovato ambiente virtuale in $VENV_DIR."
    
    # ----------------------------------------------------------------------
    # SOLUZIONE ALL'ERRORE 'ModuleNotFoundError' (Aggiunta qui)
    # ----------------------------------------------------------------------
    # Attiva l'ambiente virtuale. Questo aggiunge i binari di .venv, 
    # incluso 'uv' e 'python', al PATH del job.
    source "$VENV_DIR/bin/activate"
    echo "Ambiente virtuale attivato con successo."
    
else
    echo "ERRORE CRITICO: Ambiente virtuale non trovato in $VENV_DIR." >&2
    echo "Impossibile continuare. Assicurati che il percorso sia corretto e accessibile." >&2
    exit 1
fi


# ==============================================================================
# Logica di Esecuzione per ogni Task
# ==============================================================================

TASK_ID=$SLURM_ARRAY_TASK_ID
SIMS_LIST_FILE="sims_sets_list.txt"
IMG_RES_LIST_FILE="img_resolutions_list.txt"

# Estrai la riga corrispondente all'ID del Task
SET_FILE=$(sed -n "${TASK_ID}p" "$SIMS_LIST_FILE")
IMG_FILE=$(sed -n "${TASK_ID}p" "$IMG_RES_LIST_FILE")

echo "--- Esecuzione Task ID: $TASK_ID ---"
echo "  SET File: $SET_FILE"
echo "  IMG RES File: $IMG_FILE"

# Esegui la tua simulazione
uv run main.py "$SET_FILE" "$IMG_FILE"