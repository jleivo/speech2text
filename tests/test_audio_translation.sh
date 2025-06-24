#!/bin/bash

BASEDIR='/tmp/tests'

function init() {

    INIT_STATUS=0
    TARGETS=targets.json

    if [ $# -lt 1 ]; then 
        INIT_STATUS=1
        echo "Missing container image to use."
        echo "Use the script like ./test_audio_translation speech2text:test"
    fi

    if [ ! -d audio ]; then 
        INIT_STATUS=1
        echo "Missing audio -directory and test files!"
    else
        TEST_FILES=$(find audio/ -name '*.m4a' |wc -l)
        if [ "$TEST_FILES" -lt 1 ]; then
            INIT_STATUS=1
            echo "Missing audio files (m4a) for testing. Provide at least one."
        fi
    fi

    if [ ! -f "$TARGETS" ]; then
        INIT_STATUS=1
        echo "Missing $TARGETS, can't test without definitions!"
    else
        if ! jq empty "$TARGETS" > /dev/null 2>&1; then
            INIT_STATUS=1
            echo "$TARGETS is not a valid JSON file"
        fi

    fi

    return $INIT_STATUS
}

function prep_test_area() {

    if [ -d "$BASEDIR" ]; then
        rm -rf "$BASEDIR" || { echo "Failed to clean previous test directory"; return 1; }
    fi

    for SUBDIR in audio target; do
        mkdir -p "$BASEDIR/$SUBDIR" || { echo "Failed to create test directories"; return 1; }
    done

    for COPYTARGET in audio/*.m4a targets.json; do
        cp --parents "$COPYTARGET" "$BASEDIR" || { echo "Failed to copy $COPYTARGET files"; return 1; }
    done

}


#################################### LOGIC #####################################

init "$@" || { exit 1; }
prep_test_area || { exit 1; }

docker run -it \
    -v "$BASEDIR/audio":/audio \
    -v "$BASEDIR/target":/target \
    -v "$BASEDIR/targets.json":/targets.json \
    -v whisper_models:/var/models \
    -u "$(id -u "${USER}"):$(id -g "${USER}")" "$1" --test