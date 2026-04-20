
#!/usr/bin/env bash
set -euo pipefail

# Name of your installation script
INSTALL_SCRIPT="./install.sh"

# Start the installation script as a co-process
coproc INSTALL_PROC ( bash "$INSTALL_SCRIPT" )

# INSTALL_PROC[0] = FD for reading (script stdout)
# INSTALL_PROC[1] = FD for writing (script stdin)

# Read output line by line and react
while IFS= read -r line <&"${INSTALL_PROC[0]}"; do
  # Forward the line in real time
  echo "$line"

  # Check for a specific user prompt
  # Example: the script asks "Do you want to continue? [Y/n]"
  if [[ "$line" == *"Would you like to add a udev entry to allow access to USB hardware?\n\tIf a udev entry is not added, your cameras may only be accessible by running Spinnaker as sudo."* ]]; then
    # If the prompt appears, answer "n"
    echo "n" >&"${INSTALL_PROC[1]}"
  else
    # Otherwise always send "y"
    echo "y" >&"${INSTALL_PROC[1]}"
  fi
done

# Wait for the co-process to finish and inherit exit code
wait "${INSTALL_PROC_PID:-${INSTALL_PROC[1]}}" 
exit $?
