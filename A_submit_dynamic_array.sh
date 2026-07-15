#!/bin/bash

# 1. Definisci il file di lista da usare per il conteggio
SIMS_LIST_FILE="sims_sets_list.txt"

# Usa il comando 'cat' e 'wc' per contare le righe in modo affidabile.
NUM_JOBS=$(cat "$SIMS_LIST_FILE" | wc -l)
NUM_JOBS=$(echo "$NUM_JOBS" | tr -d ' ') # Rimuovi spazi extra

if [ "$NUM_JOBS" -eq 0 ]; then
    echo "Errore: Il file di input $SIMS_LIST_FILE è vuoto. Nessun job da sottomettere."
    exit 1
fi

echo "Trovati $NUM_JOBS task totali. Generazione dell'array 1-$NUM_JOBS."

# 2. Costruisci il range dell'array.
ARRAY_RANGE="1-$NUM_JOBS"

# 3. Sottometti lo script Array (modifica il nome se hai usato .sbatch)
sbatch --array="$ARRAY_RANGE%30" B_run_simulations_array.sh