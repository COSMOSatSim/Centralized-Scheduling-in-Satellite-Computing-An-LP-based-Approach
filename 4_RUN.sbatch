#!/bin/bash
#SBATCH --job-name=DSR
#SBATCH --partition=students
#SBATCH --output=OUT_DSR.txt
#SBATCH --error=ERR_DSR.txt

uv run main.py