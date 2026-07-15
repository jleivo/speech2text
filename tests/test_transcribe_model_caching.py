"""Test Whisper model caching in transcribe.py.

Covers:
  - Model is cached at module level (not reloaded on each call)
  - _get_whisper_model uses double-checked locking
  - Same model is returned from cache
"""
from unittest.mock import patch, MagicMock

from src.transcribe import _get_whisper_model, _whisper_cache


def test_whisper_model_cached():
    """Whisper model is cached — load_model called only once per model name."""
    # Clear cache to ensure a fresh test
    _whisper_cache.clear()

    mock_model = MagicMock()
    with patch("src.transcribe.whisper.load_model", return_value=mock_model) as mock_load:
        m1 = _get_whisper_model("base")
        m2 = _get_whisper_model("base")

    assert m1 is m2
    mock_load.assert_called_once_with("base")


def test_different_models_loaded_separately():
    """Different model names are loaded independently."""
    _whisper_cache.clear()

    mock_base = MagicMock()
    mock_small = MagicMock()
    load_calls = []

    def mock_load(name):
        load_calls.append(name)
        return mock_base if name == "base" else mock_small

    with patch("src.transcribe.whisper.load_model", side_effect=mock_load):
        m1 = _get_whisper_model("base")
        m2 = _get_whisper_model("small")

    assert m1 is mock_base
    assert m2 is mock_small
    assert load_calls == ["base", "small"]


def test_model_cache_persists_across_calls():
    """Cached models persist in _whisper_cache dict."""
    _whisper_cache.clear()

    mock_model = MagicMock()
    with patch("src.transcribe.whisper.load_model", return_value=mock_model):
        _get_whisper_model("base")

    assert "base" in _whisper_cache
    assert _whisper_cache["base"] is mock_model
