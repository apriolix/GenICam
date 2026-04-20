# Installation
To use this container it is neccesarily to prepare the host computer for the use of nvidia gpus inside an container.
Therefore you need to adjust the ``./cuda/docker/Dockerfile`` by choosing your matching nvidia base image, regarding to your cuda version and adjust the ARCH_BIN as well with the version to your cuda version. Note to check out the cuda_devel_cudnn base image for your cuda version. To get figure out your cuda version, it is required to have all cuda drivers installed on your local machine. Then your can with nvidia-smi or just by using the ``print_cuda_version.sh`` script. Additionally you need to install the nvidia container toolkit drivers on your machine. Therefore you can use the ``init_host.sh`` script.

# Build image
To build the image call ``build_image.sh``

# Run Container
Call ``docker compose up`` in your terminal. Note that the terminal needs to be opened in the same folder like the ``docker-compose.yaml``


This project is based on the use of pythons harvesters library: [text](https://harvesters.readthedocs.io/en/latest/TUTORIAL.html)