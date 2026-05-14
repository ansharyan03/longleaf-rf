#!/bin/bash
#SBATCH --job-name=vcpkg-colmap
#SBATCH --output=vcpkg-colmap.out
#SBATCH --error=vcpkg-colmap.err
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --partition=general

set -eo pipefail
export BASHRCSOURCED=1
module purge
module load gcc/12.2.0
module load cuda
module load cmake

~/bin/micromamba shell init -s bash -r ~/micromamba
source ~/.bashrc
set -x

micromamba activate vcpkg-tools

# Avoid polluted include paths from modules/conda
unset CPATH
unset C_INCLUDE_PATH
unset CPLUS_INCLUDE_PATH
unset OBJC_INCLUDE_PATH
unset INCLUDE

# Paths
export VCPKG_ROOT=/nas/longleaf/home/aaryan2/vcpkg
export VCPKG_BUILDTREES=/nas/longleaf/home/aaryan2/vcpkg-buildtrees
export VCPKG_INSTALLED=/nas/longleaf/home/aaryan2/vcpkg-installed
export CUSTOM_TRIPLETS=$VCPKG_ROOT/custom-triplets
export LONGLEAF_TOOLCHAIN=$VCPKG_ROOT/scripts/toolchains/longleaf-gcc.cmake

export PATH="$CONDA_PREFIX/bin:/nas/longleaf/rhel9/apps/gcc/12.2.0/bin:/usr/bin:/bin:$PATH"
hash -r

export CC=/nas/longleaf/rhel9/apps/gcc/12.2.0/bin/gcc
export CXX=/nas/longleaf/rhel9/apps/gcc/12.2.0/bin/g++

export VCPKG_MAX_CONCURRENCY=${SLURM_CPUS_PER_TASK:-4}

# Prefer system binaries where possible
export VCPKG_FORCE_SYSTEM_BINARIES=1

# Diagnostics
echo "===== Environment check ====="
echo "HOSTNAME=$(hostname)"
echo "VCPKG_ROOT=$VCPKG_ROOT"
echo "CC=$CC"
echo "CXX=$CXX"
echo "CONDA_PREFIX=${CONDA_PREFIX:-}"
echo "VCPKG_MAX_CONCURRENCY=$VCPKG_MAX_CONCURRENCY"
echo "PATH=$PATH"

echo
echo "===== Tool locations ====="
which tar
which cmake
which ninja || true
which gcc
which g++
which cc
which c++
which autoconf
which automake
which libtoolize
which autoreconf

echo
echo "===== Tool versions ====="
gcc --version
g++ --version
cmake --version
autoconf --version | head -n 1
automake --version | head -n 1
libtoolize --version | head -n 1

# Create custom triplet and chainload toolchain to force GCC 12
mkdir -p "$CUSTOM_TRIPLETS"
mkdir -p "$(dirname "$LONGLEAF_TOOLCHAIN")"

cp "$VCPKG_ROOT/triplets/x64-linux.cmake" "$CUSTOM_TRIPLETS/x64-longleaf.cmake"

cat >> "$CUSTOM_TRIPLETS/x64-longleaf.cmake" <<EOF

# Longleaf GCC override
set(VCPKG_CHAINLOAD_TOOLCHAIN_FILE "$LONGLEAF_TOOLCHAIN")
EOF

echo "hostname=$(hostname)"
uname -m
lscpu | egrep 'Architecture|Vendor ID|Model name|CPU family|Model:|Flags'

cat > "$LONGLEAF_TOOLCHAIN" <<EOF
set(CMAKE_C_COMPILER "/nas/longleaf/rhel9/apps/gcc/12.2.0/bin/gcc" CACHE FILEPATH "")
set(CMAKE_CXX_COMPILER "/nas/longleaf/rhel9/apps/gcc/12.2.0/bin/g++" CACHE FILEPATH "")
set(CMAKE_SYSTEM_PROCESSOR "x86_64" CACHE STRING "")
EOF

cd "$VCPKG_ROOT"

rm -rf "$VCPKG_BUILDTREES/lz4"
rm -rf "$VCPKG_ROOT/packages/lz4_x64-linux"
rm -rf "$VCPKG_ROOT/packages/lz4_x64-longleaf"
rm -rf "$VCPKG_INSTALLED/x64-linux/share/lz4"
rm -rf "$VCPKG_INSTALLED/x64-linux/lib/liblz4"*
rm -rf "$VCPKG_INSTALLED/x64-linux/debug/lib/liblz4"*
rm -rf "$VCPKG_INSTALLED/x64-longleaf/share/lz4"
rm -rf "$VCPKG_INSTALLED/x64-longleaf/lib/liblz4"*
rm -rf "$VCPKG_INSTALLED/x64-longleaf/debug/lib/liblz4"*


echo
echo "===== Building COLMAP with CUDA ====="
./vcpkg install 'colmap[cuda]:x64-longleaf' \
  --overlay-triplets="$CUSTOM_TRIPLETS" \
  --x-buildtrees-root="$VCPKG_BUILDTREES" \
  --x-install-root="$VCPKG_INSTALLED"

echo
echo "===== Build completed successfully ====="
