"""E2E integration test — full pipeline with real audio file.

Places a real audio file in a temp watch directory, runs the pipeline
(transcribe -> route -> note_handler), and asserts the note was created.

Requires:
  - LiteLLM server available (skipped if not)
  - The Voice 001 audio file in tests/audio/
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

AUDIO_FILE = os.path.join(os.path.dirname(__file__),
                          "audio", "Voice 001_W_20250624_111642.m4a")


@pytest.mark.skipif(not os.path.exists(AUDIO_FILE),
                    reason="Voice 001 audio file not found")
def test_e2e_pipeline_with_voice_001():
    """Full pipeline: audio file -> transcribe -> route -> note_handler.

    This test uses the folder_watcher + router + note_handler as subprocesses
    to verify the end-to-end flow.
    """
    import requests

    litellm_url = os.environ.get("LITELLM_BASE_URL", "http://tuprpisrvp02.intra.leivo:4000")
    try:
        requests.get(f"{litellm_url}/health", timeout=3)
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip(f"LiteLLM server not available at {litellm_url}")

    # Set up temp directories
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = os.path.join(tmpdir, "watch")
        note_dir = os.path.join(tmpdir, "notes")
        os.makedirs(watch_dir)
        os.makedirs(note_dir)

        # Copy the audio file to the watch directory
        audio_dest = os.path.join(watch_dir, "test_voice.m4a")
        shutil.copy2(AUDIO_FILE, audio_dest)

        # Create a note_handler.py that just writes its input to a file
        handler_script = os.path.join(tmpdir, "note_handler.py")
        with open(handler_script, "w") as f:
            f.write('#!/usr/bin/env python3\n')
            f.write('import sys\n')
            f.write('import os\n')
            f.write('from datetime import datetime, timezone\n')
            f.write('\n')
            f.write('note_dir = os.environ.get("S2T_NOTE_DIR", "' + note_dir + '")\n')
            f.write('filepath = os.path.join(note_dir, "Voice Notes.md")\n')
            f.write('os.makedirs(note_dir, exist_ok=True)\n')
            f.write('\n')
            f.write('if not os.path.exists(filepath):\n')
            f.write('    with open(filepath, "w") as fh:\n')
            f.write('        fh.write("---\\\\n")\n')
            f.write('        fh.write("created: " + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "\\\\n")\n')
            f.write('        fh.write("tags: [voice-notes]\\\\n")\n')
            f.write('        fh.write("---\\\\n\\\\n# Voice Notes\\\\n\\\\n")\n')
            f.write('\n')
            f.write('timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")\n')
            f.write('entry = "- **[" + timestamp + "]** " + sys.argv[1] + "\\\\n"\n')
            f.write('\n')
            f.write('with open(filepath, "a") as fh:\n')
            f.write('    fh.write(entry)\n')

        # Create config for the pipeline
        import json
        config_path = os.path.join(tmpdir, "config.json")
        config = {
            "folder_to_watch": watch_dir,
            "watched_extensions": [".m4a"],
            "delete_after_processing": False,
            "backend": "litellm",
            "model": "whisper-1",
            "magic_words": {
                "NOTE": {"script_path": handler_script}
            },
            "default_action": {"script_path": handler_script},
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Run the folder_watcher process_audio_file directly
        # (simulating what happens when the watcher picks up the file)
        from src.folder_watcher import FolderWatcherHandler
        from src.config import load_config

        os.environ["OPENAI_API_BASE"] = litellm_url
        os.environ["S2T_NOTE_DIR"] = note_dir

        try:
            loaded_config = load_config(config_path)
            handler = FolderWatcherHandler(loaded_config)
            handler.process_audio_file(audio_dest)

            # Wait a moment for async writes
            time.sleep(1)

            # Assert the note file was created
            note_file = os.path.join(note_dir, "Voice Notes.md")
            assert os.path.exists(note_file), f"Note file was not created at {note_file}"

            content = open(note_file).read()
            assert "# Voice Notes" in content
            assert "- **[" in content  # timestamped entry
        finally:
            os.environ.pop("OPENAI_API_BASE", None)
            os.environ.pop("S2T_NOTE_DIR", None)
