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
