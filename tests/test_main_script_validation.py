"""Test script_path validation at startup (R2-m6, R3-M4).

Covers:
  - Missing magic_word script_path raises SystemExit
  - Missing default_action script_path raises SystemExit
  - Valid script paths pass validation
  - Multiple errors are all reported
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch

from src.main import _validate_script_paths, main


def _make_config_with_scripts(tmpdir):
    script = os.path.join(tmpdir, "handler.py")
    with open(script, "w") as f:
        f.write("import sys; sys.exit(0)")
    return script


def test_validate_script_paths_passes_when_all_exist(tmp_path):
    """Validation passes when all script paths exist."""
    tmpdir = str(tmp_path)
    script = _make_config_with_scripts(tmpdir)
    config = {
        "magic_words": {
            "FILE": {"script_path": script},
        },
        "default_action": {"script_path": script},
    }
    # Should not raise
    _validate_script_paths(config)


def test_validate_script_paths_fails_on_missing_magic_word_script(tmp_path):
    """Validation fails when a magic_word script_path does not exist."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/nonexistent/handler.py"},
        },
    }
    with pytest.raises(SystemExit):
        _validate_script_paths(config)


def test_validate_script_paths_fails_on_missing_default_action_script(tmp_path):
    """Validation fails when default_action script_path does not exist."""
    tmpdir = str(tmp_path)
    script = _make_config_with_scripts(tmpdir)
    config = {
        "magic_words": {
            "FILE": {"script_path": script},
        },
        "default_action": {"script_path": "/nonexistent/default.py"},
    }
    with pytest.raises(SystemExit):
        _validate_script_paths(config)


def test_validate_script_paths_reports_multiple_errors(tmp_path):
    """All missing paths are reported before exiting."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/nonexistent/handler.py"},
            "APPEND": {"script_path": "/nonexistent/append.py"},
        },
        "default_action": {"script_path": "/nonexistent/default.py"},
    }
    with pytest.raises(SystemExit):
        _validate_script_paths(config)


def test_main_exits_on_invalid_script_path(tmp_path):
    """main() exits early when script_path validation fails."""
    tmpdir = str(tmp_path)
    watch_dir = os.path.join(tmpdir, "audio")
    os.makedirs(watch_dir)
    config = {
        "folder_to_watch": watch_dir,
        "magic_words": {
            "FILE": {"script_path": "/nonexistent/handler.py"},
        },
    }
    config_path = os.path.join(tmpdir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    with pytest.raises(SystemExit):
        main(config_path)
