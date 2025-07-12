
# Speech2Text Tests

This directory contains test files and scripts for testing the speech-to-text functionality of the application.

## Directory Structure

- `audio/`: Contains audio files (m4a format) used for testing along with their corresponding text transcriptions.
- `targets.json`: JSON file defining test configurations.
- `test_audio_translation.sh`: Shell script to run tests using Docker.

## Test Configuration (`targets.json`)

The `targets.json` file defines different test scenarios. Each key in the object represents a test configuration with various options:

```json
{
  "default": { "keepaudiofile": ".", "transcript": "." },
  "kone": { "keepaudiofile": ".", "transcript": ".", "filename":"kone.txt" },
  "ruokailu": { "keepaudiofile": false, "transcript": ".", "filename":"ruokailu.txt", "timestamp": true }
}
```

- `keepaudiofile`: Whether to keep the audio file after processing (false) or specify a directory (e.g., "." for current directory).
- `transcript`: Directory where transcriptions will be saved.
- `filename`: Custom filename for the transcription output.
- `timestamp`: Whether to include timestamps in the transcription.

## Running Tests

The tests are run using Docker with the shell script `test_audio_translation.sh`. The script:

1. Validates that required files and directories exist
2. Sets up a test area in `/tmp/tests`
3. Runs a Docker container with the specified image, mounting the necessary files and directories

To run the tests, use the following command (replace `speech2text:test` with your actual Docker image):

```bash
./test_audio_translation.sh speech2text:test
```

## Test Files

The audio directory contains pairs of `.m4a` audio files and corresponding `.txt` transcription files. These are used as reference outputs for testing the accuracy of the speech-to-text processing.
