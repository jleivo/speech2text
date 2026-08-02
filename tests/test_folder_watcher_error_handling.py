"""Test per-phase error handling in folder_watcher.process_audio_file.

Covers:
  - Route failure doesn't crash the watcher (caught in its own try/except)
  - Log failure doesn't crash the watcher
  - Delete failure doesn't crash the watcher
  - Each phase is independently protected
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

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


def test_route_failure_does_not_crash_watcher():
    """Route exception is caught; logging and deletion still proceed."""
    config = _make_config(transcription_log="/tmp/test.log")
    handler = FolderWatcherHandler(config)

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="file note"), \
         patch("src.folder_watcher.route_transcription", side_effect=RuntimeError("route boom")), \
         patch("src.folder_watcher.log_transcription") as mock_log, \
         patch("src.folder_watcher.os.remove") as mock_remove:
        # Should not raise
        handler.process_audio_file("/tmp/audio/test.wav")

        # Logging still attempted despite route failure
        mock_log.assert_called_once()


def test_log_failure_does_not_crash_watcher():
    """Log exception is caught; deletion still proceeds."""
    config = _make_config(delete_after_processing=True, transcription_log="/tmp/test.log")
    handler = FolderWatcherHandler(config)

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="file note"), \
         patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None)), \
         patch("src.folder_watcher.log_transcription", side_effect=IOError("log boom")), \
         patch("src.folder_watcher.os.remove") as mock_remove:
        # Should not raise
        handler.process_audio_file("/tmp/audio/test.wav")

        # Deletion still attempted despite log failure
        mock_remove.assert_called_once()


def test_delete_failure_does_not_crash_watcher():
    """os.remove exception is caught and logged."""
    config = _make_config(delete_after_processing=True)
    handler = FolderWatcherHandler(config)

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="file note"), \
         patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None)), \
         patch("src.folder_watcher.os.remove", side_effect=OSError("delete boom")):
        # Should not raise
        handler.process_audio_file("/tmp/audio/test.wav")


def test_file_not_deleted_when_no_action_matched():
    """File MUST NOT be deleted when no action handled the transcription.

    Regression guard: route_transcription returns (None, False) when nothing
    matched, so the file is preserved rather than silently destroyed (§164).
    """
    config = _make_config(delete_after_processing=True)
    handler = FolderWatcherHandler(config)

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="some unmatched words"), \
         patch("src.folder_watcher.route_transcription", return_value=(None, False, "no match")), \
         patch("src.folder_watcher.os.remove") as mock_remove:
        handler.process_audio_file("/tmp/audio/test.wav")

        mock_remove.assert_not_called()
