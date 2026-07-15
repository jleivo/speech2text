"""Test startup scan in main.py — processes pre-existing files in the watch directory.

Covers:
  - Pre-existing audio files are processed on startup
  - Non-matching files are skipped
  - Directories in the watch dir are skipped
  - OSError on listdir is caught and logged
"""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from src.main import _startup_scan


def _make_config(watch_dir, **overrides):
    config = {
        "folder_to_watch": watch_dir,
        "watched_extensions": [".wav", ".mp3"],
    }
    config.update(overrides)
    return config


def test_startup_scan_processes_pre_existing_files():
    """Startup scan processes all matching audio files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        # Create pre-existing files
        for name in ["note1.wav", "note2.mp3", "notes.txt"]:
            with open(os.path.join(watch_dir, name), "w") as f:
                f.write("fake audio")

        config = _make_config(watch_dir)
        mock_handler = MagicMock()

        _startup_scan(mock_handler, config)

        calls = [c[0][0] for c in mock_handler.process_audio_file.call_args_list]
        assert os.path.join(watch_dir, "note1.wav") in calls
        assert os.path.join(watch_dir, "note2.mp3") in calls
        assert len(calls) == 2  # .txt is skipped


def test_startup_scan_skips_subdirectories():
    """Subdirectories in watch dir are not processed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        os.makedirs(os.path.join(watch_dir, "subdir"))
        with open(os.path.join(watch_dir, "note.wav"), "w") as f:
            f.write("fake")

        config = _make_config(watch_dir)
        mock_handler = MagicMock()

        _startup_scan(mock_handler, config)

        assert mock_handler.process_audio_file.call_count == 1
        assert "note.wav" in mock_handler.process_audio_file.call_args[0][0]


def test_startup_scan_handles_os_error():
    """OSError during listdir is caught and does not raise."""
    mock_handler = MagicMock()
    config = {"folder_to_watch": "/nonexistent/dir", "watched_extensions": [".wav"]}

    # Should not raise
    _startup_scan(mock_handler, config)

    mock_handler.process_audio_file.assert_not_called()
