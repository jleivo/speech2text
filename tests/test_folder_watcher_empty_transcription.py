"""Test empty/whitespace transcription handling in folder_watcher.py.

Covers:
  - Empty string transcription is skipped
  - Whitespace-only transcription is skipped
  - Non-empty transcription proceeds to routing
"""
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


def test_empty_transcription_is_skipped():
    """Empty string transcription skips routing."""
    handler = FolderWatcherHandler(_make_config())

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value=""), \
         patch("src.folder_watcher.route_transcription") as mock_route:
        handler.process_audio_file("/tmp/audio/test.wav")
        mock_route.assert_not_called()


def test_whitespace_only_transcription_is_skipped():
    """Whitespace-only transcription skips routing."""
    handler = FolderWatcherHandler(_make_config())

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="   \n\t  "), \
         patch("src.folder_watcher.route_transcription") as mock_route:
        handler.process_audio_file("/tmp/audio/test.wav")
        mock_route.assert_not_called()


def test_none_transcription_is_skipped():
    """None transcription skips routing."""
    handler = FolderWatcherHandler(_make_config())

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value=None), \
         patch("src.folder_watcher.route_transcription") as mock_route:
        handler.process_audio_file("/tmp/audio/test.wav")
        mock_route.assert_not_called()


def test_valid_transcription_proceeds_to_route():
    """Non-empty transcription is routed."""
    handler = FolderWatcherHandler(_make_config())

    with patch("src.folder_watcher._wait_for_file_stable", return_value=True), \
         patch("src.folder_watcher.transcribe_audio", return_value="file my note"), \
         patch("src.folder_watcher.route_transcription") as mock_route:
        handler.process_audio_file("/tmp/audio/test.wav")
        mock_route.assert_called_once()
