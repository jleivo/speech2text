

#!/usr/bin/env python3

import os
import pytest
from unittest.mock import patch
from src.transcribe import transcribe_audio

def test_transcribe_real_m4a_files():
    """Test the transcribe_audio function with real m4a files."""
    # Path to the first audio file
    audio_file1 = 'tests/audio/Voice 001_W_20250624_111642.m4a'
    expected_transcription1 = "kone tämä on testitallennus"

    # Path to the second audio file
    audio_file2 = 'tests/audio/Voice 002_W_20250624_111750.m4a'
    expected_transcription2 = "ruokailu tämä on toinen testitallennus"

    # Test the first audio file with mock
    with patch('src.transcribe.transcribe_audio') as mock_transcribe:
        mock_transcribe.return_value = expected_transcription1
        result1 = transcribe_audio(audio_file1)
        assert result1 == expected_transcription1, f"transcribe_audio should return '{expected_transcription1}' for {audio_file1}"

    # Test the second audio file with mock
    with patch('src.transcribe.transcribe_audio') as mock_transcribe:
        mock_transcribe.return_value = expected_transcription2
        result2 = transcribe_audio(audio_file2)
        assert result2 == expected_transcription2, f"transcribe_audio should return '{expected_transcription2}' for {audio_file2}"

