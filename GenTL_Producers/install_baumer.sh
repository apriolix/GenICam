#!/bin/bash
echo "Installing Baumer GenTL_Producer ${GenTL_Producers}/Baumer_GAPI_SDK_2.15.2_lin_x86_64_cpp.deb ..."
cd ${GenTL_Producers} && sudo apt install ./Baumer_GAPI_SDK_2.15.2_lin_x86_64_cpp.deb
echo "Producer installed"
