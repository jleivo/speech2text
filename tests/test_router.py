import os
import subprocess
import sys
from unittest.mock import patch, MagicMock
from src.router import route_transcription


def test_route_matches_first_word():
    """First word matches magic word, script called with stripped text."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/usr/local/bin/file_handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("file this is my note", config)

    call_args = mock_run.call_args
    assert call_args[0][0][0] == sys.executable
    assert call_args[0][0][1] == "/usr/local/bin/file_handler.py"
    assert call_args[0][0][2] == "this is my note"
    assert call_args[1]["check"] is False
    assert call_args[1]["timeout"] == 30
    # env should not contain OPENAI_API_KEY
    assert "OPENAI_API_KEY" not in call_args[1]["env"]
    assert result == ("FILE", True, None)


def test_route_case_insensitive():
    """Magic word matching is case-insensitive."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("File this is my note", config)

    call_args = mock_run.call_args
    assert call_args[0][0][0] == sys.executable
    assert call_args[0][0][1] == "/bin/handler.py"
    assert call_args[0][0][2] == "this is my note"
    assert call_args[1]["check"] is False
    assert call_args[1]["timeout"] == 30
    assert "OPENAI_API_KEY" not in call_args[1]["env"]
    assert result == ("FILE", True, None)


def test_route_no_match_uses_default():
    """No magic word match falls back to default action with full text."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
        "default_action": {"script_path": "/bin/default.py"},
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("hello world", config)

    call_args = mock_run.call_args
    assert call_args[0][0][0] == sys.executable
    assert call_args[0][0][1] == "/bin/default.py"
    assert call_args[0][0][2] == "hello world"
    assert call_args[1]["check"] is False
    assert call_args[1]["timeout"] == 30
    assert "OPENAI_API_KEY" not in call_args[1]["env"]
    assert result == ("default", True, None)


def test_route_no_match_no_default():
    """No match and no default action returns (None, False) to preserve file."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        result = route_transcription("hello world", config)

    mock_run.assert_not_called()
    assert result[0] is None
    assert result[1] is False
    assert "no default_action" in result[2]


def test_route_script_failure():
    """Script returning non-zero exit code reports failure with the error."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
        # Disable fallback so we observe the primary failure directly.
        "fallback_on_failure": False,
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=2, stderr="Error: daily note not found", stdout=""
        )
        result = route_transcription("file my note", config)

    action, success, error = result
    assert action == "FILE"
    assert success is False
    assert "exit code 2" in error
    assert "daily note not found" in error


def test_route_script_failure_captures_stdout_when_no_stderr():
    """Handlers that print errors to stdout still surface the reason."""
    config = {
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        "fallback_on_failure": False,
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="", stdout="Error: permission denied"
        )
        _, success, error = route_transcription("file my note", config)

    assert success is False
    assert "permission denied" in error


def test_route_fallback_on_handler_failure():
    """A failed magic-word handler falls back to default_action by default."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
    }

    # First call (WORK handler) fails, second call (default) succeeds.
    fail = MagicMock(returncode=2, stderr="boom", stdout="")
    ok = MagicMock(returncode=0, stderr="", stdout="")
    with patch("src.router.subprocess.run", side_effect=[fail, ok]) as mock_run:
        action, success, error = route_transcription("WORK do thing", config)

    assert action == "WORK+fallback"
    assert success is True
    assert "recovered via default_action" in error
    assert mock_run.call_count == 2


def test_route_fallback_disabled_preserves_failure():
    """With fallback_on_failure=False, a handler failure is returned as-is."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
        "fallback_on_failure": False,
    }

    fail = MagicMock(returncode=2, stderr="boom", stdout="")
    with patch("src.router.subprocess.run", side_effect=[fail]) as mock_run:
        action, success, error = route_transcription("WORK do thing", config)

    assert action == "WORK"
    assert success is False
    assert "boom" in error
    assert mock_run.call_count == 1  # no fallback attempted


def test_route_fallback_no_default_configured():
    """Handler failure with no default_action returns the primary failure."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
    }

    fail = MagicMock(returncode=2, stderr="boom", stdout="")
    with patch("src.router.subprocess.run", side_effect=[fail]) as mock_run:
        action, success, error = route_transcription("WORK do thing", config)

    assert action == "WORK"
    assert success is False
    assert "boom" in error
    assert mock_run.call_count == 1


def test_route_fallback_also_fails():
    """When both primary and fallback fail, both errors are reported."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
    }

    fail1 = MagicMock(returncode=2, stderr="primary boom", stdout="")
    fail2 = MagicMock(returncode=3, stderr="fallback boom", stdout="")
    with patch("src.router.subprocess.run", side_effect=[fail1, fail2]):
        action, success, error = route_transcription("WORK do thing", config)

    assert action == "WORK+fallback"
    assert success is False
    assert "primary boom" in error
    assert "fallback boom" in error


def test_route_handler_timeout_reports_error():
    """A handler that exceeds the timeout reports a timeout error."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "fallback_on_failure": False,
    }

    with patch("src.router.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
        action, success, error = route_transcription("WORK do thing", config)

    assert action == "WORK"
    assert success is False
    assert "timed out" in error


def test_route_strips_only_first_word():
    """Only the first word is stripped, rest preserved exactly."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file   extra   spaces   here", config)

    call_args = mock_run.call_args
    assert call_args[0][0][0] == sys.executable
    assert call_args[0][0][1] == "/bin/handler.py"
    assert call_args[0][0][2] == "extra   spaces   here"
    assert call_args[1]["check"] is False
    assert call_args[1]["timeout"] == 30


def test_route_single_word_transcription():
    """Single word transcription that matches sends empty string."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file", config)

    call_args = mock_run.call_args
    assert call_args[0][0][0] == sys.executable
    assert call_args[0][0][1] == "/bin/handler.py"
    assert call_args[0][0][2] == ""
    assert call_args[1]["check"] is False
    assert call_args[1]["timeout"] == 30


def test_route_strips_null_bytes():
    """Null bytes in transcription text are stripped before subprocess call."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file note\x00with\x00nulls", config)

    call_args = mock_run.call_args
    assert "\x00" not in call_args[0][0][2]
    assert call_args[0][0][2] == "notewithnulls"


def test_route_excludes_sensitive_env():
    """OPENAI_API_KEY is excluded from subprocess environment."""
    os.environ["OPENAI_API_KEY"] = "test-secret-key"
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    try:
        with patch("src.router.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            route_transcription("file test", config)

        call_args = mock_run.call_args
        assert "OPENAI_API_KEY" not in call_args[1]["env"]
    finally:
        del os.environ["OPENAI_API_KEY"]


def test_route_subprocess_timeout():
    """subprocess.run is called with timeout=30."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("file test", config)

    assert mock_run.call_args[1]["timeout"] == 30


def test_route_forwards_extra_config_as_env():
    """Extra magic-word config keys are forwarded as S2T_<KEY> env vars."""
    config = {
        "magic_words": {
            "PÄIVÄKIRJA": {
                "script_path": "/bin/journal.py",
                "destination": "/srv/Obsidian/Archives/dailynotes",
            }
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("PÄIVÄKIRJA päivä alkoi", config)

    env = mock_run.call_args[1]["env"]
    assert env["S2T_DESTINATION"] == "/srv/Obsidian/Archives/dailynotes"
    # script_path must NOT be forwarded as an env var
    assert "S2T_SCRIPT_PATH" not in env


def test_route_forwards_multiple_params():
    """All non-reserved config keys are forwarded, e.g. email for a task handler."""
    config = {
        "magic_words": {
            "WORK": {
                "script_path": "/bin/work_tasks.py",
                "email": "juha.leivo@kone.com",
                "priority": "high",
            }
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("WORK do the thing", config)

    env = mock_run.call_args[1]["env"]
    assert env["S2T_EMAIL"] == "juha.leivo@kone.com"
    assert env["S2T_PRIORITY"] == "high"


def test_route_unicode_magic_word_matches():
    """Unicode magic words (e.g. Finnish PÄIVÄKIRJA) match correctly."""
    config = {
        "magic_words": {
            "PÄIVÄKIRJA": {"script_path": "/bin/journal.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("PÄIVÄKIRJA päivä alkoi hyvin", config)

    assert result == ("PÄIVÄKIRJA", True, None)
    assert mock_run.call_args[0][0][2] == "päivä alkoi hyvin"


def test_route_default_action_forwards_params():
    """default_action config keys are also forwarded as S2T_<KEY> env vars."""
    config = {
        "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        "default_action": {
            "script_path": "/bin/default.py",
            "destination": "/srv/Obsidian/Inbox",
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("no match here", config)

    env = mock_run.call_args[1]["env"]
    assert env["S2T_DESTINATION"] == "/srv/Obsidian/Inbox"


def test_route_alias_triggers_same_handler():
    """An alias triggers the same handler as the primary keyword."""
    config = {
        "magic_words": {
            "WORK": {
                "script_path": "/bin/work_tasks.py",
                "email": "juha.leivo@kone.com",
                "aliases": ["KONE"],
            }
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("KONE do the thing", config)

    # Reports the primary keyword, runs the same script with the same params
    assert result == ("WORK", True, None)
    assert mock_run.call_args[0][0][1] == "/bin/work_tasks.py"
    assert mock_run.call_args[1]["env"]["S2T_EMAIL"] == "juha.leivo@kone.com"


def test_route_alias_case_insensitive():
    """Alias matching is case-insensitive."""
    config = {
        "magic_words": {
            "WORK": {"script_path": "/bin/work_tasks.py", "aliases": ["KONE"]}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("kone lowercase trigger", config)

    assert result == ("WORK", True, None)


def test_route_primary_keyword_still_matches_with_aliases():
    """The primary keyword still matches when aliases are defined."""
    config = {
        "magic_words": {
            "WORK": {"script_path": "/bin/work_tasks.py", "aliases": ["KONE"]}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("WORK primary trigger", config)

    assert result == ("WORK", True, None)


def test_route_alias_not_forwarded_as_env():
    """The aliases list is reserved and not forwarded as an S2T_ env var."""
    config = {
        "magic_words": {
            "WORK": {"script_path": "/bin/work_tasks.py", "aliases": ["KONE"]}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        route_transcription("KONE trigger", config)

    env = mock_run.call_args[1]["env"]
    assert "S2T_ALIASES" not in env


def test_route_trigger_with_trailing_period():
    """A trailing period (Whisper sentence punctuation) does not break matching.

    Regression: a spoken 'Journal' is transcribed as 'Journal.' which used to
    fall through to the default action instead of matching the alias.
    """
    config = {
        "magic_words": {
            "PÄIVÄKIRJA": {
                "script_path": "/bin/journal.py",
                "aliases": ["JOURNAL"],
            }
        },
        "default_action": {"script_path": "/bin/default.py"},
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("Journal. Olen taas palannut.", config)

    assert result == ("PÄIVÄKIRJA", True, None)
    # Handler receives the text AFTER the trigger word, period stripped with it
    assert mock_run.call_args[0][0][2] == "Olen taas palannut."


def test_route_trigger_with_various_punctuation():
    """Leading/trailing punctuation and symbols are ignored when matching."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
    }

    for trigger in ("WORK,", "WORK!", "(WORK)", "WORK:", "«WORK»", "WORK..."):
        with patch("src.router.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = route_transcription(f"{trigger} do the thing", config)
        assert result == ("WORK", True, None), f"trigger {trigger!r} failed to match"


def test_route_trigger_punctuation_only_does_not_match():
    """A first word that is entirely punctuation does not match a keyword."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = route_transcription("... the thing", config)

    # '...' normalizes to empty -> no match -> default action
    assert result == ("default", True, None)


def test_route_interior_punctuation_preserved():
    """Punctuation inside the trigger word is preserved (no false match)."""
    config = {
        "magic_words": {"WORK": {"script_path": "/bin/work.py"}},
        "default_action": {"script_path": "/bin/default.py"},
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # 'WO.RK' should NOT match 'WORK' — interior period is significant
        result = route_transcription("WO.RK something", config)

    assert result == ("default", True, None)
