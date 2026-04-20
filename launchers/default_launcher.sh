#!/bin/bash
# bash ${GenTL_Producers}/install_spinnaker.sh
bash

# #!/bin/bash
# set -euo pipefail

# # Name of your installation script
# INSTALL_SCRIPT=$SPINNAKER_INSTALLER_SCRIPT_PATH

# # Start the installation script as a co-process
# coproc INSTALL_PROC (bash -c "cd \"$SPINNAKER_INSTALLER_SCRIPT_PATH\" && bash ./install_spinnaker.sh")


# # INSTALL_PROC[0] = FD for reading (script stdout)
# # INSTALL_PROC[1] = FD for writing (script stdin)

# # Read output line by line and react
# while IFS= read -r line <&"${INSTALL_PROC[0]}"; do
#   # Forward the line in real time
#   echo "$line"

#   # Check for a specific user prompt
#   # Example: the script asks "To add a new member please enter username (or hit Enter to continue):"
#   if [[ "$line" == *"To add a new member please enter username (or hit Enter to continue):"* ]]; then
#     # If the prompt appears, answer "n"
#     echo "n" >&"${INSTALL_PROC[1]}"
#   else
#     # Otherwise always send "y"
#     echo "y" >&"${INSTALL_PROC[1]}"
#   fi
# done

# # Wait for the co-process to finish and inherit exit code
# wait "${INSTALL_PROC_PID:-${INSTALL_PROC[1]}}" 
# exit $?
