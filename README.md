# Speech2Text

Watches a folder for audio files, transcribes them using LiteLLM (with local Whisper fallback), and routes the transcription to external scripts based on the first word (magic word).

## How It Works

1. Drop an audio file into the watched folder
2. The tool transcribes it (LiteLLM API or local Whisper)
3. The first word is matched against configured magic words
4. The matching script is called with the remaining text as an argument
5. If no magic word matches, the default action runs (if configured)

Example: saying "File buy groceries" triggers the FILE magic word's script with "buy groceries" as the argument.

## Setup

```bash
python3 -m venv .venv --prompt speech2text
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Edit `config/config.json`:

```json
{
    "folder_to_watch": "/tmp/audio",
    "watched_extensions": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
    "delete_after_processing": false,
    "transcription_log": "/tmp/speech2text.log",
    "backend": "litellm",
    "model": "whisper-1",
    "default_action": {
        "script_path": "path/to/default_handler.py"
    },
    "magic_words": {
        "FILE": {
            "script_path": "examples/create_note.py"
        }
    }
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `folder_to_watch` | Yes | - | Directory to monitor for audio files |
| `magic_words` | Yes | - | Map of trigger words to scripts |
| `watched_extensions` | No | .wav .mp3 .flac .m4a .ogg | Audio file extensions to process |
| `delete_after_processing` | No | false | Delete audio file after successful processing |
| `transcription_log` | No | - | Path to JSON-line log file |
| `backend` | No | litellm | Transcription backend (litellm or local) |
| `model` | No | whisper-1 | Model name (whisper-1 for LiteLLM, turbo/small/medium/large for local) |
| `default_action` | No | - | Script to run when no magic word matches |

## Writing Action Scripts

Scripts receive the transcribed text (with magic word stripped) as the first argument:

```python
#!/usr/bin/env python3
import sys

text = sys.argv[1]  # "buy groceries" (magic word already stripped)
# Do something with the text...
```

- Exit code 0 = success, non-zero = failure
- Scripts can be in any language, as long as they're executable
- See `examples/` for sample scripts

## Installing Handlers

Handlers in `handlers/` declare a `MANIFEST` describing their parameters.
The installer walks you through wiring one into `config.json` (interactive or
flag-driven), validates the result, and optionally updates the systemd
`ReadWritePaths` for handlers that write to disk.

```bash
# Interactive wizard
python scripts/install_handler.py

# Non-interactive
python scripts/install_handler.py \
    --handler journal_handler --word JOURNAL \
    --param destination=/srv/Obsidian/Archives/dailynotes --yes

# List handlers and installed words
python scripts/install_handler.py --list
```

See `docs/installer-usage.md` for the full workflow and
`docs/installer-setup.md` for the passwordless sudo setup the systemd step
needs.

## Running

```bash
python -m src.main
# or
python src/main.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for LiteLLM backend |
| `OPENAI_API_BASE` | Custom API base URL for LiteLLM |
| `LITELLM_BASE_URL` | LiteLLM server URL (for integration tests) |
| `LITELLM_MODEL` | Model override (for integration tests) |

## Testing

```bash
# Unit tests
pytest tests/ --ignore=tests/test_transcribe_integration.py

# Integration tests (requires LiteLLM server)
pytest tests/test_transcribe_integration.py -v
```

## Project Structure

```
src/
  main.py            # Entry point
  config.py          # Configuration loading and validation
  transcribe.py      # Audio transcription (LiteLLM + Whisper)
  router.py          # Magic word matching and script dispatch
  folder_watcher.py  # File system monitoring
  logger.py          # Transcription history logging
examples/            # Example action scripts
handlers/            # Built-in handlers (declare a MANIFEST for the installer)
scripts/             # Tooling (install_handler.py)
deploy/              # Deployment (systemd template, setup.sh, sudoers fragment)
config/              # Configuration files
tests/               # Unit and integration tests
```
# CI verified
