


# Speech2Text

Speech-to-text application that monitors a folder for new audio files, transcribes them using OpenAI Whisper, and performs actions based on "magic words" in the transcription.

## Features

- Monitors a user-defined folder for new audio files
- Transcribes audio to text using OpenAI Whisper
- Analyzes transcriptions for magic words that determine actions:
  - Create a new file with the content
  - Append content to an existing file
  - Send content via email
  - Execute a script with the content as input
- Handles failed transcriptions by moving files and notifying via email or script

## Setup

1. Clone this repository
2. Create and activate a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Configure the application by creating a JSON config file in the `config/` directory
5. Run the application: `python src/main.py`

## Configuration

Create a JSON configuration file in the `config/` directory with the following structure:

```json
{
  "folder_to_watch": "/path/to/folder",
  "failed": {
    "to": "/path/to/failed/files",
    "inform": "admin@example.com"  // OR
    "script": "/path/to/notify_script.sh"
  },
  "magic_words": {
    "FILE": {
      "action": "create_file",
      "file_path_template": "/path/to/output/{timestamp}.txt"
    },
    "APPEND": {
      "action": "append_to_file",
      "file_path": "/path/to/existing/file.txt"
    },
    "EMAIL": {
      "action": "send_email",
      "recipient": "user@example.com",
      "subject": "New transcription"
    },
    "SCRIPT": {
      "action": "execute_script",
      "script_path": "/path/to/script.py"
    }
  }
}
```

### Failed Transcription Handling

The `failed` configuration item is used to handle transcriptions that fail. It has the following structure:

- `to`: (required) The directory where failed audio files will be moved
- `inform`: (optional, one of these required) Email address to notify when a transcription fails
- `script`: (optional, one of these required) Script to execute when a transcription fails

For every translation that fails:
1. The audio file will be moved to the directory defined by the `to` field
2. Depending on the configuration, either an email will be sent to the person in the `inform` field or a script is run with the input message of "transcribing failed for file <name of the file>"

## Development

### Project Structure

- `src/`: Main application code
- `tests/`: Unit and integration tests
- `config/`: Configuration files
- `scripts/`: Example scripts for the SCRIPT action

### Running Tests

To run the tests, use the following command:

```bash
pytest tests/
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

