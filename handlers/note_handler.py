#!/usr/bin/env python3
# v1.0.0
"""Voice note handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1] and appends it
to a voice notes file in the Obsidian vault.

Usage:
    python note_handler.py "remaining text after magic word"

Exit codes:
    0  success
    1  missing input
    2  file / directory error
"""

import os
import sys
from datetime import datetime, timezone

# Installer-facing self-description (see journal_handler.py for details).
MANIFEST = {
    "description": "Appends timestamped voice notes to Voice Notes.md in the Obsidian inbox",
    "parameters": {
        "destination": {
            "description": "Directory containing Voice Notes.md (created if missing)",
            "required": True,
            "default": "/srv/Obsidian/Inbox",
            "type": "path",
        }
    },
}

# The Obsidian inbox directory where Voice Notes.md lives.
# S2T_DESTINATION is set by the router from config.json ("destination" key).
# S2T_NOTE_DIR is the legacy fallback. Override either for testing.
NOTE_DIR: str = (
    os.environ.get("S2T_DESTINATION")
    or os.environ.get("S2T_NOTE_DIR")
    or "/srv/Obsidian/Inbox"
)
NOTE_FILE: str = "Voice Notes.md"

# Frontmatter written once when the file is created.
def _build_frontmatter() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        "---\n"
        f"created: {today}\n"
        "tags: [voice-notes]\n"
        "---\n"
        "\n"
        "# Voice Notes\n"
        "\n"
    )


def _append_note(filepath: str, text: str) -> None:
    """Append a timestamped note entry to *filepath*.

    Create the file with frontmatter if it does not exist yet.
    The parent directory is created recursively if missing.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if os.path.exists(filepath):
        mode = "a"
        prefix = ""
    else:
        mode = "w"
        prefix = _build_frontmatter()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- **[{timestamp}]** {text}\n"

    with open(filepath, mode, encoding="utf-8") as fh:
        fh.write(prefix)
        fh.write(entry)


def main() -> int:
    """Entry point: validate input, append the note to Voice Notes.md."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: note_handler.py <text>")
        return 1

    text = sys.argv[1].strip()
    filepath = os.path.join(NOTE_DIR, NOTE_FILE)

    try:
        _append_note(filepath, text)
    except PermissionError as exc:
        print(f"Error: permission denied — {exc}")
        return 2
    except OSError as exc:
        print(f"Error: could not write note — {exc}")
        return 2

    print(f"Note saved to {filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
