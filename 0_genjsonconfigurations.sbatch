#!/bin/bash

#SBATCH --job-name=CONFGEN
#SBATCH --partition=students
#SBATCH --output=logs.txt
#SBATCH --error=err.txt

uv run configsGenerator.py