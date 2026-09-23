#!/bin/bash

# ----- CONFIGURAZIONE -----
VENV_PATH=".venv"
PYTHON="$VENV_PATH/bin/python"

MAIN="main.py"

INPUT_DIR="SIMS_SETS"
SECOND_DIR="SIMS_IMG_RESOLUTIONS"

MAX_PARALLEL=6
# --------------------------

if [ ! -f "$PYTHON" ]; then
    echo "ERRORE: Python del venv non trovato in $PYTHON"
    exit 1
fi

TOTAL=$(find "$INPUT_DIR" -type f | wc -l)
TOTAL2=$(find "$SECOND_DIR" -type f | wc -l)
TOTAL_RUNS=$((TOTAL * TOTAL2))

echo "Trovate $TOTAL_RUNS simulazioni."
echo "Uso interpreter: $PYTHON"
echo "Avvio simulazioni (max $MAX_PARALLEL parallele)"
echo "---------------------------------------------"

run_simulation() {
    INDEX="$1"
    FILE1="$2"
    FILE2="$3"

    BASE1=$(basename "$FILE1")
    BASE2=$(basename "$FILE2")

    echo "[START] ($INDEX/$TOTAL_RUNS) $BASE1 + $BASE2"

    "$PYTHON" "$MAIN" "$FILE1" "$FILE2" > /dev/null 2>&1

    echo "[END]   ($INDEX/$TOTAL_RUNS) $BASE1 + $BASE2"
}

export -f run_simulation
export PYTHON MAIN TOTAL_RUNS

# genera tutte le combinazioni e numerale
{
    find "$INPUT_DIR" -type f | while read f1; do
        find "$SECOND_DIR" -type f | while read f2; do
            echo "$f1|$f2"
        done
    done
} | nl -w1 -s '|' | \
xargs -P $MAX_PARALLEL -n1 -I{} bash -c '
    IFS="|" read IDX F1 F2 <<< "{}"
    run_simulation "$IDX" "$F1" "$F2"
'

echo "---------------------------------------------"
echo "Tutte le simulazioni sono terminate."