#!/bin/bash
echo "Cuda version: "
nvidia-smi | grep -m1 "CUDA Version" \
            | sed -E 's/.*CUDA Version: *([0-9]+\.[0-9]+).*/\1/'

echo "CUDA_ARCH_BIN version: "
nvidia-smi --query-gpu=compute_cap --format=csv,noheader

ARG="$(which nvcc)"
echo "$ARG"