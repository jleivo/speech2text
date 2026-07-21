#!/usr/bin/env python3
"""Tests for handlers/general_handler.py."""
import os
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime

# Path to the handler script — run it as a subprocess like the router does
HANDLER = os.path.join(os.path.dirname(__file__), "..", "handlers", "general_handler.py")


class TestSlugify:
    """Test _slugify via the handler's output."""

    def test_basic_slug_from_text(self, tmp_path):
        """Slug is derived from first words of text."""
        note_dir = str(tmp_path / "inbox")
        result = subprocess.run(
            [sys.executable, HANDLER, "Hello world this is a test"],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": note_dir},
        )
        assert result.returncode == 0
        # Check that a file was created with the expected slug prefix
        files = os.listdir(note_dir)
        assert len(files) == 1
        # Filename should start with "hello-world-this-is-a-test"
        assert files[0].startswith("hello-world-this-is-a-test-")
        assert files[0].endswith(".md")

    def test_slug_truncates_long_text(self, tmp_path):
        """Slug is truncated when text is very long."""
        note_dir = str(tmp_path / "inbox")
        long_text = " ".join(["word"] * 50)
        result = subprocess.run(
            [sys.executable, HANDLER, long_text],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": note_dir},
        )
        assert result.returncode == 0
        files = os.listdir(note_dir)
        filename = files[0]
        # Slug part (before the date) should be reasonable length
        slug_part = filename.split("-20")[0]  # Everything before the date portion
        assert len(slug_part) <= 60


class TestFrontmatter:
    """Test that notes have correct frontmatter."""

    def _read_note(self, tmp_path):
        note_dir = str(tmp_path / "inbox")
        files = os.listdir(note_dir)
        filepath = os.path.join(note_dir, files[0])
        with open(filepath) as f:
            return f.read()

    def test_has_created_field(self, tmp_path):
        """Note has 'created' frontmatter with today's date."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        subprocess.run(
            [sys.executable, HANDLER, "Test note content"],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        content = self._read_note(tmp_path)
        assert "---" in content
        assert "created: " in content
        # Check date format is YYYY-MM-DD
        for line in content.split("\n"):
            if line.startswith("created:"):
                date_part = line.split(": ")[1].strip()
                datetime.strptime(date_part, "%Y-%m-%d")
                break

    def test_has_transcribed_field(self, tmp_path):
        """Note has 'transcribed' frontmatter with ISO datetime."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        subprocess.run(
            [sys.executable, HANDLER, "Test note content"],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        content = self._read_note(tmp_path)
        assert "transcribed: " in content

    def test_has_tags(self, tmp_path):
        """Note has voice-note tag in frontmatter."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        subprocess.run(
            [sys.executable, HANDLER, "Test note content"],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        content = self._read_note(tmp_path)
        assert "tags: [voice-note]" in content

    def test_content_after_frontmatter(self, tmp_path):
        """Transcription text appears after frontmatter."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        text = "This is the actual transcription content"
        subprocess.run(
            [sys.executable, HANDLER, text],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        content = self._read_note(tmp_path)
        # Content should appear after the closing ---
        parts = content.split("---", 2)
        body = parts[2] if len(parts) > 2 else ""
        assert text in body

    def test_source_file_in_frontmatter(self, tmp_path):
        """Source file path appears in frontmatter when S2T_SOURCE_FILE is set."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        env = {**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")}
        env["S2T_SOURCE_FILE"] = "/srv/speech2text/audio_transfer/recording.wav"
        subprocess.run(
            [sys.executable, HANDLER, "Test content"],
            capture_output=True, text=True,
            env=env,
        )
        content = self._read_note(tmp_path)
        assert "source: /srv/speech2text/audio_transfer/recording.wav" in content


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_no_input(self):
        """Returns exit code 1 when no text is provided."""
        result = subprocess.run(
            [sys.executable, HANDLER],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "no text provided" in result.stderr or "no text provided" in result.stdout

    def test_empty_input(self, tmp_path):
        """Returns exit code 1 when text is empty/whitespace."""
        result = subprocess.run(
            [sys.executable, HANDLER, "   "],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        assert result.returncode == 1

    def test_special_characters_in_text(self, tmp_path):
        """Text with special characters is handled correctly."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        text = "Buy groceries: milk, eggs & bread! Cost: €5.99"
        result = subprocess.run(
            [sys.executable, HANDLER, text],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        assert result.returncode == 0
        filepath = os.path.join(str(tmp_path / "inbox"), os.listdir(str(tmp_path / "inbox"))[0])
        with open(filepath) as f:
            content = f.read()
        assert text in content

    def test_punctuation_only_input(self, tmp_path):
        """Text that is only punctuation falls back to 'note' slug."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        result = subprocess.run(
            [sys.executable, HANDLER, "... !?! ..."],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        assert result.returncode == 0
        files = os.listdir(str(tmp_path / "inbox"))
        assert len(files) == 1
        assert files[0].startswith("note-")

    def test_creates_parent_directory(self, tmp_path):
        """Creates the inbox directory if it doesn't exist."""
        inbox = tmp_path / "nested" / "deep" / "inbox"
        result = subprocess.run(
            [sys.executable, HANDLER, "Test"],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(inbox)},
        )
        assert result.returncode == 0
        assert inbox.exists()

    def test_permission_denied(self):
        """Returns exit code 2 on permission denied."""
        # Use a read-only directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            ro_dir = os.path.join(tmp_dir, "readonly")
            os.makedirs(ro_dir, mode=0o000)
            try:
                result = subprocess.run(
                    [sys.executable, HANDLER, "Test"],
                    capture_output=True, text=True,
                    env={**os.environ, "S2T_NOTE_DIR": ro_dir},
                )
                assert result.returncode == 2
            finally:
                os.chmod(ro_dir, 0o700)


class TestFilenameUniqueness:
    """Test that filenames are unique."""

    def test_unique_names_for_different_text(self, tmp_path):
        """Different text produces different filenames."""
        note_dir = str(tmp_path / "inbox")
        texts = ["Meeting notes", "Shopping list", "Idea for project"]
        for text in texts:
            result = subprocess.run(
                [sys.executable, HANDLER, text],
                capture_output=True, text=True,
                env={**os.environ, "S2T_NOTE_DIR": note_dir},
            )
            assert result.returncode == 0
        # All files should be unique — one per text
        files = os.listdir(note_dir)
        assert len(files) == len(texts)
        assert len(files) == len(set(files))

    def test_multiline_text(self, tmp_path):
        """Multiline transcription text is preserved in the note body."""
        os.makedirs(tmp_path / "inbox", exist_ok=True)
        text = "Line one\nLine two\nLine three"
        result = subprocess.run(
            [sys.executable, HANDLER, text],
            capture_output=True, text=True,
            env={**os.environ, "S2T_NOTE_DIR": str(tmp_path / "inbox")},
        )
        assert result.returncode == 0
        filepath = os.path.join(str(tmp_path / "inbox"), os.listdir(str(tmp_path / "inbox"))[0])
        with open(filepath) as f:
            content = f.read()
        # All three lines should be in the body
        body = content.split("---", 2)[2]
        assert "Line one" in body
        assert "Line two" in body
        assert "Line three" in body
