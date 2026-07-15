"""Test config schema strictness.

Covers:
  - additionalProperties: false (unknown keys rejected)
  - Path validation: absolute paths required, no '..' components
  - vault_service pattern: alphanumeric + underscore + hyphen only
"""
import json
import os
import tempfile
import pytest
import jsonschema

from src.config import load_config, CONFIG_SCHEMA


def _write_config(config):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        return f.name


def test_additional_properties_rejected():
    """Unknown top-level keys are rejected (additionalProperties: false)."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        "unknown_field": "not allowed",
    }
    config_path = _write_config(config)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        load_config(config_path)


def test_path_must_be_absolute():
    """Path fields must be absolute."""
    config = {
        "folder_to_watch": "relative/path",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config_path = _write_config(config)

    with pytest.raises(ValueError, match="path must be absolute"):
        load_config(config_path)


def test_path_must_not_contain_dotdot():
    """Path fields must not contain '..' components."""
    config = {
        "folder_to_watch": "/tmp/../etc/audio",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config_path = _write_config(config)

    with pytest.raises(ValueError, match=r"path must not contain '\.\.' components"):
        load_config(config_path)


def test_transcription_log_path_must_be_absolute():
    """transcription_log must also be an absolute path."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "transcription_log": "relative/log.txt",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config_path = _write_config(config)

    with pytest.raises(ValueError, match="path must be absolute"):
        load_config(config_path)


def test_vault_service_pattern_rejects_special_chars():
    """vault_service must match ^[a-zA-Z0-9_-]+$ — rejects special chars."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        "vault_service": "speech2text;rm -rf /",
    }
    config_path = _write_config(config)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        load_config(config_path)


def test_vault_service_pattern_accepts_valid():
    """vault_service accepts alphanumeric, underscore, hyphen."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        "vault_service": "speech2text_svc-1",
    }
    config_path = _write_config(config)

    result = load_config(config_path)
    assert result["vault_service"] == "speech2text_svc-1"


def test_magic_words_pattern_rejects_lowercase_keys():
    """Magic word keys must match ^[A-Z]+$ — rejects lowercase."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"},
            "lowercase": {"script_path": "/bin/handler.py"},
        },
    }
    config_path = _write_config(config)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        load_config(config_path)


def test_valid_absolute_paths_pass():
    """Valid absolute paths without '..' pass validation."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "transcription_log": "/var/log/speech2text.log",
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
    }
    config_path = _write_config(config)

    result = load_config(config_path)
    assert result["folder_to_watch"] == "/tmp/audio"
    assert result["transcription_log"] == "/var/log/speech2text.log"
