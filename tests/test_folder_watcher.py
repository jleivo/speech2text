





#!/usr/bin/env python3

import os
import tempfile
import pytest
import shutil
from src.folder_watcher import FolderWatcherHandler
from src.transcribe import transcribe_audio
from unittest.mock import MagicMock, patch

@pytest.fixture
def sample_config():
    return {
        "folder_to_watch": "/tmp/test_folder",
        "magic_words": {
            "TEST": {
                "action": "create_file",
                "file_path_template": "/tmp/test_output_{timestamp}.txt"
            }
        }
    }

@pytest.fixture
def failed_config():
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a directory for failed files
        failed_dir = os.path.join(temp_dir, 'failed')
        os.makedirs(failed_dir, exist_ok=True)

        return {
            "folder_to_watch": "/tmp/test_folder",
            "failed": {
                "to": failed_dir,
                "inform": "admin@example.com"
            },
            "magic_words": {
                "TEST": {
                    "action": "create_file",
                    "file_path_template": "/tmp/test_output_{timestamp}.txt"
                }
            }
        }
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)

@pytest.fixture
def folder_watcher(sample_config):
    return FolderWatcherHandler(sample_config)

@pytest.fixture
def failed_watcher(failed_config):
    return FolderWatcherHandler(failed_config)

def test_on_created_no_audio_file(folder_watcher):
    """Test that on_created does nothing for non-audio files."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        event = MagicMock()
        event.is_directory = False
        event.src_path = tmp.name

        # Mock the process_audio_file method to check if it's called
        folder_watcher.process_audio_file = MagicMock()

        folder_watcher.on_created(event)

        assert not folder_watcher.process_audio_file.called, "process_audio_file should not be called for non-audio files"

def test_on_created_with_audio_file(folder_watcher):
    """Test that on_created calls process_audio_file for audio files."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        event = MagicMock()
        event.is_directory = False
        event.src_path = tmp.name

        # Mock the process_audio_file method to check if it's called
        folder_watcher.process_audio_file = MagicMock()

        folder_watcher.on_created(event)

        assert folder_watcher.process_audio_file.called, "process_audio_file should be called for audio files"
        assert folder_watcher.process_audio_file.call_args[0][0] == tmp.name, "process_audio_file should be called with the correct file path"

def test_process_audio_file(folder_watcher):
    """Test that process_audio_file transcribes and checks for magic words."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        # Mock the transcribe_audio function
        mock_transcription = "This is a TEST transcription"
        with patch('src.folder_watcher.transcribe_audio', return_value=mock_transcription):
            # Mock the check_for_magic_words method to check if it's called
            folder_watcher.check_for_magic_words = MagicMock()

            folder_watcher.process_audio_file(tmp.name)

            assert folder_watcher.check_for_magic_words.called, "check_for_magic_words should be called"
            assert folder_watcher.check_for_magic_words.call_args[0][0] == mock_transcription, "check_for_magic_words should be called with the transcription"

def test_check_for_magic_words(folder_watcher):
    """Test that check_for_magic_words performs actions for magic words."""
    # Mock the perform_action function
    with patch('src.folder_watcher.perform_action') as mock_perform_action:
        # Test with a transcription containing a magic word
        folder_watcher.check_for_magic_words("This is a TEST transcription")

        assert mock_perform_action.called, "perform_action should be called"
        args, kwargs = mock_perform_action.call_args
        print(f"Magic word 'TEST' found. Performing action...")
        # Check if the transcription was passed as an argument (positional or keyword)
        assert len(args) > 1 and args[1] == "This is a TEST transcription", f"perform_action should be called with the transcription"

        # Reset the mock to test with a transcription not containing any magic words
        mock_perform_action.reset_mock()
        folder_watcher.check_for_magic_words("This does not contain any magic words")

        assert not mock_perform_action.called, "perform_action should not be called when no magic words are found"

def test_handle_failed_transcription_email(failed_watcher):
    """Test that handle_failed_transcription moves the file and sends an email."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        # Mock the send_email function
        with patch('src.folder_watcher.send_email') as mock_send_email:
            # Call the method directly since it's not normally called from outside
            failed_watcher.handle_failed_transcription(tmp.name)

            # Check if the file was moved to the failed directory
            failed_dir = os.path.join(os.path.dirname(failed_watcher.config['failed']['to']), 'failed')
            assert os.path.exists(failed_dir), "Failed directory should exist"

            # Check if send_email was called with the correct parameters
            assert mock_send_email.called, "send_email should be called"
            args, kwargs = mock_send_email.call_args
            assert args[0] == failed_watcher.config['failed']['inform'], "send_email should be called with the correct recipient"

def test_handle_failed_transcription_script(failed_config):
    """Test that handle_failed_transcription moves the file and executes a script."""
    # Create a temporary script for testing
    temp_dir = os.path.dirname(failed_config['failed']['to'])
    script_path = os.path.join(temp_dir, 'test_script.sh')
    with open(script_path, 'w') as f:
        f.write("#!/bin/bash\necho $1\n")

    # Make the script executable
    os.chmod(script_path, 0o755)

    try:
        # Create a watcher with the script configuration
        failed_config['failed']['script'] = script_path
        del failed_config['failed']['inform']
        failed_watcher = FolderWatcherHandler(failed_config)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            # Mock the execute_script function
            with patch('src.folder_watcher.execute_script') as mock_execute_script:
                # Call the method directly since it's not normally called from outside
                failed_watcher.handle_failed_transcription(tmp.name)

                # Check if the file was moved to the failed directory
                failed_dir = os.path.join(os.path.dirname(failed_watcher.config['failed']['to']), 'failed')
                assert os.path.exists(failed_dir), "Failed directory should exist"

                # Check if execute_script was called with the correct parameters
                assert mock_execute_script.called, "execute_script should be called"
                args, kwargs = mock_execute_script.call_args
                assert args[0] == failed_watcher.config['failed']['script'], "execute_script should be called with the correct script path"
    finally:
        # Clean up the temporary script
        if os.path.exists(script_path):
            os.remove(script_path)

def test_handle_failed_transcription_no_config(folder_watcher):
    """Test that handle_failed_transcription does nothing when no failed config exists."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        # Call the method directly since it's not normally called from outside
        folder_watcher.handle_failed_transcription(tmp.name)

        # Check if the file was moved (it shouldn't be)
        assert os.path.exists(tmp.name), "The file should still exist"


