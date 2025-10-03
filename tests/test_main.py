










#!/usr/bin/env python3

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from src.main import load_config, main

def test_load_config():
    """Test the load_config function."""
    # Create a valid config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'config.json')
        valid_config = {
            "folder_to_watch": "/tmp/test_folder",
            "magic_words": {
                "TEST": {
                    "action": "create_file",
                    "file_path_template": "/tmp/test_output_{timestamp}.txt"
                }
            }
        }
        with open(config_path, 'w') as f:
            json.dump(valid_config, f)

        # Load the config
        loaded_config = load_config(config_path)

        assert loaded_config == valid_config, "Config should be loaded correctly"

def test_load_config_missing():
    """Test that load_config raises an exception for missing configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'config.json')

        # The file doesn't exist
        with patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                load_config(config_path)

def test_main():
    """Test the main function."""
    # Mock various components to avoid actually starting the observer
    with patch('src.main.load_config', return_value={'folder_to_watch': '/tmp/test_folder'}):
        with patch('src.main.FolderWatcherHandler'):
            with patch('src.main.Observer'):
                with patch('builtins.input', return_value='n'):  # Mock user input to skip waiting for files
                    main()





