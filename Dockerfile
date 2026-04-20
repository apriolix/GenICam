#######
# Info: To share (mount/bind) a host folder with its content to the container execute the following run-command:  
#   docker run -it --mount type=bind,source=<absolute-path-to-host-folder>,target=<absolute-path-in-container> <image-name>
# Through mounting a folder, all changes made in that folder in the container are directly synchronized to the host folder.
#######

# First stage: base setup with ROS
FROM opencv_cuda AS ros_setup

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    ROS_DISTRO=humble

# 1) System update + basic tools
RUN apt update && apt install -y \
    locales apt-transport-https ca-certificates curl gnupg2 lsb-release \
  && locale-gen en_US.UTF-8

# 2) Add ROS 2 repo
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    | apt-key add - \
 && echo "deb [arch=amd64] http://packages.ros.org/ros2/ubuntu \
    $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/ros2.list

# 3) Install ROS 2 base & dev tools
RUN apt update && apt install -y \
    ros-humble-ros-base \
    python3-colcon-common-extensions \
    python3-rosdep \
    ros-dev-tools

# 4) Initialize rosdep
RUN rosdep init && rosdep update

# 5) Working directory & environment setup
RUN mkdir -p /tmp/ros2_ws/src
WORKDIR /tmp/ros2_ws
RUN echo "source /opt/ros/humble/setup.sh" \
    >> /root/.bashrc


FROM ros_setup AS user_setup
ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

ARG USERNAME=dockerino
ARG USER_UID=1000
ARG USER_GID=1000
ARG GenTL_DRIVER_VERSION=x86_64 

RUN mkdir -p /etc/sudoers.d \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd -m --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo "$USERNAME ALL=(root) NOPASSWD: ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME


RUN echo "source /opt/ros/humble/setup.sh" \
    >> /home/${USERNAME}/.bashrc

COPY packages.txt /tmp/
RUN apt-get update && xargs apt-get install -y < /tmp/packages.txt && apt-get update

FROM user_setup AS python_setup
RUN python3 --version
COPY requirements.txt /tmp/
RUN python3 -m pip install -r /tmp/requirements.txt

FROM python_setup AS spinnaker_installation

# Copying the gentl producers into image
ARG GenTL_Producers_Path=/GenTL_Producers
RUN mkdir -p ${GenTL_Producers_Path} && mkdir -p /etc/udev/rules.d
COPY ./GenTL_Producers ${GenTL_Producers_Path}

# Unpack spinnaker and remove tar
RUN tar -xf ${GenTL_Producers_Path}/spinnaker-4.2.0.46-amd64-22.04-pkg.tar.gz -C ${GenTL_Producers_Path} && \
    rm -r ${GenTL_Producers_Path}/spinnaker-4.2.0.46-amd64-22.04-pkg.tar.gz

# Install spinnaker
WORKDIR ${GenTL_Producers_Path}/spinnaker-4.2.0.46-amd64
RUN chmod -x ./install_spinnaker.sh
RUN yes | bash ./install_spinnaker.sh


FROM spinnaker_installation AS baumer_installation
RUN wget https://share.baumer.com/link/S4yd3lRLvn0rvSuDxgKrpe/download/Baumer_GAPI_SDK_2.15.2_lin_x86_64_cpp.tar.gz -P /tmp

ARG SDK_ARCHIVE=Baumer_GAPI_SDK_2.15.2_lin_x86_64_cpp.tar.gz
ARG INSTALL_DIR=/opt/baumer-gapi

# Entpacken und aufräumen
RUN mkdir -p ${INSTALL_DIR} \
 && tar -xzf /tmp/${SDK_ARCHIVE} -C ${INSTALL_DIR} --strip-components=1 \
 && rm /tmp/${SDK_ARCHIVE}


FROM baumer_installation AS final
ARG WorkingDirectory=/GeniCamROS
ENV LaunchScriptPath=/launchers
ENV LaunchScriptName=default_launcher

ENV GenTL_Producers=${GenTL_Producers_Path}

ENV WorkingDir=${WorkingDirectory}
WORKDIR ${WorkingDirectory}

COPY ./launchers ${LaunchScriptPath}

RUN chmod -x ${LaunchScriptPath}/${LaunchScriptName}.sh
RUN chmod -x ${GenTL_Producers_Path}/install_baumer.sh
RUN chmod -x ${GenTL_Producers_Path}/install_spinnaker.sh

#####
# Enable docker communication out of an container
#####
COPY ./dds_profile/dds_profile.xml /etc/ros/dds_profiles/dds_profile.xml
ENV FASTRTPS_DEFAULT_PROFILES_FILE=/etc/ros/dds_profiles/dds_profile.xml
#####

ENV LAUNCH=${LaunchScriptPath}/${LaunchScriptName}.sh

RUN apt-get install -y bash

ENV USER=$USERNAME




# Forcing all sh-Shell launch commands to launch bash instead
RUN ln -sf /bin/bash /bin/sh
# Setting bash as default shell
SHELL ["/bin/bash", "-l", "-c"]
# Entry command launches shell
CMD ["/bin/bash"]

USER $USER

