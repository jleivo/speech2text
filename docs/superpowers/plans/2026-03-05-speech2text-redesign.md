# Speech2Text Redesign

## Overview

A minimal, modular speech-to-text tool that watches a folder for audio files,
transcribes them, and routes the transcription to external scripts based on the
first word (magic word).

## Architecture

### Core Pipeline

```
Folder Watcher -> Transcriber -> Magic Word Router -> External Script
```

### Modules

1. **main.py** - Entry point, loads config, starts watcher
2. **config.py** - Config loading and validation
3. **transcribe.py** - Backend-agnostic transcription (LiteLLM primary, local Whisper fallback)
4. **folder_watcher.py** - Watches folder for new audio files, dispatches to pipeline
5. **router.py** - Magic word matching, stripping, script dispatch
6. **logger.py** - Transcription history logging

## Design Decisions

- **All actions are external scripts** - no built-in actions. The core tool only
  does transcription and routing. This keeps the core simple and makes the system
  extensible without modifying the tool itself.
- **Magic word is stripped** before passing text to the script. If the user says
  "File this is my note", the script receives "this is my note".
- **Text passed as command-line argument** - scripts receive clean text as `sys.argv[1]`.
  Script exit code 0 = success, non-zero = failure.
- **Scripts explicitly registered** in config per magic word. No auto-discovery.
- **Default action** configurable for when no magic word matches. Receives full text.
- **LiteLLM as primary backend**, local Whisper as fallback. Backend configured globally.
- **API keys via environment variables only** - no secrets in config files.
- **File extensions configurable** with sane defaults (wav, mp3, flac, m4a, ogg).
- **Delete after processing** is configurable (default: false).
- **Transcription log** records timestamp, filename, text, action triggered, success/failure.
- **Error handling** is resilient - log errors and keep watching.

## Configuration

```json
{
  "folder_to_watch": "/tmp/audio",
  "watched_extensions": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
  "delete_after_processing": false,
  "transcription_log": "/tmp/speech2text.log",
  "backend": "litellm",
  "model": "whisper-1",
  "default_action": {
    "script_path": "/path/to/default_handler.py"
  },
  "magic_words": {
    "FILE": {
      "script_path": "/path/to/create_note.py"
    },
    "APPEND": {
      "script_path": "/path/to/append_log.py"
    }
  }
}
```

## Data Flow

1. Watcher detects new file with matching extension
2. Wait for file to be fully written (check file size stability)
3. Transcribe using configured backend (LiteLLM -> fall back to local Whisper)
4. Log transcription (timestamp, audio filename, full text, action triggered)
5. Extract first word, match against magic words (case-insensitive)
6. If match: strip magic word, call `python <script_path> "<remaining text>"`
7. If no match: call default action script with full text (if configured)
8. On error: log error, keep watching
9. If delete_after_processing is true and processing succeeded: delete audio file

## Transcription Backends

### LiteLLM (primary)
- Uses LiteLLM API to call whisper-compatible endpoints
- Model configurable (e.g. whisper-1 for OpenAI, or other providers)
- API keys via environment variables

### Local Whisper (fallback)
- Uses openai-whisper package directly
- Model size configurable (tiny, base, small, medium, large, turbo)
- Auto-detects CUDA/CPU

### Fallback Logic
- Try configured backend first
- If it fails (import error, network error, API error), fall back to local Whisper
- Log which backend was used

## Testing Strategy

- **Unit tests** with mocks for each module (transcriber, router, watcher, logger)
- **Integration tests** using existing test audio files (Finnish m4a recordings)
- **Audio transcription tests** against configurable LiteLLM server
  - Default server: `http://tuprpisrvp02.intra.leivo:4000`
  - Configurable via environment variable
- **Test scripts** - simple python scripts as mock actions for end-to-end testing
- **pytest** as test framework
