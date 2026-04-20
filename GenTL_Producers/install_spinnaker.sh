#!/bin/bash
echo "Installing Spinnaker GenTL_Producer ${GenTL_Producers}/spinnaker-4.2.0.46-amd64/install_spinnaker.sh ..."
cd ${GenTL_Producers}/spinnaker-4.2.0.46-amd64 && bash install_spinnaker.sh

echo "Producer installed"