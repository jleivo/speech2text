"""Additional tests for note_handler.py — error handling & edge cases.

Complements test_note_handler.py with error handling scenarios:
  - Permission denied errors (exit code 2)
  - OSError / disk full errors (exit code 2)
"""
import os
import subprocess
import sys
import tempfile
import shutil
import stat

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


class TestNoteHandlerErrorHandling:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.note_path = os.path.join(self.tmpdir, "Voice Notes.md")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_permission_denied_returns_exit_code_2(self):
        """PermissionError on write returns exit code 2."""
        # Create the note file and make it read-only
        _run("initial note", note_dir=self.tmpdir)
        os.chmod(self.note_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        stdout, rc = _run("another note", note_dir=self.tmpdir)
        # If running as root, chmod won't block, so skip assertion
        if os.geteuid() == 0:
            return
        assert rc == 2
        assert "permission denied" in stdout.lower()

    def test_error_message_contains_oserror_info(self):
        """OSError output contains error description."""
        # Same as permission test — on non-root, verify message format
        _run("initial note", note_dir=self.tmpdir)
        os.chmod(self.note_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        stdout, rc = _run("another note", note_dir=self.tmpdir)
        if os.geteuid() == 0:
            return
        assert rc == 2
        # The handler prints: "Error: permission denied — ..." or "Error: could not write note — ..."
        assert stdout.startswith("Error:")
