#!/bin/bash

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mem=128G
#SBATCH --partition=l40-gpu
#SBATCH --qos=gpu_access
#SBATCH --mail-type=ALL
#SBATCH --gres=gpu:nvidia_l40s:2
#SBATCH --output=bigjob.out
module load cuda/13.0
module load python/3.12.4
cd /work/users/a/a/aaryan2/models

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
source /users/a/a/aaryan2/gsplats/bin/activate
export CUDA_VISIBLE_DEVICES=0,1
ns-train nerfacto-big --data "/work/users/a/a/aaryan2/data/main/main-west" --pipeline.datamanager.dataloader_num_workers 8 --machine.num-devices 2 --vis wandb colmap > test.out

