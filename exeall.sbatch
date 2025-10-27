#!/bin/bash

#SBATCH --job-name=SBTCH_BLDR
#SBATCH --partition=students
#SBATCH --output=logs.txt
#SBATCH --error=err.txt

python3 execParallelBlocks.py