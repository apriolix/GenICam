# Cuda 12.9.0 devel cudnn
FROM nvidia/cuda@sha256:ef33852f3d321c9aedee5103f57b247114407d2e8382fe291a7ea5b2e6cb94ce AS opencv_cuda 

ENV DEBIAN_FRONTEND=noninteractive

#----------------------------------------
# 2. system dependencies
#----------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common \
  && add-apt-repository universe \
  && add-apt-repository multiverse \
  && apt-get update  \
  && apt-get install -y --no-install-recommends \
      build-essential cmake pkg-config unzip yasm git checkinstall \
      libgtk-3-dev libavcodec-dev libavformat-dev libswscale-dev \
      python3-dev python3-pip python3-numpy \
      libjpeg-dev libpng-dev libtiff-dev \
      libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
      libxvidcore-dev libx264-dev libfaac-dev libmp3lame-dev libtheora-dev \
      libopencore-amrnb-dev libopencore-amrwb-dev \
      libdc1394-dev \
      libv4l-dev v4l-utils \
      libtbb2 libtbb-dev libatlas-base-dev gfortran \
      libprotobuf-dev protobuf-compiler libgoogle-glog-dev libgflags-dev \
      libgphoto2-dev libeigen3-dev libhdf5-dev doxygen \
  && rm -rf /var/lib/apt/lists/*


#----------------------------------------
# Opencl
#----------------------------------------
# OpenCL & Blas/FFT
RUN apt-get update && apt-get install -y --no-install-recommends \
      ocl-icd-opencl-dev \
      opencl-headers \
      ocl-icd-libopencl1 \
      clinfo \
      nvidia-opencl-dev \
      libclblas-dev \
      libclfft-dev \
      pocl-opencl-icd \
  && rm -rf /var/lib/apt/lists/*


#----------------------------------------
# 3. remove of preinstalled opencv packages to avoid conflicts with our custom build
#----------------------------------------
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 uninstall -y opencv-python opencv-python-headless || true && \
    apt-get remove -y python3-opencv || true && \
    rm -rf /usr/local/lib/python3*/dist-packages/cv2*

# für opencv
RUN pip3 install "numpy<2" 


#----------------------------------------
# 4. OpenCV-Quellcode clonen
#----------------------------------------
ARG OPENCV_VERSION=4.5.5
WORKDIR /opt
RUN git clone --depth 1  \
      https://github.com/opencv/opencv.git && \
    git clone --depth 1  \
      https://github.com/opencv/opencv_contrib.git

#----------------------------------------
# 5. OpenCV builden
#----------------------------------------
RUN mkdir -p /opt/opencv_build
WORKDIR /opt/opencv_build


ARG CUDA_ARCH_BIN=6.1

RUN cmake \
  -D CMAKE_BUILD_TYPE=Release \
  -D CMAKE_INSTALL_PREFIX=/usr/local \
  -D OPENCV_EXTRA_MODULES_PATH=../opencv_contrib/modules \
  -D BUILD_opencv_python3=ON \
  -D BUILD_opencv_python_bindings_generator=ON \
  -D OPENCV_GENERATE_PKGCONFIG=ON \
  -D OPENCV_PC_FILE_NAME=opencv.pc \
  -D PYTHON3_EXECUTABLE="$(which python3)" \
  -D PYTHON3_INCLUDE_DIR="$(python3 -c 'from sysconfig import get_paths; print(get_paths()[\"include\"])')" \
  -D PYTHON3_NUMPY_INCLUDE_DIRS="$(python3 -c 'import numpy; print(numpy.get_include())')" \
  # CUDA
  -D WITH_CUDA=ON \
  -D CUDA_TOOLKIT_ROOT_DIR="$(dirname "$(dirname "$(which nvcc)")")" \
  -D CUDA_ARCH_BIN="${CUDA_ARCH_BIN}" \
  -D CUDA_ARCH_PTX="${CUDA_ARCH_BIN}" \
  -D ENABLE_FAST_MATH=ON \
  -D CUDA_FAST_MATH=ON \
  -D WITH_CUBLAS=ON \
  -D WITH_CUFFT=ON \
  -D WITH_NVCUVID=ON \
  -D BUILD_opencv_cudaarithm=ON \
  -D BUILD_opencv_cudaimgproc=ON \
  -D BUILD_opencv_cudafilters=ON \
  -D BUILD_opencv_cudaoptflow=ON \
  -D BUILD_opencv_cudawarping=ON \
  -D BUILD_opencv_cudaobjdetect=ON \
  -D BUILD_opencv_cudastereo=ON \
  -D BUILD_opencv_cudalegacy=ON \
  -D BUILD_opencv_cudabgsegm=ON \
  -D BUILD_opencv_cudacodec=ON \
  # DNN CUDA
  -D OPENCV_DNN_CUDA=ON \
  -D WITH_CUDNN=ON \
  # OpenCL (T-API / UMat)
  -D WITH_OPENCL=ON \
  -D BUILD_opencv_opencl=ON \
  -D OPENCV_OPENCL_RUNTIME=dynamic \
  -D WITH_OPENCL_SVM=ON \
  -D WITH_OPENCLAMDBLAS=ON \
  -D WITH_OPENCLAMDFFT=ON \
  # Additional Features
  -D WITH_V4L=ON \
  -D WITH_OPENGL=ON \
  -D WITH_GSTREAMER=ON \
  -D WITH_TBB=ON \
  -D BUILD_opencv_world=ON \
  -D BUILD_EXAMPLES=OFF \
  -D BUILD_TESTS=OFF \
  -D BUILD_DOCS=OFF \
  ../opencv


RUN make -j"$(nproc)" install && \
    ldconfig

WORKDIR /workspace
CMD ["/bin/bash"]


