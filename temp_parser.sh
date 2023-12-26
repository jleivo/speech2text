#!/bin/bash

declare -a magicwords_array
declare -A magicwords_dict

create_array_and_dictionary() {
    local file="$1"
    local magicword
    local keepaudiofile
    local transcript
    local email

    while IFS= read -r line; do
        magicword=$(echo "$line" | jq -r '.magicword')
        keepaudiofile=$(echo "$line" | jq -r '.keepaudiofile')
        transcript=$(echo "$line" | jq -r '.transcript')
        email=$(echo "$line" | jq -r '.email // "noemail"')

        # Add magicword to the array
        magicwords_array+=("$magicword")

        # Add entry to the dictionary
        if [ -n "${magicwords_dict[$magicword]}" ]; then
            magicwords_dict[$magicword]="${magicwords_dict[$magicword]},$keepaudiofile:$transcript:$email"
        else
            magicwords_dict[$magicword]="$keepaudiofile:$transcript:$email"
        fi
    done < <(jq -c '.[]' "$file")
}

# Usage
create_array_and_dictionary "$1"

# Print the magicwords array
echo "Magicwords Array: ${magicwords_array[@]}"

# Print the magicwords dictionary
for key in "${!magicwords_dict[@]}"; do
    echo "Magicword: $key, Values: ${magicwords_dict[$key]}"
done
