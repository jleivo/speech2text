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
readonly TARGET_DATA=/targets.json
readonly TARGET_DIR=/target
declare -A magicwords_dict
DEBUG=1

################################# FUNCTIONS ####################################

function monitor_directory() {
  local result

  echo "Monitoring directory: ${1}"
  # shellcheck disable=SC2034  # Unused variables left for readability
  inotifywait -m "${1}" -e create -e moved_to |
  while read -r dir action file; do
      echo "Detected change in ${1}/${file}"
      result=$(python3 /app/LLM_text_to_speech.py -f "${1}/${file}")
      if [ "$DEBUG" = 1 ]; then 
      echo ""
      echo "Transcript is as follows"
      echo "${result}" 
      echo ""
      fi
      # detect if the first word in the result is in the magicwords_array, while
      # remove all characters that don't belong to alphabet from the firstword
      # and then lowercase it ...
      firstword="${result## *}"
      echo "First word: ${firstword}"
      firstword="${firstword//[^a-zA-Z0-9]/}"
      firstword="$(echo "$firstword"| tr '[:upper:]' '[:lower:]')"
      if [ "$DEBUG" = 1 ] ; then echo "Cleaned up first word: ${firstword}"; fi
      # detect if the first word in the result is in the magicwords_array
      if [[ " ${magicwords_array[*]} " =~ "${firstword}" ]]; then
        # get the magicword, email, keepaudiofile, transcript from the result
        magicword="${firstword}"
        OLDIFS=$IFS
        # parse keepaudiofile,transcript and email from magicwords_dict
        if [ "$DEBUG" = 1 ]; then 
          echo "Dictionary for this magic word is ${magicwords_dict["$magicword"]}"; 
        fi
        IFS=":"
        read -r keepaudiofile transcript email filename <<< "${magicwords_dict[$magicword]}"
        IFS=$OLDIFS
        # if DEBUG is defined as 1, print all the variables
        if [ "$DEBUG" = 1 ]; then
          echo "Results of parsing the dictionary for $magicword is:"
          echo "Keepaudiofile: ${keepaudiofile}"
          echo "Transcript: ${transcript}"
          echo "Email: ${email}"
          echo "Note filename is: ${filename}"
        fi
        # if the email is not "noemail", send the email    
        if [ "$email" != "noemail" ]; then
          # process email
          echo "sending email to $email"
        else
          create_note "$keepaudiofile" "$transcript" "$file" "$result" "$1" "$filename"
        fi
      else
        echo "First word is not in the magicwords_array"
        # parse keepaudiofile,transcript and email from magicwords_dict
        if [ "$DEBUG" = 1 ]; then 
          echo "Dictionary for this magic word is ${magicwords_dict["default"]}"; 
        fi
        OLDIFS=$IFS
        IFS=":"
        read -r keepaudiofile transcript email  <<< "${magicwords_dict["default"]}"
        # if DEBUG is defined as 1, print all the variables
        if [ "$DEBUG" = 1 ]; then
          echo "Results of parsing the dictionary for 'default' is:"
          echo "Keepaudiofile: ${keepaudiofile}"
          echo "Transcript: ${transcript}"
          echo "Email: ${email}"
          echo "Note filename is: ${filename}"
        fi
        IFS=$OLDIFS
        create_note "$keepaudiofile" "$transcript" "$file" "$result" "$1" "$filename"
      fi

  done
}

function generate_monitoring_dictionary() {
    local magicword
    local keepaudiofile
    local transcript
    local email

    if [ "$DEBUG" = 1 ]; then echo "Building dictionary"; fi
    entry=0

    while IFS= read -r line; do
        magicword=$(echo "$line" | jq -r '.magicword')
        keepaudiofile=$(echo "$line" | jq -r '.keepaudiofile')
        transcript=$(echo "$line" | jq -r '.transcript')
        email=$(echo "$line" | jq -r '.email // "noemail"')
        filename=$(echo "$line" | jq -r '.filename // "none"')

        # Add magicword to the array
        magicwords_array+=("$magicword")

       # if DEBUG=1 print all the variables
        if [ "$DEBUG" = "1" ]; then
            echo "Entry $entry"
            echo "magicword: $magicword"
            echo "keepaudiofile: $keepaudiofile"
            echo "transcript: $transcript"
            echo "email: $email" 
            echo "filename: $filename" 
            echo "array: ${magicwords_array[*]}"
            echo ""
            entry=$((entry+1))
        fi

        # Add entry to the dictionary
        if [ -n "${magicwords_dict[$magicword]}" ]; then
            magicwords_dict[$magicword]="${magicwords_dict[$magicword]},$keepaudiofile:$transcript:$email"
        else
            magicwords_dict[$magicword]="$keepaudiofile:$transcript:$email"
        fi
    done < <(jq -c '.[]' "$TARGET_DATA")

    if [ "$DEBUG" = 1 ]; then echo "Dictionary done."; fi

}

# first parameter is keepaudiofile
# second parameter is transcript
# third parameter is audio filename
# fourth parameter is result from LLM_text_to_speech.py
# fifth parameter is directory where the file is located
# sixth parameter is optional filename
function create_note() {
    local keepaudiofile="$1"
    local transcript="$2"
    local file="$3"
    local result="$4"
    local directory="$5"
    local notename="$6"

    # get the file name from the file path unless the notename variable has something
    # else than none in it.
    if [ "$notename" = "none" ]; then 
      mdfilename="${file##*/}"
    else
      mdfilename="${notename}"
    fi
    
    # create a file with the transcribed output that is located in the directory
    # defined by transcript variable. Verify that the directory exists
    # and create it if it doesn't.
    if [ ! -d "${TARGET_DIR}/${transcript}" ]; then
      mkdir -p "${TARGET_DIR}/${transcript}"
    fi
    echo "${result}" >> "${TARGET_DIR}/${transcript}/${mdfilename}.md"
    # move the file to directory defined by keepaudiofile and 
    # add MD link to the file to the note if keepaudiofile is not false
    if [ "$keepaudiofile" != "false" ]; then
      mkdir -p "/${TARGET_DIR}/${keepaudiofile}"
      mv "${directory}/${file}" "/${TARGET_DIR}/${keepaudiofile}/"
      echo "![[${keepaudiofile}/${file}]]" >> "/${TARGET_DIR}/${transcript}/${mdfilename}.md"
      echo "Added link to file: ${keepaudiofile}/${filename}"
    else
      rm "${directory}/${filename}"
    fi


}

##################################### LOGIC ####################################
echo ''
echo 'Starting record watcher'
generate_monitoring_dictionary
monitor_directory "${MONITORING_DIR}"