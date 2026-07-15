"""Test SIGTERM handler and graceful shutdown in main.py.

Covers:
  - SIGTERM handler calls observer.stop()
  - observer.join() is called after stop()
"""
import json
import os
import signal
import tempfile
from unittest.mock import patch, MagicMock

from src.main import main


def _make_config_path(config):
    """Write config dict to a temp file and return path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        return f.name


def test_sigterm_stops_observer():
    """SIGTERM handler stops the watchdog observer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        script = os.path.join(tmpdir, "handler.py")
        with open(script, "w") as f:
            f.write("import sys; sys.exit(0)")
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": script}},
        }
        config_path = _make_config_path(config)

        with patch("src.main.Observer") as mock_observer_class, \
             patch("src.main.FolderWatcherHandler"):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer

            # After start(), send SIGTERM to the process
            def start_then_signal(*args, **kwargs):
                os.kill(os.getpid(), signal.SIGTERM)

            mock_observer.start.side_effect = start_then_signal

            main(config_path)

            mock_observer.stop.assert_called_once()


def test_sigterm_joins_observer():
    """SIGTERM handler joins the observer after stopping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        script = os.path.join(tmpdir, "handler.py")
        with open(script, "w") as f:
            f.write("import sys; sys.exit(0)")
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": script}},
        }
        config_path = _make_config_path(config)

        with patch("src.main.Observer") as mock_observer_class, \
             patch("src.main.FolderWatcherHandler"):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer

            def start_then_signal(*args, **kwargs):
                os.kill(os.getpid(), signal.SIGTERM)

            mock_observer.start.side_effect = start_then_signal

            main(config_path)

            mock_observer.join.assert_called_once()


def test_keyboard_interrupt_stops_observer():
    """KeyboardInterrupt (Ctrl+C) also stops the observer cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        script = os.path.join(tmpdir, "handler.py")
        with open(script, "w") as f:
            f.write("import sys; sys.exit(0)")
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": script}},
        }
        config_path = _make_config_path(config)

        with patch("src.main.Observer") as mock_observer_class, \
             patch("src.main.FolderWatcherHandler"):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer

            # Raise KeyboardInterrupt on start() to simulate Ctrl+C
            def start_then_interrupt(*args, **kwargs):
                raise KeyboardInterrupt

            mock_observer.start.side_effect = start_then_interrupt

            main(config_path)

            # Observer should still be stopped and joined in the finally block
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()
