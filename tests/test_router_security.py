"""Test router security measures.

Covers:
  - Minimal environment: OPENAI_API_KEY excluded from subprocess env (R2-M1)
  - subprocess timeout=30 (M2)
  - sys.executable used instead of "python" (R2-M10)
  - Null byte sanitization (R2-m3)
  - _sanitize_text strips null bytes
  - _SENSITIVE_ENV_KEYS is a frozenset
"""
import os
import sys
from unittest.mock import patch, MagicMock

from src.router import route_transcription, _sanitize_text, _SENSITIVE_ENV_KEYS, _run_script


def test_sensitive_env_keys_is_frozenset():
    """_SENSITIVE_ENV_KEYS is a frozenset (immutable)."""
    assert isinstance(_SENSITIVE_ENV_KEYS, frozenset)
    assert "OPENAI_API_KEY" in _SENSITIVE_ENV_KEYS


def test_sanitize_text_strips_null_bytes():
    """_sanitize_text removes null bytes from text."""
    assert _sanitize_text("hello\x00world") == "helloworld"
    assert _sanitize_text("a\x00b\x00c") == "abc"
    assert _sanitize_text("no nulls") == "no nulls"


def test_run_script_uses_sys_executable():
    """_run_script uses sys.executable, not 'python'."""
    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_script({"script_path": "/bin/handler.py"}, "test text")

    args = mock_run.call_args[0][0]
    assert args[0] == sys.executable
    assert args[1] == "/bin/handler.py"


def test_run_script_excludes_sensitive_env():
    """Sensitive env keys are excluded from subprocess environment."""
    os.environ["OPENAI_API_KEY"] = "test-secret"
    try:
        with patch("src.router.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _run_script({"script_path": "/bin/handler.py"}, "test")

        env = mock_run.call_args[1]["env"]
        assert "OPENAI_API_KEY" not in env
    finally:
        del os.environ["OPENAI_API_KEY"]


def test_run_script_has_timeout_30():
    """subprocess.run is called with timeout=30."""
    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_script({"script_path": "/bin/handler.py"}, "test")

    assert mock_run.call_args[1]["timeout"] == 30


def test_run_script_sanitizes_null_bytes_in_text():
    """Null bytes are stripped before passing text to subprocess."""
    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_script({"script_path": "/bin/handler.py"}, "text\x00with\x00nulls")

    text_arg = mock_run.call_args[0][0][2]
    assert "\x00" not in text_arg
    assert text_arg == "textwithnulls"
