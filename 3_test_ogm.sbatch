#!/bin/bash
#SBATCH --job-name=OGMsTest
#SBATCH --partition=students
#SBATCH --output=OUT_ogm.out
#SBATCH --error=ERR_ogm.err

source /home/vsalvatore/env_cluster/bin/activate

python main.py