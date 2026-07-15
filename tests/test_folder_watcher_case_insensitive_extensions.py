"""Test case-insensitive extension matching in folder_watcher.py.

Covers:
  - Extensions matched case-insensitively (.WAV, .Mp3, .FLAC)
  - _match_extension is case-insensitive
"""
from unittest.mock import patch, MagicMock

from src.folder_watcher import FolderWatcherHandler


def _make_config(**overrides):
    config = {
        "folder_to_watch": "/tmp/audio",
        "watched_extensions": [".wav", ".mp3", ".flac", ".m4a"],
        "delete_after_processing": False,
        "backend": "litellm",
        "model": "whisper-1",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config.update(overrides)
    return config


def test_uppercase_extension_is_matched():
    """Upper-case extension (.WAV) is detected."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/tmp/audio/test.WAV"

    handler.on_created(event)
    handler.process_audio_file.assert_called_once()


def test_mixed_case_extension_is_matched():
    """Mixed-case extension (.Mp3) is detected."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/tmp/audio/test.Mp3"

    handler.on_created(event)
    handler.process_audio_file.assert_called_once()


def test_uppercase_extension_on_moved():
    """Upper-case extension is matched in on_moved events."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.dest_path = "/tmp/audio/test.FLAC"

    handler.on_moved(event)
    handler.process_audio_file.assert_called_once()


def test_match_extension_method():
    """_match_extension is case-insensitive for all variants."""
    handler = FolderWatcherHandler(_make_config())

    assert handler._match_extension("/tmp/test.wav") is True
    assert handler._match_extension("/tmp/test.WAV") is True
    assert handler._match_extension("/tmp/test.WaV") is True
    assert handler._match_extension("/tmp/test.MP3") is True
    assert handler._match_extension("/tmp/test.txt") is False
    assert handler._match_extension("/tmp/test.PDF") is False
