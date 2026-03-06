# Speech2Text Test Guide

## Overview

The test suite has 30 unit tests and 2 integration tests across 7 test files. Unit tests use mocks and run without external dependencies. Integration tests require a LiteLLM server.

## Running Tests

### Unit tests only (no external dependencies)

```bash
source .venv/bin/activate
pytest tests/ -v --ignore=tests/test_transcribe_integration.py
```

### All tests including integration

```bash
pytest tests/ -v
```

Integration tests are automatically skipped if the LiteLLM server is unreachable.

### Single test file

```bash
pytest tests/test_router.py -v
```

### Single test

```bash
pytest tests/test_router.py::test_route_matches_first_word -v
```

## Test Structure

```
tests/
  test_config.py                  # 6 tests - config loading and validation
  test_logger.py                  # 3 tests - transcription log writing
  test_transcribe.py              # 4 tests - transcription backends
  test_router.py                  # 7 tests - magic word matching and dispatch
  test_folder_watcher.py          # 8 tests - file monitoring pipeline
  test_main.py                    # 2 tests - entry point
  test_transcribe_integration.py  # 2 tests - real audio against LiteLLM server
  audio/                          # Test audio files (.m4a)
```

## Test Files in Detail

### test_config.py (6 tests)

Tests config loading, schema validation, and default value injection.

| Test | What it verifies |
|------|-----------------|
| `test_load_valid_config` | Full config with all fields loads correctly |
| `test_load_minimal_config_gets_defaults` | Missing optional fields get defaults (extensions, backend, model, delete flag) |
| `test_load_config_missing_file` | `FileNotFoundError` for nonexistent config path |
| `test_load_config_missing_folder_to_watch` | `ValidationError` when required field is missing |
| `test_load_config_missing_magic_words` | `ValidationError` when required field is missing |
| `test_load_config_magic_word_missing_script_path` | `ValidationError` when magic word has no `script_path` |

All tests write real JSON files to temp directories -- no mocking of file I/O.

### test_logger.py (3 tests)

Tests JSON-line log writing.

| Test | What it verifies |
|------|-----------------|
| `test_log_transcription_creates_file` | Log file created, record has all fields (timestamp, audio_file, transcription, action, success) |
| `test_log_transcription_appends` | Multiple entries written as separate lines |
| `test_log_transcription_no_action` | `action` field can be `None` |

Uses temp directories for isolation.

### test_transcribe.py (4 tests)

Tests transcription with mocked backends (no actual audio processing).

| Test | What it verifies |
|------|-----------------|
| `test_transcribe_litellm_success` | LiteLLM returns `response.text` |
| `test_transcribe_litellm_falls_back_to_whisper` | LiteLLM exception triggers local Whisper fallback |
| `test_transcribe_local_whisper_directly` | `backend="local"` uses Whisper directly |
| `test_transcribe_local_whisper_model_passed` | Model name propagated to `whisper.load_model()` |

Mocks: `litellm.transcription`, `whisper.load_model`, `builtins.open` (for LiteLLM test).

### test_router.py (7 tests)

Tests magic word matching, text stripping, and script dispatch.

| Test | What it verifies |
|------|-----------------|
| `test_route_matches_first_word` | First word matched, script called with stripped text |
| `test_route_case_insensitive` | "File" matches config key "FILE" |
| `test_route_no_match_uses_default` | Unmatched text dispatched to `default_action` with full text |
| `test_route_no_match_no_default` | No match + no default returns `(None, True)`, no script called |
| `test_route_script_failure` | Non-zero exit code returns `success=False` |
| `test_route_strips_only_first_word` | Internal whitespace in remaining text is preserved |
| `test_route_single_word_transcription` | Single word match passes empty string to script |

Mocks: `subprocess.run`.

### test_folder_watcher.py (8 tests)

Tests the full processing pipeline orchestration.

| Test | What it verifies |
|------|-----------------|
| `test_ignores_non_audio_files` | `.txt` files don't trigger processing |
| `test_ignores_directories` | Directory creation events are ignored |
| `test_detects_configured_extensions` | All 4 configured extensions are processed |
| `test_process_audio_full_pipeline` | Pipeline calls: wait -> transcribe(backend, model) -> route |
| `test_deletes_file_when_configured` | `os.remove` called when `delete_after_processing=True` |
| `test_keeps_file_when_not_configured` | `os.remove` NOT called when `delete_after_processing=False` |
| `test_logs_transcription` | `log_transcription` called with correct args when log path set |
| `test_handles_transcription_error` | Transcription exception caught, router not called |

Uses a `_make_config()` helper to build test configs with overrides.

Mocks: `_wait_for_file_stable`, `transcribe_audio`, `route_transcription`, `log_transcription`, `os.remove`.

### test_main.py (2 tests)

Tests the application entry point.

| Test | What it verifies |
|------|-----------------|
| `test_main_starts_observer` | Observer is created, scheduled, and started |
| `test_main_missing_config` | `FileNotFoundError` for missing config |

Uses `KeyboardInterrupt` side effect on `observer.start()` to break the infinite loop.

### test_transcribe_integration.py (2 tests)

Real audio transcription tests against a LiteLLM server.

| Test | What it verifies |
|------|-----------------|
| `test_transcribe_voice_001` | Finnish audio file 001 transcription contains "testitallennus" |
| `test_transcribe_voice_002` | Finnish audio file 002 transcription contains "testitallennus" |

**Prerequisites:**
- LiteLLM server running and accessible
- Test audio files in `tests/audio/`

**Configuration via environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_BASE_URL` | `http://tuprpisrvp02.intra.leivo:4000` | LiteLLM server URL |
| `LITELLM_MODEL` | `whisper-1` | Model to use for transcription |

**Skip behavior:** Tests are automatically skipped if the server health check fails (connection error or timeout). The skip reason is printed in the test output.

**Test audio files:**
- `tests/audio/Voice 001_W_20250624_111642.m4a` -- Finnish: "kone tama on testitallennus"
- `tests/audio/Voice 002_W_20250624_111750.m4a` -- Finnish: "ruokailu tama on toinen testitallennus"

## Adding New Tests

### For a new module

1. Create `tests/test_<module>.py`
2. Import from `src.<module>`
3. Mock external dependencies (file I/O, network, subprocess)
4. Run: `pytest tests/test_<module>.py -v`

### For a new magic word action script

Test the script independently:

```python
# tests/test_my_script.py
import subprocess

def test_my_script_success():
    result = subprocess.run(
        ["python", "examples/my_script.py", "test input"],
        capture_output=True, text=True
    )
    assert result.returncode == 0

def test_my_script_empty_input():
    result = subprocess.run(
        ["python", "examples/my_script.py", ""],
        capture_output=True, text=True
    )
    assert result.returncode == 0
```

### For integration tests with a different server

```bash
LITELLM_BASE_URL=http://my-server:4000 LITELLM_MODEL=whisper-1 \
    pytest tests/test_transcribe_integration.py -v
```

## Mocking Patterns

The codebase uses `unittest.mock.patch` consistently. Common patterns:

### Mock a module-level function

```python
from unittest.mock import patch

@patch("src.folder_watcher.transcribe_audio", return_value="hello")
def test_something(mock_transcribe):
    # transcribe_audio returns "hello" without calling the real function
    ...
```

### Mock with side effect (simulate errors)

```python
@patch("src.transcribe.litellm.transcription", side_effect=Exception("API error"))
def test_fallback(mock_litellm):
    # litellm.transcription raises, testing fallback behavior
    ...
```

### Mock subprocess

```python
from unittest.mock import MagicMock

@patch("src.router.subprocess.run")
def test_script_call(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    # Test that subprocess.run was called with expected args
    mock_run.assert_called_once_with(
        ["python", "/path/to/script.py", "text"],
        check=False,
    )
```

## CI Considerations

- Unit tests require no external services and run in ~4 seconds
- Integration tests need a LiteLLM server -- skip in CI unless you have one available
- Whisper model loading can use significant memory -- the unit tests mock this entirely
- Recommended CI command: `pytest tests/ -v --ignore=tests/test_transcribe_integration.py`
