#!/usr/bin/env python3
"""Tests for note_handler.py — the voice note handler script.

Runs the handler as a subprocess via sys.executable so it exercises
the real entry point (sys.argv, main(), sys.exit).

Override NOTE_DIR via S2T_NOTE_DIR env var so tests don't write to
the production Obsidian vault.
"""
import os
import subprocess
import sys
import shutil
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      "handlers", "note_handler.py")


def _run(text=None, note_dir=None):
    """Run note_handler.py with optional text argument. Return (stdout, returncode)."""
    cmd = [sys.executable, SCRIPT]
    if text is not None:
        cmd.append(text)
    env = os.environ.copy()
    if note_dir:
        env["S2T_NOTE_DIR"] = note_dir
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.stdout.strip(), result.returncode


class TestNoteHandler:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.note_path = os.path.join(self.tmpdir, "Voice Notes.md")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- Input validation ---

    def test_no_args_returns_error(self):
        stdout, rc = _run(note_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()

    def test_empty_string_returns_error(self):
        stdout, rc = _run("", note_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()

    def test_whitespace_only_returns_error(self):
        stdout, rc = _run("   ", note_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()

    # --- File creation ---

    def test_creates_file_with_frontmatter(self):
        stdout, rc = _run("first voice note", note_dir=self.tmpdir)
        assert rc == 0
        assert os.path.exists(self.note_path)
        content = open(self.note_path).read()
        assert "---" in content
        assert "tags: [voice-notes]" in content
        assert "created:" in content
        assert "# Voice Notes" in content
        assert "first voice note" in content

    def test_creates_parent_directory(self):
        nested = os.path.join(self.tmpdir, "deep", "nested", "dir")
        stdout, rc = _run("nested note", note_dir=nested)
        assert rc == 0
        note = os.path.join(nested, "Voice Notes.md")
        assert os.path.exists(note)

    # --- Append behaviour ---

    def test_appends_to_existing_file(self):
        _run("note one", note_dir=self.tmpdir)
        _run("note two", note_dir=self.tmpdir)
        content = open(self.note_path).read()
        # frontmatter appears only once
        assert content.count("# Voice Notes") == 1
        assert "note one" in content
        assert "note two" in content

    def test_entry_format_has_timestamp(self):
        _run("timestamp check", note_dir=self.tmpdir)
        content = open(self.note_path).read()
        # Expected: - **[YYYY-MM-DD HH:MM:SS]** timestamp check
        assert "- **[" in content
        assert "]** timestamp check" in content

    # --- Content edge cases ---

    def test_unicode_text(self):
        _run("Hello world ❤ café résumé", note_dir=self.tmpdir)
        assert "café" in open(self.note_path).read()

    def test_long_text(self):
        long_text = "word " * 500
        stdout, rc = _run(long_text, note_dir=self.tmpdir)
        assert rc == 0
        assert long_text.strip() in open(self.note_path).read()

    def test_special_characters(self):
        stdout, rc = _run("note with [brackets] and #hashtags and $symbols", note_dir=self.tmpdir)
        assert rc == 0
        content = open(self.note_path).read()
        assert "[brackets]" in content
        assert "#hashtags" in content
        assert "$symbols" in content

    def test_success_message_contains_path(self):
        stdout, rc = _run("path check", note_dir=self.tmpdir)
        assert rc == 0
        assert self.note_path in stdout