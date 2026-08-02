#!/usr/bin/env python3
# v1.0.0
"""Tests for append_handler.py — run as subprocess (mirrors router)."""

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "handlers",
    "append_handler.py",
)


def _run(text=None, env_override=None):
    """Run the handler as a subprocess, return (stdout, returncode)."""
    cmd = [sys.executable, SCRIPT]
    if text is not None:
        cmd.append(text)
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, check=False
    )
    return result.stdout.strip(), result.returncode


class TestInputValidation:
    """Missing / empty / whitespace input must return rc 1."""

    def test_no_args(self):
        """No arguments at all -> rc 1."""
        _, rc = _run(text=None)
        assert rc == 1

    def test_empty_string(self):
        """Empty string argument -> rc 1."""
        _, rc = _run(text="")
        assert rc == 1

    def test_whitespace_only(self):
        """Whitespace-only argument -> rc 1."""
        _, rc = _run(text="   \t\n  ")
        assert rc == 1


class TestBasicAppend:
    """Core append behaviour with a static filename."""

    def setup_method(self):
        """Create a temp directory for each test."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove the temp directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_file_and_appends(self):
        """First entry creates the file with one line."""
        out, rc = _run(
            text="Hello world",
            env_override={
                "S2T_DESTINATION": self.tmpdir,
                "S2T_FILENAME": "test.md",
            },
        )
        assert rc == 0
        assert "Appended to" in out
        filepath = os.path.join(self.tmpdir, "test.md")
        assert os.path.isfile(filepath)
        with open(filepath, encoding="utf-8") as fh:
            assert fh.read() == "Hello world\n"

    def test_multiple_entries_accumulate(self):
        """Three entries produce three lines in order."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "multi.md",
        }
        _run(text="First entry", env_override=env)
        _run(text="Second entry", env_override=env)
        _run(text="Third entry", env_override=env)
        filepath = os.path.join(self.tmpdir, "multi.md")
        with open(filepath, encoding="utf-8") as fh:
            lines = fh.readlines()
        assert lines == [
            "First entry\n",
            "Second entry\n",
            "Third entry\n",
        ]

    def test_strips_leading_trailing_whitespace(self):
        """Surrounding whitespace is stripped before writing."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "strip.md",
        }
        _run(text="  padded text  ", env_override=env)
        filepath = os.path.join(self.tmpdir, "strip.md")
        with open(filepath, encoding="utf-8") as fh:
            assert fh.read() == "padded text\n"


class TestDateExpansion:
    """Filename tokens are expanded at runtime."""

    def setup_method(self):
        """Create a temp directory for each test."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove the temp directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_yyyy_mm_dd_pattern(self):
        """YYYY-MM-DD tokens expand to today's date."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "blogi-YYYY-MM-DD.md",
        }
        _, rc = _run(text="Blog entry", env_override=env)
        assert rc == 0
        today = datetime.now().strftime("%Y-%m-%d")
        expected = os.path.join(self.tmpdir, f"blogi-{today}.md")
        assert os.path.isfile(expected)

    def test_static_filename_no_tokens(self):
        """A filename without tokens is used verbatim."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "general.md",
        }
        _, rc = _run(text="General note", env_override=env)
        assert rc == 0
        expected = os.path.join(self.tmpdir, "general.md")
        assert os.path.isfile(expected)

    def test_time_tokens(self):
        """HH, MI, SS tokens produce a time-stamped filename."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "log-YYYY-MM-DD-HH-MI-SS.md",
        }
        _, rc = _run(text="Timed entry", env_override=env)
        assert rc == 0
        files = os.listdir(self.tmpdir)
        assert len(files) == 1
        assert files[0].startswith("log-")
        assert files[0].endswith(".md")

    def test_multiple_entries_same_day_same_file(self):
        """Two entries on the same day land in the same dated file."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "daily-YYYY-MM-DD.md",
        }
        _run(text="Morning thought", env_override=env)
        _run(text="Evening thought", env_override=env)
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(self.tmpdir, f"daily-{today}.md")
        with open(filepath, encoding="utf-8") as fh:
            lines = fh.readlines()
        assert len(lines) == 2
        assert lines[0] == "Morning thought\n"
        assert lines[1] == "Evening thought\n"


class TestUnicodeAndEdgeCases:
    """Finnish text, special chars, long text."""

    def setup_method(self):
        """Create a temp directory for each test."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove the temp directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_finnish_text(self):
        """Finnish Unicode text and filename work correctly."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "päivä.md",
        }
        _, rc = _run(
            text="Tämä on suomenkielinen merkintä", env_override=env
        )
        assert rc == 0
        filepath = os.path.join(self.tmpdir, "päivä.md")
        with open(filepath, encoding="utf-8") as fh:
            assert "Tämä on suomenkielinen merkintä" in fh.read()

    def test_special_markdown_chars(self):
        """Markdown special characters are preserved verbatim."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "special.md",
        }
        text = "# Heading **bold** [link](url) `code` > quote"
        _, rc = _run(text=text, env_override=env)
        assert rc == 0
        filepath = os.path.join(self.tmpdir, "special.md")
        with open(filepath, encoding="utf-8") as fh:
            assert text in fh.read()

    def test_long_text(self):
        """A ~25 KB entry is written intact."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "long.md",
        }
        text = "word " * 5000
        _, rc = _run(text=text, env_override=env)
        assert rc == 0
        filepath = os.path.join(self.tmpdir, "long.md")
        with open(filepath, encoding="utf-8") as fh:
            content = fh.read()
        assert content == text.strip() + "\n"


class TestErrorHandling:
    """Permission and path errors must return rc 2."""

    def test_permission_denied(self):
        """Read-only destination directory -> rc 2."""
        tmpdir = tempfile.mkdtemp()
        try:
            os.chmod(tmpdir, 0o444)
            _, rc = _run(
                text="Should fail",
                env_override={
                    "S2T_DESTINATION": tmpdir,
                    "S2T_FILENAME": "nope.md",
                },
            )
            assert rc == 2
        finally:
            os.chmod(tmpdir, 0o755)
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_creates_missing_parent_dirs(self):
        """Missing parent directories are created automatically."""
        tmpdir = tempfile.mkdtemp()
        try:
            nested = os.path.join(tmpdir, "a", "b", "c")
            _, rc = _run(
                text="Nested entry",
                env_override={
                    "S2T_DESTINATION": nested,
                    "S2T_FILENAME": "deep.md",
                },
            )
            assert rc == 0
            filepath = os.path.join(nested, "deep.md")
            assert os.path.isfile(filepath)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestConfigPrecedence:
    """S2T_DESTINATION and S2T_FILENAME drive behaviour."""

    def setup_method(self):
        """Create a temp directory for each test."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove the temp directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_env_overrides_default(self):
        """S2T_DESTINATION + S2T_FILENAME override built-in defaults."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "custom.md",
        }
        _, rc = _run(text="Custom path", env_override=env)
        assert rc == 0
        assert os.path.isfile(os.path.join(self.tmpdir, "custom.md"))
