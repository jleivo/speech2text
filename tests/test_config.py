import json
import os
import tempfile
import pytest
import jsonschema
from src.config import load_config, DEFAULT_EXTENSIONS


def test_load_valid_config():
    """Full valid config loads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        valid = {
            "folder_to_watch": "/tmp/audio",
            "watched_extensions": [".wav", ".mp3"],
            "delete_after_processing": True,
            "transcription_log": "/tmp/speech2text.log",
            "backend": "litellm",
            "model": "whisper-1",
            "litellm_base_url": "",
            "default_action": {"script_path": "/usr/local/bin/default.py"},
            "magic_words": {
                "FILE": {"script_path": "/usr/local/bin/file_handler.py"},
                "APPEND": {"script_path": "/usr/local/bin/append_handler.py"},
            },
        }
        with open(config_path, "w") as f:
            json.dump(valid, f)

        config = load_config(config_path)
        assert config == valid


def test_load_minimal_config_gets_defaults():
    """Minimal config gets default values filled in."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        minimal = {
            "folder_to_watch": "/tmp/audio",
            "magic_words": {
                "FILE": {"script_path": "/usr/local/bin/file_handler.py"}
            },
        }
        with open(config_path, "w") as f:
            json.dump(minimal, f)

        config = load_config(config_path)
        assert config["watched_extensions"] == DEFAULT_EXTENSIONS
        assert config["delete_after_processing"] is False
        assert config["backend"] == "litellm"
        assert config["model"] == "whisper-1"
        assert config.get("litellm_base_url") == ""


def test_load_config_missing_file():
    """Missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_load_config_missing_folder_to_watch():
    """Config without folder_to_watch fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {"magic_words": {"FILE": {"script_path": "/bin/handler.py"}}}
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)


def test_load_config_missing_magic_words():
    """Config without magic_words fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {"folder_to_watch": "/tmp/audio"}
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)


def test_load_config_magic_word_missing_script_path():
    """Magic word without script_path fails validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        invalid = {
            "folder_to_watch": "/tmp/audio",
            "magic_words": {"FILE": {}},
        }
        with open(config_path, "w") as f:
            json.dump(invalid, f)

        with pytest.raises(jsonschema.exceptions.ValidationError):
            load_config(config_path)
