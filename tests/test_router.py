import subprocess
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

    mock_run.assert_called_once_with(
        ["python", "/usr/local/bin/file_handler.py", "this is my note"],
        check=False,
    )
    assert result == ("FILE", True)


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

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", "this is my note"],
        check=False,
    )
    assert result == ("FILE", True)


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

    mock_run.assert_called_once_with(
        ["python", "/bin/default.py", "hello world"],
        check=False,
    )
    assert result == ("default", True)


def test_route_no_match_no_default():
    """No match and no default action returns None."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        result = route_transcription("hello world", config)

    mock_run.assert_not_called()
    assert result == (None, True)


def test_route_script_failure():
    """Script returning non-zero exit code reports failure."""
    config = {
        "magic_words": {
            "FILE": {"script_path": "/bin/handler.py"}
        },
    }

    with patch("src.router.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = route_transcription("file my note", config)

    assert result == ("FILE", False)


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

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", "extra   spaces   here"],
        check=False,
    )


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

    mock_run.assert_called_once_with(
        ["python", "/bin/handler.py", ""],
        check=False,
    )
