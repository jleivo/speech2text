import pytest
from unittest.mock import patch, MagicMock
from src.transcribe import transcribe_audio


def test_transcribe_litellm_success():
    """LiteLLM backend returns transcription on success."""
    mock_response = MagicMock()
    mock_response.text = "hello world"

    with patch("builtins.open", MagicMock()):
        with patch("src.transcribe.litellm.transcription", return_value=mock_response):
            result = transcribe_audio("/tmp/test.wav", backend="litellm", model="whisper-1")

    assert result == "hello world"


def test_transcribe_litellm_falls_back_to_whisper():
    """When LiteLLM fails, falls back to local Whisper."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "fallback text"}

    with patch("src.transcribe.litellm.transcription", side_effect=Exception("API error")):
        with patch("src.transcribe.whisper.load_model", return_value=mock_model):
            result = transcribe_audio(
                "/tmp/test.wav", backend="litellm", model="whisper-1"
            )

    assert result == "fallback text"


def test_transcribe_local_whisper_directly():
    """Local whisper backend works when configured."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "local text"}

    with patch("src.transcribe.whisper.load_model", return_value=mock_model):
        result = transcribe_audio(
            "/tmp/test.wav", backend="local", model="turbo"
        )

    assert result == "local text"


def test_transcribe_local_whisper_model_passed():
    """Local whisper loads the configured model size."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "text"}

    with patch("src.transcribe.whisper.load_model", return_value=mock_model) as mock_load:
        transcribe_audio("/tmp/test.wav", backend="local", model="small")

    mock_load.assert_called_once_with("small")
