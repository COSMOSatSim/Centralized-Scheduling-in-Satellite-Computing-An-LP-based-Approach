#!/bin/bash

#SBATCH --job-name=SBTCH_BLDR
#SBATCH --partition=students
#SBATCH --output=logs.txt
#SBATCH --error=err.txt

uv run sbatchBuilder.py