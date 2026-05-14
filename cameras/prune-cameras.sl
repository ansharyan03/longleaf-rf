#!/bin/bash

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mem=32G
#SBATCH --qos=gpu_access
#SBATCH --output=cameras.out

cd /work/users/a/a/aaryan2
source /users/a/a/aaryan2/nerf/bin/activate
python ~/prune-cameras.py --input /work/users/a/a/aaryan2/data/main-new --output /work/users/a/a/aaryan2/data/main-prune2 --min-translation 0.006 --min-rotation-deg 2 --copy-downscaled-dirs
