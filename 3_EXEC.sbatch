#!/bin/bash
#SBATCH --job-name=OGMsTest
#SBATCH --partition=students
#SBATCH --output=OUT_ogm.txt
#SBATCH --error=ERR_ogm.txt


uv run main.py