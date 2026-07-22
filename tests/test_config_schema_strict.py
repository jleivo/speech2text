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


def test_magic_words_pattern_accepts_unicode_keys():
    """Magic word keys may contain Unicode letters (e.g. Finnish PÄIVÄKIRJA)."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "PÄIVÄKIRJA": {"script_path": "/bin/journal.py"},
        },
    }
    config_path = _write_config(config)

    result = load_config(config_path)
    assert "PÄIVÄKIRJA" in result["magic_words"]


def test_magic_words_accept_handler_params():
    """Magic word entries may carry extra handler parameters (string values)."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "PÄIVÄKIRJA": {
                "script_path": "/bin/journal.py",
                "destination": "/srv/Obsidian/Archives/dailynotes",
            },
            "WORK": {
                "script_path": "/bin/work_tasks.py",
                "email": "juha.leivo@kone.com",
            },
        },
    }
    config_path = _write_config(config)

    result = load_config(config_path)
    assert result["magic_words"]["PÄIVÄKIRJA"]["destination"] == \
        "/srv/Obsidian/Archives/dailynotes"
    assert result["magic_words"]["WORK"]["email"] == "juha.leivo@kone.com"


def test_magic_words_reject_non_string_params():
    """Handler parameter values must be strings."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py", "count": 5},
        },
    }
    config_path = _write_config(config)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        load_config(config_path)


def test_magic_words_accept_aliases_array():
    """Magic word entries may carry an 'aliases' array of trigger words."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "WORK": {
                "script_path": "/bin/work_tasks.py",
                "aliases": ["KONE", "JOB"],
            },
        },
    }
    config_path = _write_config(config)

    result = load_config(config_path)
    assert result["magic_words"]["WORK"]["aliases"] == ["KONE", "JOB"]


def test_magic_words_aliases_must_be_strings():
    """Alias entries must be strings."""
    config = {
        "folder_to_watch": "/tmp/audio",
        "magic_words": {
            "WORK": {"script_path": "/bin/work_tasks.py", "aliases": [1, 2]},
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
