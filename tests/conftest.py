"""conftest.py — shared fixtures for speech2text tests.

Mocks heavy dependencies (whisper, torch) so tests that don't actually
exercise transcription can still collect and run.
"""
import sys
from unittest.mock import MagicMock

import pytest

# Mock whisper and torch before any module imports them,
# so that test collection doesn't fail when they aren't installed.
if "torch" not in sys.modules:
    sys.modules["torch"] = MagicMock()
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()


@pytest.fixture(autouse=True)
def _clear_transcribe_cache():
    """Clear the whisper model cache before each test to avoid cross-test pollution."""
    try:
        from src import transcribe
        transcribe._whisper_cache.clear()
    except ImportError:
        pass
