#!/bin/bash
set -euo pipefail
shopt -s extglob

# 1) Define all possible prompt strings and their answers
declare -A answers=(
  ["Wie ist dein Name?"]="Max Mustermann"
  ["Alter eingeben:"]="42"
  ["Fortfahren mit Installation? (j/n)"]="j"
  ["Installationsverzeichnis:"]="/opt/meinprogramm"
)

# 2) Start the install script as a coprocess
#    TARGET[0]=stdout of install.sh, TARGET[1]=stdin to install.sh
coproc TARGET { bash ./install_spinnaker.sh; }

# 3) File descriptor aliases (optionally more readable)
exec 3>&"${TARGET[1]}"   # fd 3 → stdin of install.sh
exec 4< <(cat <&"${TARGET[0]}")  # fd 4 ← stdout of install.sh

# 4) Parse output and send answers
while IFS= read -r -u 4 line; do
  printf '%s\n' "$line" >&2           # echo der Ausgabe fürs Debugging
  for prompt in "${!answers[@]}"; do
    if [[ $line == *"$prompt"* ]]; then
      printf '%s\n' "${answers[$prompt]}" >&3
      break
    fi
  done
done

# 5) Wait for the coprocess to finish
wait "${TARGET_PID:-${!TARGET[@]}}"
exit 0
