# Speech2Text User Guide

## Overview

Speech2Text watches a folder for audio files, transcribes them, and routes the transcription to external scripts based on the first word spoken. This lets you build voice-driven workflows -- say a trigger word followed by your content, and the tool dispatches it to the right script.

## Quick Start

### 1. Install

```bash
git clone <repo-url>
cd speech2text
python3 -m venv .venv --prompt speech2text
source .venv/bin/activate
pip install -r requirements.txt
sudo apt-get install ffmpeg -y
```

### 2. Configure

Edit `config/config.json`:

```json
{
    "folder_to_watch": "/tmp/audio",
    "magic_words": {
        "NOTE": {
            "script_path": "examples/create_note.py"
        }
    }
}
```

### 3. Set up your API key

#### Option A: HashiCorp Vault (recommended for production)

Add to your `config/config.json`:

```json
"vault_secret_path": "secret/hosts/<hostname>/litellm-speech2text",
"vault_service": "speech2text"
```

The app fetches the API key from Vault at startup. See `docs/SECRETS.md` for Vault setup.

#### Option B: Environment variable (for development)

```bash
export OPENAI_API_KEY="your-api-key"
```

If using a custom LiteLLM server:

```bash
export OPENAI_API_BASE="http://your-litellm-server:4000"
```

### 4. Run

```bash
python src/main.py
```

### 5. Use it

Drop an audio file into the watched folder. Say "Note buy groceries" and the tool will call `examples/create_note.py` with "buy groceries" as the argument.

## How It Works

```
Audio file appears in watched folder
        |
        v
Wait for file to finish writing
        |
        v
Transcribe (LiteLLM API, or local Whisper fallback)
        |
        v
Extract first word
        |
        v
Match against magic words (case-insensitive)
        |
    +---+---+
    |       |
  Match   No match
    |       |
    v       v
Strip    Run default action
magic    (if configured),
word,    passing full text
run
script
with
remaining
text
```

**Example:** You say "File this is my meeting summary"

1. Transcription: `"file this is my meeting summary"`
2. First word: `"file"` matches magic word `"FILE"`
3. Script receives: `"this is my meeting summary"` (magic word stripped)

## Configuration Reference

### Full config example

```json
{
    "folder_to_watch": "/tmp/audio",
    "watched_extensions": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
    "delete_after_processing": false,
    "transcription_log": "/tmp/speech2text.log",
    "backend": "litellm",
    "model": "whisper-1",
    "default_action": {
        "script_path": "scripts/default_handler.py"
    },
    "magic_words": {
        "FILE": {
            "script_path": "examples/create_note.py"
        },
        "APPEND": {
            "script_path": "examples/append_log.py"
        },
        "EMAIL": {
            "script_path": "scripts/send_email.py"
        }
    }
}
```

### Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `folder_to_watch` | Yes | -- | Directory to monitor for new audio files |
| `magic_words` | Yes | -- | Map of trigger words to action scripts |
| `watched_extensions` | No | .wav .mp3 .flac .m4a .ogg | File extensions to process |
| `delete_after_processing` | No | false | Delete audio file after successful processing |
| `transcription_log` | No | -- | Path to JSON-line log file |
| `backend` | No | litellm | Transcription backend: `litellm` or `local` |
| `model` | No | whisper-1 | Model name (see Transcription Backends below) |
| `default_action` | No | -- | Script to run when no magic word matches |

### Magic word rules

- Keys must be **uppercase letters only** (e.g., `FILE`, `NOTE`, `TODO`)
- Matching is case-insensitive (spoken "file", "File", or "FILE" all match `FILE`)
- Only the **first word** of the transcription is checked
- The first matching magic word wins -- order matters if words could overlap
- Each magic word maps to a `script_path`

## Transcription Backends

### LiteLLM (default)

Uses the LiteLLM API to access whisper-compatible transcription services (OpenAI, Azure, self-hosted, etc).

```json
{
    "backend": "litellm",
    "model": "whisper-1"
}
```

Required environment variable: `OPENAI_API_KEY`

Optional: `OPENAI_API_BASE` to point to a custom server.

If LiteLLM fails (network error, API error, etc.), the tool automatically falls back to local Whisper.

### Local Whisper

Uses OpenAI's open-source Whisper model running locally. Requires GPU for reasonable performance (falls back to CPU).

```json
{
    "backend": "local",
    "model": "turbo"
}
```

Available models (smallest to largest): `tiny`, `base`, `small`, `medium`, `large`, `turbo`

No API key needed. The model is downloaded on first use.

## Writing Action Scripts

Action scripts are regular Python scripts (or any executable) that receive the transcribed text as a command-line argument.

### Script interface

- **Input:** Text is passed as `sys.argv[1]` (magic word already stripped)
- **Output:** Exit code 0 = success, non-zero = failure
- **Language:** Any, as long as the script is callable with `python script.py "text"`

### Minimal example

```python
#!/usr/bin/env python3
import sys

text = sys.argv[1]
print(f"Received: {text}")
# Do something with the text...
```

### Practical example: save to file with timestamp

```python
#!/usr/bin/env python3
import os
import sys
from datetime import datetime

text = sys.argv[1] if len(sys.argv) > 1 else ""
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
path = f"/home/user/notes/{timestamp}.txt"

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    f.write(text)
```

### Practical example: send a notification

```python
#!/usr/bin/env python3
import subprocess
import sys

text = sys.argv[1] if len(sys.argv) > 1 else ""
subprocess.run(["notify-send", "Speech2Text", text])
```

### Practical example: add to a todo list

```python
#!/usr/bin/env python3
import sys

text = sys.argv[1] if len(sys.argv) > 1 else ""
with open("/home/user/todo.md", "a") as f:
    f.write(f"- [ ] {text}\n")
```

### Default action

If you want to handle transcriptions that don't match any magic word, configure a `default_action`. The default action receives the **full text** (nothing stripped):

```json
{
    "default_action": {
        "script_path": "scripts/catch_all.py"
    }
}
```

If no `default_action` is configured, unmatched transcriptions are silently ignored.

## Transcription Log

When `transcription_log` is set, every transcription is recorded as a JSON line:

```json
{"timestamp": "2026-03-06T10:30:00+00:00", "audio_file": "/tmp/audio/recording.wav", "transcription": "file buy groceries", "action": "FILE", "success": true}
```

Each record contains:
- `timestamp` -- UTC ISO 8601
- `audio_file` -- path to the audio file
- `transcription` -- full transcribed text
- `action` -- matched magic word (or `"default"`, or `null` if no match)
- `success` -- whether the script exited with code 0

You can query the log with standard tools:

```bash
# Recent transcriptions
tail -5 /tmp/speech2text.log | python3 -m json.tool

# Failed actions
grep '"success": false' /tmp/speech2text.log

# Count by action
cat /tmp/speech2text.log | python3 -c "
import sys, json, collections
counts = collections.Counter(json.loads(l)['action'] for l in sys.stdin)
for k, v in counts.most_common(): print(f'{k}: {v}')
"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For LiteLLM | API key for the transcription service |
| `OPENAI_API_BASE` | No | Custom API base URL (for self-hosted LiteLLM) |

## File Handling

- The watcher waits for files to finish writing before processing (checks file size stability)
- Only files with configured extensions are processed
- When `delete_after_processing` is true, audio files are deleted only after **successful** processing
- On error, the audio file is always kept and the watcher continues

## Troubleshooting

**"Config file not found"** -- Make sure `config/config.json` exists and the path is correct. The default path is relative to where you run the command.

**Transcription is empty or wrong** -- Try a different model. For local Whisper, `turbo` is the fastest but `medium` or `large` may be more accurate. For LiteLLM, check your API key and server URL.

**Script not executing** -- Check that the `script_path` is correct (relative to working directory or absolute). Check script permissions. Look at the console output for error messages.

**Audio file not detected** -- Verify the file extension is in `watched_extensions`. Check that the file is being written to the correct `folder_to_watch` directory.

**LiteLLM falls back to local Whisper** -- This means the LiteLLM API call failed. Check `OPENAI_API_KEY` and `OPENAI_API_BASE`. The fallback uses the `turbo` model by default.
