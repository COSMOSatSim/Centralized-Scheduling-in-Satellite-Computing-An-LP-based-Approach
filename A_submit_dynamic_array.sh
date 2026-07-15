#!/bin/bash

SIMS_LIST_FILE="sims_sets_list.txt"

NUM_JOBS=$(cat "$SIMS_LIST_FILE" | wc -l)
NUM_JOBS=$(echo "$NUM_JOBS" | tr -d ' ')

if [ "$NUM_JOBS" -eq 0 ]; then
    echo "Errore: Il file di input $SIMS_LIST_FILE è vuoto."
    exit 1
fi

echo "Trovati $NUM_JOBS task totali. Inizio accodamento sequenziale con Offset."

MAX_ARRAY_SIZE=1000
PREV_JOB_ID=""
CURRENT_OFFSET=0

while [ $CURRENT_OFFSET -lt $NUM_JOBS ]; do
    
    # Calcola quanti job rimangono da inviare
    REMAINING=$((NUM_JOBS - CURRENT_OFFSET))
    
    # Se i rimanenti superano il limite, invia un blocco pieno (1000), altrimenti invia quello che resta
    if [ $REMAINING -gt $MAX_ARRAY_SIZE ]; then
        CHUNK_SIZE=$MAX_ARRAY_SIZE
    else
        CHUNK_SIZE=$REMAINING
    fi

    # Il range di Slurm sarà SEMPRE compreso tra 1 e MAX_ARRAY_SIZE
    ARRAY_RANGE="1-$CHUNK_SIZE"
    
    echo "Sottomissione blocco con OFFSET: $CURRENT_OFFSET (Range Slurm: $ARRAY_RANGE)"
    
    # Esportiamo la variabile CHUNK_OFFSET affinché lo script B possa leggerla
    export CHUNK_OFFSET=$CURRENT_OFFSET
    
    if [ -z "$PREV_JOB_ID" ]; then
        # Primo blocco (usa --parsable per estrarre il Job ID pulito)
        PREV_JOB_ID=$(sbatch --parsable --array="$ARRAY_RANGE%50" B_run_simulations_array.sh)
    else
        # Blocchi successivi concatenati
        echo "  -> In attesa che il blocco $PREV_JOB_ID finisca..."
        PREV_JOB_ID=$(sbatch --parsable --dependency=afterany:$PREV_JOB_ID --array="$ARRAY_RANGE%50" B_run_simulations_array.sh)
    fi
    
    echo "  -> Job ID assegnato da Slurm: $PREV_JOB_ID"
    
    # Avanza l'offset per il prossimo ciclo
    CURRENT_OFFSET=$((CURRENT_OFFSET + CHUNK_SIZE))
done

echo "Tutti i blocchi sono stati accodati con successo!"