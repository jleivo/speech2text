"""Test file stability timeout in folder_watcher.py.

Covers:
  - _wait_for_file_stable returns True when file stabilizes
  - _wait_for_file_stable returns False on timeout (max_wait=30)
  - File that never stabilizes (constantly growing) triggers timeout
"""
import os
import tempfile
import time
from unittest.mock import patch, MagicMock

from src.folder_watcher import _wait_for_file_stable


def test_wait_for_file_stable_returns_true_when_stable():
    """Returns True when file size is stable for the required checks."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"fixed content")
        tmpfile = f.name

    try:
        result = _wait_for_file_stable(tmpfile, interval=0.1, checks=3, max_wait=30)
        assert result is True
    finally:
        os.unlink(tmpfile)


def test_wait_for_file_stable_returns_false_on_timeout():
    """Returns False when file never stabilizes within max_wait."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmpfile = f.name

    try:
        # Simulate a file that keeps growing by patching os.path.getsize
        size_counter = [0]
        def growing_size(path):
            size_counter[0] += 1
            return size_counter[0]

        with patch("os.path.getsize", side_effect=growing_size):
            result = _wait_for_file_stable(tmpfile, interval=0.05, checks=3, max_wait=0.3)
            assert result is False
    finally:
        if os.path.exists(tmpfile):
            os.unlink(tmpfile)


def test_wait_for_file_stable_default_max_wait_is_30():
    """Default max_wait parameter is 30 seconds."""
    # Verify function signature / default
    import inspect
    sig = inspect.signature(_wait_for_file_stable)
    assert sig.parameters["max_wait"].default == 30


def test_wait_for_file_stable_stabilizes_after_growing():
    """File that stops growing eventually stabilizes."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmpfile = f.name

    try:
        write_count = [0]
        def growing_then_stable(path):
            if write_count[0] < 3:
                write_count[0] += 1
                return write_count[0] * 100
            return 300  # stabilizes at 300

        with patch("os.path.getsize", side_effect=growing_then_stable):
            result = _wait_for_file_stable(tmpfile, interval=0.05, checks=3, max_wait=10)
            assert result is True
    finally:
        if os.path.exists(tmpfile):
            os.unlink(tmpfile)
