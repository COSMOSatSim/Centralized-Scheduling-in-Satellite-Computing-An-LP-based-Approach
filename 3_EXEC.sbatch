#!/bin/bash
#SBATCH --job-name=DSR_simulation
#SBATCH --partition=students
#SBATCH --output=OUT_DSR.txt
#SBATCH --error=ERR_DSR.txt


uv run main.py