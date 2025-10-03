










#!/usr/bin/env python3

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from src.transcribe import transcribe_audio

def test_transcribe_audio():
    """Test the transcribe_audio function."""
    # Create a temporary audio file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        file_path = tmp.name

    # Mock the actual transcription to avoid needing OpenAI Whisper
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {'text': 'This is a test transcription'}

    with patch('src.transcribe.whisper.load_model', return_value=mock_model):
        result = transcribe_audio(file_path)

        assert result == "This is a test transcription", "transcribe_audio should return the expected result"

    # Clean up
    os.unlink(file_path)



