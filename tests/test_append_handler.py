#!/usr/bin/env python3
# v1.0.0
"""Tests for append_handler.py — run as subprocess (mirrors router)."""

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

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


class TestTemplate:
    """A configured template seeds newly created files."""

    def setup_method(self):
        """Create temp dirs for output and templates."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init
        self.tmpldir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove temp directories."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.tmpldir, ignore_errors=True)

    def _write_template(self, name, content):
        """Write a template file and return its absolute path."""
        path = os.path.join(self.tmpldir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_template_seeds_new_file(self):
        """A new file gets the template content before the entry."""
        tmpl = self._write_template("blog.md", "# Blog\n\n")
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "blog.md",
            "S2T_TEMPLATE": tmpl,
        }
        _, rc = _run(text="First post", env_override=env)
        assert rc == 0
        with open(
            os.path.join(self.tmpdir, "blog.md"), encoding="utf-8"
        ) as fh:
            assert fh.read() == "# Blog\n\nFirst post\n"

    def test_template_date_tokens_expanded(self):
        """Date tokens inside the template content are expanded."""
        tmpl = self._write_template("daily.md", "# YYYY-MM-DD\n\n")
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "daily.md",
            "S2T_TEMPLATE": tmpl,
        }
        _, rc = _run(text="Entry", env_override=env)
        assert rc == 0
        today = datetime.now().strftime("%Y-%m-%d")
        with open(
            os.path.join(self.tmpdir, "daily.md"), encoding="utf-8"
        ) as fh:
            content = fh.read()
        assert content == f"# {today}\n\nEntry\n"

    def test_template_not_reapplied_to_existing_file(self):
        """Appending to an existing file does not rewrite the template."""
        tmpl = self._write_template("t.md", "# Header\n\n")
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "t.md",
            "S2T_TEMPLATE": tmpl,
        }
        _run(text="First", env_override=env)
        _run(text="Second", env_override=env)
        with open(
            os.path.join(self.tmpdir, "t.md"), encoding="utf-8"
        ) as fh:
            content = fh.read()
        # Header appears exactly once.
        assert content.count("# Header") == 1
        assert content == "# Header\n\nFirst\nSecond\n"

    def test_template_without_trailing_newline(self):
        """An entry still starts on its own line after a bare template."""
        tmpl = self._write_template("bare.md", "# NoNewline")
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "bare.md",
            "S2T_TEMPLATE": tmpl,
        }
        _, rc = _run(text="Entry", env_override=env)
        assert rc == 0
        with open(
            os.path.join(self.tmpdir, "bare.md"), encoding="utf-8"
        ) as fh:
            assert fh.read() == "# NoNewline\nEntry\n"

    def test_missing_template_is_error(self):
        """A configured-but-missing template file -> rc 2."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "x.md",
            "S2T_TEMPLATE": os.path.join(self.tmpldir, "ghost.md"),
        }
        _, rc = _run(text="Entry", env_override=env)
        assert rc == 2

    def test_no_template_configured_still_works(self):
        """Without S2T_TEMPLATE the handler behaves as before."""
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "plain.md",
        }
        _, rc = _run(text="Just text", env_override=env)
        assert rc == 0
        with open(
            os.path.join(self.tmpdir, "plain.md"), encoding="utf-8"
        ) as fh:
            assert fh.read() == "Just text\n"


class TestTemplater:
    """Safe Templater tags are expanded headlessly."""

    def setup_method(self):
        """Create temp dirs for output and templates."""
        self.tmpdir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init
        self.tmpldir = tempfile.mkdtemp()  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self):
        """Remove temp directories."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.tmpldir, ignore_errors=True)

    def _write_template(self, name, content):
        """Write a template file and return its absolute path."""
        path = os.path.join(self.tmpldir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def _run_with_template(self, tmpl_content, text="Entry"):
        """Write a template, run the handler, return file content."""
        tmpl = self._write_template("t.md", tmpl_content)
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "t.md",
            "S2T_TEMPLATE": tmpl,
        }
        _, rc = _run(text=text, env_override=env)
        assert rc == 0
        with open(
            os.path.join(self.tmpdir, "t.md"), encoding="utf-8"
        ) as fh:
            return fh.read()

    def test_date_now_basic(self):
        """tp.date.now("YYYY-MM-DD") expands to today's date."""
        content = self._run_with_template(
            '# <% tp.date.now("YYYY-MM-DD") %>\n\n'
        )
        today = datetime.now().strftime("%Y-%m-%d")
        assert content == f"# {today}\n\nEntry\n"

    def test_date_now_long_format(self):
        """Moment long formats (dddd, MMMM, Do) are converted."""
        content = self._run_with_template(
            '# <% tp.date.now("dddd, MMMM Do YYYY") %>\n\n'
        )
        now = datetime.now()
        expected_date = now.strftime("%A, %B")
        # Ordinal day
        day = now.day
        if 11 <= day <= 13:
            ordinal = f"{day}th"
        else:
            ordinal = f"{day}" + {1: "st", 2: "nd", 3: "rd"}.get(
                day % 10, "th"
            )
        expected = f"# {expected_date} {ordinal} {now.year}\n\nEntry\n"
        assert content == expected

    def test_date_now_with_offset(self):
        """tp.date.now("YYYY-MM-DD", 1) expands to tomorrow."""
        content = self._run_with_template(
            '<% tp.date.now("YYYY-MM-DD", 1) %>\n'
        )
        tomorrow = (
            datetime.now() + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        assert content == f"{tomorrow}\nEntry\n"

    def test_file_title(self):
        """tp.file.title expands to the filename without extension."""
        tmpl = self._write_template("t.md", "# <% tp.file.title %>\n")
        env = {
            "S2T_DESTINATION": self.tmpdir,
            "S2T_FILENAME": "blogi-2026-08-02.md",
            "S2T_TEMPLATE": tmpl,
        }
        _, rc = _run(text="Entry", env_override=env)
        assert rc == 0
        with open(
            os.path.join(self.tmpdir, "blogi-2026-08-02.md"),
            encoding="utf-8",
        ) as fh:
            content = fh.read()
        assert content == "# blogi-2026-08-02\nEntry\n"

    def test_creation_date(self):
        """tp.file.creation_date(...) expands to now."""
        content = self._run_with_template(
            'created: <% tp.file.creation_date("YYYY-MM-DD") %>\n'
        )
        today = datetime.now().strftime("%Y-%m-%d")
        assert content == f"created: {today}\nEntry\n"

    def test_unsafe_tag_left_intact(self):
        """Interactive tags are NOT expanded (left for Obsidian)."""
        content = self._run_with_template(
            "# Title\n\n<% tp.system.prompt('Name?') %>\n"
        )
        assert "<% tp.system.prompt('Name?') %>" in content
        assert "Entry" in content

    def test_mixed_safe_and_unsafe(self):
        """Safe tags expand, unsafe tags survive in the same file."""
        content = self._run_with_template(
            '# <% tp.date.now("YYYY") %>\n'
            "<% tp.file.cursor(1) %>\n"
        )
        year = datetime.now().strftime("%Y")
        assert f"# {year}" in content
        assert "<% tp.file.cursor(1) %>" in content

    def test_bare_tokens_outside_tags(self):
        """Handler tokens expand in text outside Templater tags."""
        content = self._run_with_template(
            "# YYYY-MM-DD\n<% tp.file.cursor(1) %>\n"
        )
        today = datetime.now().strftime("%Y-%m-%d")
        assert content.startswith(f"# {today}\n")
        # The cursor tag must NOT have its content mangled
        assert "<% tp.file.cursor(1) %>" in content

    def test_literal_brackets_in_moment(self):
        """[literal] blocks in Moment formats pass through."""
        content = self._run_with_template(
            '<% tp.date.now("[Week] WW [of] YYYY") %>\n'
        )
        now = datetime.now()
        expected = f"Week {now.strftime('%W')} of {now.year}\nEntry\n"
        assert content == expected

    def test_existing_templater_template_reuse(self):
        """A realistic existing Templater daily-note template works."""
        tmpl_content = (
            "---\n"
            "created: <% tp.file.creation_date('YYYY-MM-DD') %>\n"
            "tags: [daily]\n"
            "---\n"
            "# <% tp.date.now('dddd, MMMM Do YYYY') %>\n\n"
            "## Journal\n\n"
        )
        content = self._run_with_template(tmpl_content)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        assert f"created: {today}" in content
        assert "tags: [daily]" in content
        assert "## Journal" in content
        assert "Entry" in content
        # No raw Templater tags should remain
        assert "<%" not in content


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
