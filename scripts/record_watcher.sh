#!/bin/bash
#
# Author: Juha Leivo
# Version: 4
# Date: 2023-12-26
#
# History
#   1 - 2023-04-29, initial write, monitors folder, converts items to flac
#   2 - 2023-05-05, Minor typo fixed, improved task/note detection, corrected
#       bug in detecting files with spaces in their names 
#   3 - 2023-11-20 Implemented LLM based speech-to-text, Shellcheck done to the
#       script
#   4 - 2023-12-26 Full rewrite, removed dependency to shared functions

readonly MONITORING_DIR=/audio

################################# FUNCTIONS ####################################

function monitor_directory() {

    echo "Monitoring directory: ${1}"
    # shellcheck disable=SC2034  # Unused variables left for readability
    inotifywait -m "${1}" -e create -e moved_to |
    while read -r dir action file; do
       result=$(python3 /app/LLM_text_to_speech.py -f "${1}/${file}")
       echo "${result}"
    done
}


##################################### LOGIC ####################################
echo ''
echo 'Starting record watcher'
monitor_directory "${MONITORING_DIR}"