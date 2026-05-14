module reset
module load cuda/13.0
module load git-lfs/3.6.1
module load python/3.12.4
module load cmake/4.0.3

USERS_ROOT=users/a/a/aaryan2
ENV_PATH=/$USERS_ROOT/gsplats
python -m venv $ENV_PATH
source $ENV_PATH/bin/activate
export MODEL_FOLDER=/work/$USERS_ROOT/models
cd $MODEL_FOLDER

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
pip install --no-build-isolation git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
git clone --recurse-submodules https://github.com/nerfstudio-project/nerfstudio.git
cd $MODEL_FOLDER/nerfstudio
pip install --upgrade pip setuptools
pip install -e .
cd $MODEL_FOLDER
pip install --no-build-isolation git+https://github.com/nerfstudio-project/gsplat.git
