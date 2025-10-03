
#!/usr/bin/env python3

import os
import tempfile
from unittest.mock import patch, MagicMock
from src.transcribe import transcribe_audio

def test_transcribe_m4a():
    """Test the transcribe_audio function with an m4a file."""
    # Create a temporary audio file
    with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as tmp:
        file_path = tmp.name

    try:
        # Mock the actual transcription to avoid needing OpenAI Whisper
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {'text': 'This is a test m4a transcription'}

        with patch('src.transcribe.whisper.load_model', return_value=mock_model):
            result = transcribe_audio(file_path)

            assert result == "This is a test m4a transcription", "transcribe_audio should return the expected result"
    finally:
        # Clean up
        if os.path.exists(file_path):
            os.unlink(file_path)
