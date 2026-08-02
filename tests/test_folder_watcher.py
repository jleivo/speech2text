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


@patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None))
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
    mock_route.assert_called_once_with("file my note", config, source_file="/tmp/audio/test.wav")


@patch("src.folder_watcher.os.remove")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_deletes_file_when_configured(mock_wait, mock_transcribe, mock_route, mock_remove):
    """Audio file deleted after successful processing when configured."""
    config = _make_config(delete_after_processing=True)
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_remove.assert_called_once_with("/tmp/audio/test.wav")


@patch("src.folder_watcher.os.remove")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_keeps_file_when_not_configured(mock_wait, mock_transcribe, mock_route, mock_remove):
    """Audio file kept when delete_after_processing is false."""
    config = _make_config(delete_after_processing=False)
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_remove.assert_not_called()


@patch("src.folder_watcher.log_transcription")
@patch("src.folder_watcher.route_transcription", return_value=("FILE", True, None))
@patch("src.folder_watcher.transcribe_audio", return_value="file my note")
@patch("src.folder_watcher._wait_for_file_stable")
def test_logs_transcription(mock_wait, mock_transcribe, mock_route, mock_log):
    """Transcription is logged when transcription_log is configured."""
    config = _make_config(transcription_log="/tmp/test.log")
    handler = FolderWatcherHandler(config)

    handler.process_audio_file("/tmp/audio/test.wav")

    mock_log.assert_called_once_with(
        "/tmp/test.log", "/tmp/audio/test.wav", "file my note", "FILE", True,
        error=None,
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


def test_on_moved_detects_syncthing_files():
    """Files synced via Syncthing (rename pattern) are detected."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/tmp/audio/.syncthing.test.wav.tmp"
    event.dest_path = "/tmp/audio/test.wav"

    handler.on_moved(event)
    handler.process_audio_file.assert_called_once_with("/tmp/audio/test.wav")


def test_on_moved_ignores_directories():
    """Directory rename events are ignored."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = True
    event.src_path = "/tmp/audio/olddir"
    event.dest_path = "/tmp/audio/newdir"

    handler.on_moved(event)
    handler.process_audio_file.assert_not_called()


def test_on_moved_ignores_non_audio_extensions():
    """Non-audio file renames are ignored."""
    handler = FolderWatcherHandler(_make_config())
    handler.process_audio_file = MagicMock()

    event = MagicMock()
    event.is_directory = False
    event.src_path = "/tmp/audio/.syncthing.notes.txt.tmp"
    event.dest_path = "/tmp/audio/notes.txt"

    handler.on_moved(event)
    handler.process_audio_file.assert_not_called()
