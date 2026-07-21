#!/usr/bin/env python3
"""Tests for journal_handler.py — the daily note journal handler.

Runs the handler as a subprocess via sys.executable so it exercises
the real entry point (sys.argv, main(), sys.exit).

Override JOURNAL_DIR via S2T_JOURNAL_DIR env var so tests don't write
to the production Obsidian vault.
"""
import os
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      "handlers", "journal_handler.py")

# Template mimicking a real daily note structure
DAILY_NOTE_TEMPLATE = """\
Category: [[daily notes]]
# {weekday}, {date}

<< [[{yesterday}|Yesterday]] | [[{tomorrow}|Tomorrow]] >

---
# Tehtävät


```tasks
not done
due on or before {date}
group by due
```

# Journal

# Ilta

- [ ] pese hampaat
- [ ] laita dödö
- [x] ota vitamiineja
- [ ] Suihku
## Seuranta

Alkoholin kokonaismäärä:3
Karkki: ei
"""


def _run(text=None, journal_dir=None):
    """Run journal_handler.py with optional text argument. Return (stdout, returncode)."""
    cmd = [sys.executable, SCRIPT]
    if text is not None:
        cmd.append(text)
    env = os.environ.copy()
    if journal_dir:
        env["S2T_JOURNAL_DIR"] = journal_dir
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.stdout.strip(), result.returncode


def _create_daily_note(base_dir, now=None):
    """Create a daily note at the correct path for 'now' (default: today).

    Returns the full path to the created file.
    """
    if now is None:
        now = datetime.now()
    note_dir = os.path.join(base_dir, now.strftime("%Y"), now.strftime("%m"))
    os.makedirs(note_dir, exist_ok=True)
    filepath = os.path.join(note_dir, now.strftime("%Y-%m-%d") + ".md")
    content = DAILY_NOTE_TEMPLATE.format(
        weekday=now.strftime("%A"),
        date=now.strftime("%Y-%m-%d"),
        yesterday="2026-07-20",
        tomorrow="2026-07-22",
    )
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(content)
    return filepath


class TestJournalHandlerInputValidation:
    """Input validation — exit code 1 for missing/empty text."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_args_returns_error(self):
        _create_daily_note(self.tmpdir)
        stdout, rc = _run(journal_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()

    def test_empty_string_returns_error(self):
        _create_daily_note(self.tmpdir)
        stdout, rc = _run("", journal_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()

    def test_whitespace_only_returns_error(self):
        _create_daily_note(self.tmpdir)
        stdout, rc = _run("   ", journal_dir=self.tmpdir)
        assert rc == 1
        assert "no text provided" in stdout.lower()


class TestJournalHandlerFileErrors:
    """File error handling — exit code 2."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_daily_note_returns_error(self):
        """Exit code 2 when the daily note file does not exist."""
        stdout, rc = _run("some journal text", journal_dir=self.tmpdir)
        assert rc == 2
        assert "daily note not found" in stdout.lower()

    def test_permission_denied_on_write(self):
        """Exit code 2 when the daily note is read-only."""
        filepath = _create_daily_note(self.tmpdir)
        os.chmod(filepath, 0o444)
        try:
            stdout, rc = _run("some journal text", journal_dir=self.tmpdir)
            assert rc == 2
        finally:
            os.chmod(filepath, 0o644)


class TestJournalHandlerInsertion:
    """Core insertion behaviour."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filepath = _create_daily_note(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _read_note(self):
        with open(self.filepath, encoding="utf-8") as fh:
            return fh.read()

    def test_entry_added_under_journal_header(self):
        """Entry appears after '# Journal' and before '# Ilta'."""
        stdout, rc = _run("Päivä on alkanut hyvin", journal_dir=self.tmpdir)
        assert rc == 0
        content = self._read_note()
        journal_idx = content.index("# Journal")
        ilta_idx = content.index("# Ilta")
        entry_idx = content.index("Päivä on alkanut hyvin")
        assert journal_idx < entry_idx < ilta_idx

    def test_entry_has_timestamp_format(self):
        """Entry format is 'HH:MM text'."""
        _run("test entry", journal_dir=self.tmpdir)
        content = self._read_note()
        now = datetime.now()
        expected_prefix = now.strftime("%H:%M")
        # Find the line containing our entry
        for line in content.split("\n"):
            if "test entry" in line:
                assert line.startswith(expected_prefix), \
                    f"Expected line to start with '{expected_prefix}', got: {line}"
                break
        else:
            raise AssertionError("Entry 'test entry' not found in note")

    def test_multiple_entries_accumulate(self):
        """Multiple entries are appended in order under Journal."""
        _run("first entry", journal_dir=self.tmpdir)
        _run("second entry", journal_dir=self.tmpdir)
        content = self._read_note()
        first_idx = content.index("first entry")
        second_idx = content.index("second entry")
        assert first_idx < second_idx
        # Both should be between Journal and Ilta
        journal_idx = content.index("# Journal")
        ilta_idx = content.index("# Ilta")
        assert journal_idx < first_idx < ilta_idx
        assert journal_idx < second_idx < ilta_idx

    def test_existing_journal_content_preserved(self):
        """Existing content under Journal is not overwritten."""
        # Pre-populate with an existing entry
        content = self._read_note()
        content = content.replace("# Journal\n", "# Journal\n\n09:00 Existing entry\n")
        with open(self.filepath, "w", encoding="utf-8") as fh:
            fh.write(content)

        _run("new entry", journal_dir=self.tmpdir)
        updated = self._read_note()
        assert "09:00 Existing entry" in updated
        assert "new entry" in updated

    def test_other_sections_untouched(self):
        """Sections outside Journal are not modified."""
        _run("journal text", journal_dir=self.tmpdir)
        content = self._read_note()
        assert "# Tehtävät" in content
        assert "# Ilta" in content
        assert "pese hampaat" in content
        assert "Category: [[daily notes]]" in content

    def test_unicode_finnish_text(self):
        """Finnish characters are preserved correctly."""
        text = "Päivä on alkanut hyvin, linnut laulaa koodia syntyy."
        _run(text, journal_dir=self.tmpdir)
        content = self._read_note()
        assert text in content

    def test_success_message_contains_path(self):
        """Success output includes the file path."""
        stdout, rc = _run("path check", journal_dir=self.tmpdir)
        assert rc == 0
        assert self.filepath in stdout


class TestJournalHandlerEdgeCases:
    """Edge cases for the journal handler."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_journal_header_appends_section(self):
        """If '# Journal' header is missing, a new section is appended."""
        now = datetime.now()
        note_dir = os.path.join(self.tmpdir, now.strftime("%Y"), now.strftime("%m"))
        os.makedirs(note_dir, exist_ok=True)
        filepath = os.path.join(note_dir, now.strftime("%Y-%m-%d") + ".md")
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("# Some other header\n\nSome content\n")

        stdout, rc = _run("orphan entry", journal_dir=self.tmpdir)
        assert rc == 0
        with open(filepath, encoding="utf-8") as fh:
            content = fh.read()
        assert "# Journal" in content
        assert "orphan entry" in content

    def test_journal_at_end_of_file(self):
        """Journal section at EOF (no next header) works correctly."""
        now = datetime.now()
        note_dir = os.path.join(self.tmpdir, now.strftime("%Y"), now.strftime("%m"))
        os.makedirs(note_dir, exist_ok=True)
        filepath = os.path.join(note_dir, now.strftime("%Y-%m-%d") + ".md")
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("# Journal\n\n09:00 morning entry\n")

        stdout, rc = _run("evening entry", journal_dir=self.tmpdir)
        assert rc == 0
        with open(filepath, encoding="utf-8") as fh:
            content = fh.read()
        morning_idx = content.index("morning entry")
        evening_idx = content.index("evening entry")
        assert morning_idx < evening_idx

    def test_special_characters_in_text(self):
        """Text with markdown special characters is preserved."""
        text = "note with [brackets] and #hashtags and $symbols"
        _create_daily_note(self.tmpdir)
        stdout, rc = _run(text, journal_dir=self.tmpdir)
        assert rc == 0
        now = datetime.now()
        actual_path = os.path.join(
            self.tmpdir, now.strftime("%Y"), now.strftime("%m"),
            now.strftime("%Y-%m-%d") + ".md"
        )
        with open(actual_path, encoding="utf-8") as fh:
            content = fh.read()
        assert "[brackets]" in content
        assert "#hashtags" in content

    def test_long_text(self):
        """Long transcription text is handled without truncation."""
        _create_daily_note(self.tmpdir)
        long_text = "word " * 500
        stdout, rc = _run(long_text, journal_dir=self.tmpdir)
        assert rc == 0
        now = datetime.now()
        filepath = os.path.join(
            self.tmpdir, now.strftime("%Y"), now.strftime("%m"),
            now.strftime("%Y-%m-%d") + ".md"
        )
        with open(filepath, encoding="utf-8") as fh:
            content = fh.read()
        assert long_text.strip() in content
