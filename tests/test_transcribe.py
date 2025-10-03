










#!/usr/bin/env python3

import os
import tempfile
import pytest
from src.transcribe import transcribe_audio

def test_transcribe_audio():
    """Test the transcribe_audio function."""
    # Create a temporary audio file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        file_path = tmp.name

    # Mock the actual transcription to avoid needing OpenAI Whisper
    import src.transcribe
    original_transcribe_audio = src.transcribe.transcribe_audio
    src.transcribe.transcribe_audio = lambda x: "This is a mock transcription"

    result = transcribe_audio(file_path)

    assert result == "This is a test transcription of the audio file.", "transcribe_audio should return the expected result"
    # Restore the original function to avoid affecting other tests
    src.transcribe.transcribe_audio = original_transcribe_audio

    # Clean up
    os.unlink(file_path)



