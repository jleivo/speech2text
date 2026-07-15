"""Test timeouts in transcribe.py.

Covers:
  - LiteLLM calls have timeout=60
  - Local Whisper transcribe has timeout=300
"""
from unittest.mock import patch, MagicMock

from src.transcribe import transcribe_audio, _transcribe_litellm


def test_litellm_has_timeout():
    """LiteLLM transcription call uses timeout=60."""
    mock_response = MagicMock()
    mock_response.text = "hello"

    with patch("builtins.open", MagicMock()):
        with patch("src.transcribe.litellm.transcription", return_value=mock_response) as mock_lt:
            _transcribe_litellm("/tmp/test.wav", "whisper-1")

    assert mock_lt.call_args[1]["timeout"] == 60


def test_local_whisper_has_timeout():
    """Local Whisper transcribe uses ThreadPoolExecutor with timeout=300."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "local"}

    with patch("src.transcribe._get_whisper_model", return_value=mock_model) as mock_get:
        with patch("src.transcribe.ThreadPoolExecutor") as mock_executor_cls:
            mock_future = MagicMock()
            mock_future.result.return_value = {"text": "local"}
            mock_executor = MagicMock()
            mock_executor.__enter__ = MagicMock(return_value=mock_executor)
            mock_executor.__exit__ = MagicMock(return_value=None)
            mock_executor.submit.return_value = mock_future
            mock_executor_cls.return_value = mock_executor

            transcribe_audio("/tmp/test.wav", backend="local", model="base")

            mock_future.result.assert_called_once_with(timeout=300)
