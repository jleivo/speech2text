# Speech2Text Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild speech2text as a minimal pipeline: watch folder -> transcribe (LiteLLM/Whisper) -> route by first word -> call external script.

**Architecture:** Folder watcher detects audio files, transcriber uses LiteLLM with local Whisper fallback, router matches first word against magic words and dispatches to external scripts with stripped text as argv[1]. All actions are external scripts - no built-in actions.

**Tech Stack:** Python 3, watchdog, litellm, openai-whisper (fallback), jsonschema, pytest

**Design doc:** `docs/plans/2026-03-05-speech2text-redesign.md`

---

### Task 1: Clean slate - remove old source files, update requirements

We're rewriting all modules. Remove old source and test files, update dependencies.

**Files:**
- Delete: `src/actions.py`
- Delete: `src/config.py`
- Delete: `src/main.py`
- Delete: `src/transcribe.py`
- Delete: `src/folder_watcher.py`
- Delete: `tests/test_actions.py`
- Delete: `tests/test_config.py`
- Delete: `tests/test_folder_watcher.py`
- Delete: `tests/test_transcribe.py`
- Delete: `tests/test_transcribe_m4a.py`
- Delete: `tests/test_transcribe_audio_files.py`
- Delete: `tests/test_main.py`
- Delete: `tests/test_update_config.py`
- Delete: `scripts/update_config.py`
- Modify: `requirements.txt`
- Keep: `tests/audio/` (test audio files)
- Keep: `src/__init__.py`, `tests/__init__.py`

**Step 1: Remove old source and test files**

```bash
rm src/actions.py src/config.py src/main.py src/transcribe.py src/folder_watcher.py
rm tests/test_actions.py tests/test_config.py tests/test_folder_watcher.py
rm tests/test_transcribe.py tests/test_transcribe_m4a.py tests/test_transcribe_audio_files.py
rm tests/test_main.py tests/test_update_config.py
rm scripts/update_config.py
```

**Step 2: Update requirements.txt**

```
watchdog
pytest
jsonschema
litellm
openai-whisper
torch
```

**Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 4: Commit**

```bash
git add -A && git commit -m "chore: clean slate for speech2text redesign"
```

---

### Task 2: Config module

The config module loads and validates JSON configuration. New schema supports: folder_to_watch, watched_extensions (with defaults), delete_after_processing, transcription_log, backend, model, default_action, and magic_words where each word maps to a script_path.

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

```python
# tests/test_config.py
import json
import os
import tempfile
import pytest
import jsonschema
from src.config import load_config, DEFAULT_EXTENSIONS


def test_load_valid_config():
    """Full valid config loads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        valid = {
            "folder_to_watch": "/tmp/audio",
            "watched_extensions": [".wav", ".mp3"],
            "delete_after_processing": True,
            "transcription_log": "/tmp/speech2text.log",
            "backend": "litellm",
            "model": "whisper-1",
            "default_action": {"script_path": "/usr/local/bin/default.py"},
            "magic_words": {
                "FILE": {"script_path": "/usr/local/bin/file_handler.py"},
                "APPEND": {"script_path": "/usr/local/bin/append_handler.py"},
            },
        }
        with open(config_path, "w") as f:
            json.dump(valid, f)

        config = load_config(config_path)
        assert config == valid


def test_load_minimal_config_gets_defaults():
    """Minimal config gets default values filled in."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        minimal = {
            "folder_to_watch": "/tmp/audio",
            "magic_words": {
                "FILE": {"script_path": "/usr/local/bin/file_handler.py"}
            },
        }
        with open(config_path, "w") as f:
            json.dump(minimal, f)

        config = load_config(config_path)
        assert config["watched_extensions"] == DEFAULT_EXTENSIONS
        assert config["delete_after_processing"] is False
        assert config["backend"] == "litellm"
        assert config["model"] == "whisper-1"


def test_load_config_missing_file():
    """Missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_load_config_missing_folder_to_watch():
    """Config without folder_to_watch fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {"magic_words": {"FILE": {"script_path": "/bin/handler.py"}}}
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)


def test_load_config_missing_magic_words():
    """Config without magic_words fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {"folder_to_watch": "/tmp/audio"}
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)


def test_load_config_magic_word_missing_script_path():
    """Magic word without script_path fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {
            "folder_to_watch": "/tmp/audio",
            "magic_words": {"FILE": {}},
        }
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL with ImportError (module doesn't exist)

**Step 3: Write minimal implementation**

```python
# src/config.py
import json
import jsonschema

DEFAULT_EXTENSIONS = [".wav", ".mp3", ".flac", ".m4a", ".ogg"]

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "folder_to_watch": {"type": "string"},
        "watched_extensions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "delete_after_processing": {"type": "boolean"},
        "transcription_log": {"type": "string"},
        "backend": {"type": "string"},
        "model": {"type": "string"},
        "default_action": {
            "type": "object",
            "properties": {"script_path": {"type": "string"}},
            "required": ["script_path"],
        },
        "magic_words": {
            "type": "object",
            "patternProperties": {
                "^[A-Z]+$": {
                    "type": "object",
                    "properties": {"script_path": {"type": "string"}},
                    "required": ["script_path"],
                }
            },
            "additionalProperties": False,
        },
    },
    "required": ["folder_to_watch", "magic_words"],
}

DEFAULTS = {
    "watched_extensions": DEFAULT_EXTENSIONS,
    "delete_after_processing": False,
    "backend": "litellm",
    "model": "whisper-1",
}


def load_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)

    jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)

    for key, value in DEFAULTS.items():
        config.setdefault(key, value)

    return config
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py && git commit -m "feat: add config module with schema validation and defaults"
```

---

### Task 3: Logger module

Simple module that appends transcription records to a log file. Each record is a JSON line with timestamp, audio filename, transcription text, action triggered, and success status.

**Files:**
- Create: `src/logger.py`
- Create: `tests/test_logger.py`

**Step 1: Write the failing tests**

```python
# tests/test_logger.py
import json
import os
import tempfile
from src.logger import log_transcription


def test_log_transcription_creates_file():
    """Log file is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.log")
        log_transcription(log_path, "test.wav", "hello world", "FILE", True)

        assert os.path.exists(log_path)
        with open(log_path) as f:
            record = json.loads(f.readline())
        assert record["audio_file"] == "test.wav"
        assert record["transcription"] == "hello world"
        assert record["action"] == "FILE"
        assert record["success"] is True
        assert "timestamp" in record


def test_log_transcription_appends():
    """Multiple log entries are appended as separate lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.log")
        log_transcription(log_path, "a.wav", "first", "FILE", True)
        log_transcription(log_path, "b.wav", "second", "APPEND", False)

        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["audio_file"] == "a.wav"
        assert json.loads(lines[1])["audio_file"] == "b.wav"


def test_log_transcription_no_action():
    """Action can be None when no magic word matched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.log")
        log_transcription(log_path, "test.wav", "hello", None, True)

        with open(log_path) as f:
            record = json.loads(f.readline())
        assert record["action"] is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_logger.py -v
```

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/logger.py
import json
from datetime import datetime, timezone


def log_transcription(log_path, audio_file, transcription, action, success):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audio_file": audio_file,
        "transcription": transcription,
        "action": action,
        "success": success,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_logger.py -v
```

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/logger.py tests/test_logger.py && git commit -m "feat: add logger module for transcription history"
```

---

### Task 4: Transcribe module

Backend-agnostic transcription. Tries LiteLLM first, falls back to local Whisper. Both backend and model are configurable.

**Files:**
- Create: `src/transcribe.py`
- Create: `tests/test_transcribe.py`

**Step 1: Write the failing tests**

```python
# tests/test_transcribe.py
import pytest
from unittest.mock import patch, MagicMock
from src.transcribe import transcribe_audio


def test_transcribe_litellm_success():
    """LiteLLM backend returns transcription on success."""
    mock_response = MagicMock()
    mock_response.text = "hello world"

    with patch("src.transcribe.litellm.transcription", return_value=mock_response):
        result = transcribe_audio("/tmp/test.wav", backend="litellm", model="whisper-1")

    assert result == "hello world"


def test_transcribe_litellm_falls_back_to_whisper():
    """When LiteLLM fails, falls back to local Whisper."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "fallback text"}

    with patch("src.transcribe.litellm.transcription", side_effect=Exception("API error")):
        with patch("src.transcribe.whisper.load_model", return_value=mock_model):
            result = transcribe_audio(
                "/tmp/test.wav", backend="litellm", model="whisper-1"
            )

    assert result == "fallback text"


def test_transcribe_local_whisper_directly():
    """Local whisper backend works when configured."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "local text"}

    with patch("src.transcribe.whisper.load_model", return_value=mock_model):
        result = transcribe_audio(
            "/tmp/test.wav", backend="local", model="turbo"
        )

    assert result == "local text"


def test_transcribe_local_whisper_model_passed():
    """Local whisper loads the configured model size."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "text"}

    with patch("src.transcribe.whisper.load_model", return_value=mock_model) as mock_load:
        transcribe_audio("/tmp/test.wav", backend="local", model="small")

    mock_load.assert_called_once_with("small")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_transcribe.py -v
```

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/transcribe.py
import logging

import litellm
import whisper

logger = logging.getLogger(__name__)


def transcribe_audio(file_path, backend="litellm", model="whisper-1"):
    if backend == "litellm":
        try:
            return _transcribe_litellm(file_path, model)
        except Exception as e:
            logger.warning("LiteLLM failed (%s), falling back to local Whisper", e)
            return _transcribe_local(file_path, model="turbo")
    else:
        return _transcribe_local(file_path, model)


def _transcribe_litellm(file_path, model):
    with open(file_path, "rb") as audio_file:
        response = litellm.transcription(model=model, file=audio_file)
    return response.text


def _transcribe_local(file_path, model):
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(file_path, language=None)
    return result["text"]
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_transcribe.py -v
```

Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/transcribe.py tests/test_transcribe.py && git commit -m "feat: add transcribe module with LiteLLM and Whisper fallback"
```

---

### Task 5: Router module

Matches first word of transcription against magic words. Strips the magic word and calls the external script with clean text as argv[1]. Falls back to default action if no match.

**Files:**
- Create: `src/router.py`
- Create: `tests/test_router.py`

**Step 1: Write the failing tests**

```python
# tests/test_router.py
import subprocess
from unittest.mock import patch, MagicMock
from src.router import route_transcription


def test_route_matches_first_word():
    """First word matches magic word, script called with stripped text."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/usr/local/bin/file_handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("file this is my note", config)

    mock_run.assert_called_once_with(
        ["python", "/usr/local/bin/file_handler.py", "this is my note"],
        check=False,
    )
    assert result == ("FILE", True)


def test_route_case_insensitive():
    """Magic word matching is case-insensitive."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("File this is my note", config)

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", "this is my note"],
        check=False,
    )
    assert result == ("FILE", True)


def test_route_no_match_uses_default():
    """No magic word match falls back to default action with full text."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
        "default_action": {"script_path": "/bin/default.py"},
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("hello world", config)

    mock_run.assert_called_once_with(
        ["python", "/bin/default.py", "hello world"],
        check=False,
    )
    assert result == ("default", True)


def test_route_no_match_no_default():
    """No match and no default action returns None."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        result = route_transcription("hello world", config)

    mock_run.assert_not_called()
    assert result == (None, True)


def test_route_script_failure():
    """Script returning non-zero exit code reports failure."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = route_transcription("file my note", config)

    assert result == ("FILE", False)


def test_route_strips_only_first_word():
    """Only the first word is stripped, rest preserved exactly."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file   extra   spaces   here", config)

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", "extra   spaces   here"],
        check=False,
    )


def test_route_single_word_transcription():
    """Single word transcription that matches sends empty string."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file", config)

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", ""],
        check=False,
    )
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_router.py -v
```

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/router.py
import logging
import subprocess

logger = logging.getLogger(__name__)


def route_transcription(transcription, config):
    words = transcription.split(None, 1)
    first_word = words[0] if words else ""
    remaining = words[1] if len(words) > 1 else ""

    for keyword, word_config in config["magic_words"].items():
        if first_word.upper() == keyword.upper():
            success = _run_script(word_config["script_path"], remaining)
            return (keyword, success)

    if "default_action" in config:
        success = _run_script(config["default_action"]["script_path"], transcription)
        return ("default", success)

    return (None, True)


def _run_script(script_path, text):
    logger.info("Running script %s", script_path)
    result = subprocess.run(["python", script_path, text], check=False)
    if result.returncode != 0:
        logger.error("Script %s failed with return code %d", script_path, result.returncode)
        return False
    return True
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_router.py -v
```

Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/router.py tests/test_router.py && git commit -m "feat: add router module for magic word matching and script dispatch"
```

---

### Task 6: Folder watcher module

Watches a folder for new audio files. On detection, waits for file stability, transcribes, routes, logs, and optionally deletes the file.

**Files:**
- Create: `src/folder_watcher.py`
- Create: `tests/test_folder_watcher.py`

**Step 1: Write the failing tests**

```python
# tests/test_folder_watcher.py
import tempfile
from unittest.mock import MagicMock, patch, call
from src.folder_watcher import FolderWatcherHandler


def _make_config(**overrides):
    config = {
        "folder_to_watch": "/tmp/audio",
        "watched_extensions": [".wav", ".mp3", ".flac", ".m4a"],
        "delete_after_processing": False,
        "backend": "litellm",
        "model": "whisper-1",
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }
    config.update(overrides)
    return config


def test_ignores_non_audio_files():
    """Non-audio files are ignored."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/tmp/audio/notes.txt"

    handler.on_created(event)
    handler.process_audio_file.assert_not_called()


def test_ignores_directories():
    """Directory creation events are ignored."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = True
    event.src_path = "/tmp/audio/subdir"

    handler.on_created(event)
    handler.process_audio_file.assert_not_called()


def test_detects_configured_extensions():
    """Audio files with configured extensions are processed."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    for ext in [".wav", ".mp3", ".flac", ".m4a"]:
        event = MagicMock()
        event.is_directory = False
        event.src_path = f"/tmp/audio/test{ext}"
        handler.on_created(event)

    assert handler.process_audio_file.call_count == 4


@patch("src.folder_watcher.route_transcription", return_value=("FILE", True))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_process_audio_full_pipeline(mock_wait, mock_transcribe, mock_route):
    """Full pipeline: wait -> transcribe -> route."""
    config = _make_config()
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_wait.assert_called_once_with("/tmp/audio/test.wav")
    mock_transcribe.assert_called_once_with(
        "/tmp/audio/test.wav", backend="litellm", model="whisper-1"
    )
    mock_route.assert_called_once_with("file my note", config)


@patch("src.folder_watcher.os.remove")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_deletes_file_when_configured(mock_wait, mock_transcribe, mock_route, mock_remove):
    """Audio file deleted after successful processing when configured."""
    config = _make_config(delete_after_processing=True)
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_remove.assert_called_once_with("/tmp/audio/test.wav")


@patch("src.folder_watcher.os.remove")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_keeps_file_when_not_configured(mock_wait, mock_transcribe, mock_route, mock_remove):
    """Audio file kept when delete_after_processing is false."""
    config = _make_config(delete_after_processing=False)
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_remove.assert_not_called()


@patch("src.folder_watcher.log_transcription")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_logs_transcription(mock_wait, mock_transcribe, mock_route, mock_log):
    """Transcription is logged when transcription_log is configured."""
    config = _make_config(transcription_log="/tmp/test.log")
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_log.assert_called_once_with(
        "/tmp/test.log", "/tmp/audio/test.wav", "file my note", "FILE", True
    )


@patch("src.folder_watcher.route_transcription")
@patch("src.folder_watcher.transcribe_audio", side_effect=Exception("transcription failed"))
@patch("src.folder_watcher._wait_for_file_stable")
def test_handles_transcription_error(mock_wait, mock_transcribe, mock_route):
    """Transcription error is caught and logged, processing continues."""
    config = _make_config()
    handler = FolderWatcherHandler(config)

    # Should not raise
    handler.process_audio_file("/tmp/audio/test.wav")

    mock_route.assert_not_called()
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_folder_watcher.py -v
```

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/folder_watcher.py
import logging
import os
import time

from watchdog.events import FileSystemEventHandler

from src.logger import log_transcription
from src.router import route_transcription
from src.transcribe import transcribe_audio

logger = logging.getLogger(__name__)


def _wait_for_file_stable(file_path, interval=0.5, checks=3):
    previous_size = -1
    stable_count = 0
    while stable_count < checks:
        current_size = os.path.getsize(file_path)
        if current_size == previous_size:
            stable_count += 1
        else:
            stable_count = 0
        previous_size = current_size
        time.sleep(interval)


class FolderWatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.extensions = tuple(config.get("watched_extensions", []))

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(self.extensions):
            return
        logger.info("New audio file detected: %s", event.src_path)
        self.process_audio_file(event.src_path)

    def process_audio_file(self, file_path):
        try:
            _wait_for_file_stable(file_path)
            transcription = transcribe_audio(
                file_path,
                backend=self.config["backend"],
                model=self.config["model"],
            )
        except Exception:
            logger.exception("Failed to transcribe %s", file_path)
            return

        action, success = route_transcription(transcription, self.config)

        log_path = self.config.get("transcription_log")
        if log_path:
            log_transcription(log_path, file_path, transcription, action, success)

        if self.config.get("delete_after_processing") and success:
            os.remove(file_path)
            logger.info("Deleted %s", file_path)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_folder_watcher.py -v
```

Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add src/folder_watcher.py tests/test_folder_watcher.py && git commit -m "feat: add folder watcher with configurable extensions and file cleanup"
```

---

### Task 7: Main entry point

Loads config, sets up logging, starts the watchdog observer.

**Files:**
- Create: `src/main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing tests**

```python
# tests/test_main.py
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.main import main


@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_starts_observer(mock_handler_class, mock_observer_class):
    """Main starts observer on configured folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        mock_observer.start.side_effect = KeyboardInterrupt

        main(config_path)

        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()


def test_main_missing_config():
    """Main raises FileNotFoundError for missing config."""
    import pytest
    with pytest.raises(FileNotFoundError):
        main("/nonexistent/config.json")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/main.py
import logging
import time

from watchdog.observers import Observer

from src.config import load_config
from src.folder_watcher import FolderWatcherHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main(config_path="config/config.json"):
    config = load_config(config_path)

    handler = FolderWatcherHandler(config)
    observer = Observer()
    observer.schedule(handler, path=config["folder_to_watch"], recursive=False)

    logger.info("Watching %s for audio files...", config["folder_to_watch"])
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add src/main.py tests/test_main.py && git commit -m "feat: add main entry point with observer setup"
```

---

### Task 8: Audio integration tests against LiteLLM server

Integration tests that transcribe real audio files against a configurable LiteLLM server. Skipped when the server is not available.

**Files:**
- Create: `tests/test_transcribe_integration.py`

**Step 1: Write the integration tests**

```python
# tests/test_transcribe_integration.py
import os
import pytest
import requests
from src.transcribe import transcribe_audio

LITELLM_BASE_URL = os.environ.get(
    "LITELLM_BASE_URL", "http://tuprpisrvp02.intra.leivo:4000"
)
LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "whisper-1")


def _server_available():
    try:
        requests.get(f"{LITELLM_BASE_URL}/health", timeout=3)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


skip_no_server = pytest.mark.skipif(
    not _server_available(),
    reason=f"LiteLLM server not available at {LITELLM_BASE_URL}",
)


@skip_no_server
def test_transcribe_voice_001():
    """Transcribe Finnish test audio file 001 via LiteLLM."""
    os.environ.setdefault("OPENAI_API_BASE", LITELLM_BASE_URL)

    audio_path = os.path.join(
        os.path.dirname(__file__), "audio", "Voice 001_W_20250624_111642.m4a"
    )
    result = transcribe_audio(audio_path, backend="litellm", model=LITELLM_MODEL)

    assert "testitallennus" in result.lower()


@skip_no_server
def test_transcribe_voice_002():
    """Transcribe Finnish test audio file 002 via LiteLLM."""
    os.environ.setdefault("OPENAI_API_BASE", LITELLM_BASE_URL)

    audio_path = os.path.join(
        os.path.dirname(__file__), "audio", "Voice 002_W_20250624_111750.m4a"
    )
    result = transcribe_audio(audio_path, backend="litellm", model=LITELLM_MODEL)

    assert "testitallennus" in result.lower()
```

**Step 2: Run tests**

```bash
pytest tests/test_transcribe_integration.py -v
```

Expected: Tests PASS if LiteLLM server is available, SKIP otherwise.

Note: The `OPENAI_API_BASE` env var tells litellm where to route requests. If the LiteLLM server requires an API key, set `OPENAI_API_KEY` env var. The exact env var and litellm.transcription() call parameters may need adjustment based on how the LiteLLM server is configured — adjust in implementation if needed.

**Step 3: Add requests to requirements.txt**

Add `requests` to `requirements.txt` (needed for the health check in integration tests).

**Step 4: Commit**

```bash
git add tests/test_transcribe_integration.py requirements.txt && git commit -m "test: add audio integration tests against LiteLLM server"
```

---

### Task 9: Update config file and README

Update the sample config and documentation to reflect the new architecture.

**Files:**
- Modify: `config/config.json`
- Modify: `README.md`

**Step 1: Update config/config.json**

```json
{
    "folder_to_watch": "/tmp/audio",
    "watched_extensions": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
    "delete_after_processing": false,
    "transcription_log": "/tmp/speech2text.log",
    "backend": "litellm",
    "model": "whisper-1",
    "magic_words": {
        "FILE": {
            "script_path": "examples/create_note.py"
        },
        "APPEND": {
            "script_path": "examples/append_log.py"
        }
    }
}
```

**Step 2: Create example scripts**

Create `examples/create_note.py`:

```python
#!/usr/bin/env python3
"""Example action script: creates a timestamped note file."""
import sys
from datetime import datetime

text = sys.argv[1] if len(sys.argv) > 1 else ""
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
path = f"/tmp/notes/{timestamp}.txt"

import os
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    f.write(text)
print(f"Created note: {path}")
```

Create `examples/append_log.py`:

```python
#!/usr/bin/env python3
"""Example action script: appends text to a log file."""
import sys

text = sys.argv[1] if len(sys.argv) > 1 else ""
log_path = "/tmp/notes/log.txt"

import os
os.makedirs(os.path.dirname(log_path), exist_ok=True)
with open(log_path, "a") as f:
    f.write(text + "\n")
print(f"Appended to: {log_path}")
```

**Step 3: Update README.md**

Write a concise README covering:
- What the tool does (one paragraph)
- Installation (`pip install -r requirements.txt`)
- Configuration (reference config/config.json, explain each field)
- Writing action scripts (script receives text as argv[1], exit 0 for success)
- Running (`python -m src.main` or `python src/main.py`)
- Environment variables (OPENAI_API_KEY, LITELLM_BASE_URL for custom server)
- Testing (`pytest` for unit tests, integration tests need LiteLLM server)

**Step 4: Run all tests to verify nothing is broken**

```bash
pytest tests/ -v --ignore=tests/test_transcribe_integration.py
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add config/config.json examples/ README.md && git commit -m "docs: update config, add example scripts, update README"
```

---

### Task 10: Final cleanup and full test run

Remove any leftover files, run full test suite, verify everything works.

**Files:**
- Delete: `Readme.md` (old duplicate)
- Delete: `plan.md` (old plan, superseded by docs/plans/)
- Delete: `.openhands/` (AI agent config, no longer needed)

**Step 1: Clean up old files**

```bash
rm -f Readme.md plan.md
rm -rf .openhands/
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All unit tests PASS, integration tests SKIP if no server

**Step 3: Commit**

```bash
git add -A && git commit -m "chore: remove old files, final cleanup"
```
