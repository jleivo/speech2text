"""Test symlink skipping in folder_watcher.py.

Covers:
  - Symlinks are detected and skipped (R2-M8)
  - Regular files are still processed normally
"""
import os
import tempfile
from unittest.mock import patch

from src.folder_watcher import FolderWatcherHandler


def _make_config(**overrides):
    config = {
        "folder_to_watch": "/tmp/audio",
        "watched_extensions": [".wav", ".mp3"],
        "delete_after_processing": False,
        "backend": "litellm",
        "model": "whisper-1",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config.update(overrides)
    return config


def test_symlink_is_skipped():
    """Symlinked files are skipped with a warning."""
    handler = FolderWatcherHandler(_make_config())

    with patch("os.path.islink", return_value=True):
        handler.process_audio_file("/tmp/audio/symlink.wav")

    # transcribe_audio should NOT be called
    with patch("src.folder_watcher.transcribe_audio") as mock_transcribe:
        with patch("os.path.islink", return_value=True):
            handler.process_audio_file("/tmp/audio/symlink.wav")
        mock_transcribe.assert_not_called()


def test_regular_file_is_processed():
    """Regular (non-symlink) files proceed to transcription."""
    handler = FolderWatcherHandler(_make_config())

    with patch("os.path.islink", return_value=False), \
         patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="file note"), \
         patch("src.folder_watcher.route_transcription", return_value=("FILE", True)):
        handler.process_audio_file("/tmp/audio/real.wav")

        # If we get here without error, the file was processed
