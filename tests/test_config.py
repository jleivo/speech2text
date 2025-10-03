







#!/usr/bin/env python3

import os
import json
import tempfile
import pytest
import jsonschema
from src.config import load_config, create_default_config

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

def test_load_config_invalid():
    """Test that load_config raises an exception for invalid configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'config.json')

        # Test with missing required fields
        invalid_config = {
            "folder_to_watch": "/tmp/test_folder"
            # Missing magic_words
        }
        with open(config_path, 'w') as f:
            json.dump(invalid_config, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)

def test_create_default_config():
    """Test the create_default_config function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = create_default_config(tmpdir)

        assert os.path.exists(config_path), "Config file should be created"
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Check that the default config has the expected structure
        assert "folder_to_watch" in config, "Default config should have folder_to_watch"
        assert "magic_words" in config, "Default config should have magic_words"




