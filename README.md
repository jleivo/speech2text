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

## Setup

1. Clone this repository
2. Create and activate a virtual environment: `python3 -m venv .venv --prompt "speech2text"`
3. Install dependencies: `pip install -r requirements.txt`
4. Configure the application by creating a JSON config file in the `config/` directory
5. Run the application: `python src/main.py`

## Configuration

Create a JSON configuration file in the `config/` directory with the following structure:

```json
{
  "folder_to_watch": "/path/to/folder",
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

