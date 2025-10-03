
#!/usr/bin/env python3

import os
import tempfile
from src.transcribe import transcribe_audio

def test_transcribe_m4a():
    """Test the transcribe_audio function with an m4a file."""
    # Create a temporary audio file
    with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as tmp:
        file_path = tmp.name

    try:
        # Mock the actual transcription to avoid needing OpenAI Whisper
        import src.transcribe
        original_transcribe_audio = src.transcribe.transcribe_audio
        src.transcribe.transcribe_audio = lambda x: "This is a mock m4a transcription"

        result = transcribe_audio(file_path)

        assert result == "This is a test transcription of the audio file.", "transcribe_audio should return the expected result"
    finally:
        # Clean up
        if os.path.exists(file_path):
            os.unlink(file_path)
