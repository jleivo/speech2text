#!/usr/bin/env python3
# v1.0.0
"""Append-to-file handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1] and appends it as a
new line to a file.  The filename supports date/time tokens
(YYYY, MM, DD, HH, MI, SS) that are expanded at runtime, so a
single config entry can route entries to date-stamped files.

Usage:
    python append_handler.py "<transcription text>"

Environment (set by the router from config.json):
    S2T_DESTINATION  Target directory for the file.
    S2T_FILENAME     Filename pattern, e.g. "blogi-YYYY-MM-DD.md".
    S2T_SOURCE_FILE  Original audio file path (optional, unused).

Exit codes:
    0  success
    1  missing input
    2  file / directory error
"""

import os
import sys
from datetime import datetime

# Installer-facing self-description.  scripts/install_handler.py imports
# each handler and reads MANIFEST to discover parameters and their types.
# "path" => the value must be writable by the systemd service (needs a
# ReadWritePaths entry).  Keep description lines < 100 chars.
MANIFEST = {
    "description": (
        "Appends each transcription as a new line to a file. "
        "Filename supports date tokens (YYYY-MM-DD)."
    ),
    "parameters": {
        "destination": {
            "description": "Directory where the target file lives",
            "required": True,
            "default": "/srv/Obsidian/Inbox",
            "type": "path",
        },
        "filename": {
            "description": (
                "Filename pattern. Tokens YYYY, MM, DD, HH, MI, SS "
                "are expanded at runtime. Example: blogi-YYYY-MM-DD.md"
            ),
            "required": True,
            "default": "notes.md",
            "type": "string",
        },
    },
}

# Date/time token -> strftime mapping.
# Order matters: YYYY must be replaced before MM so we don't
# partially replace inside the already-substituted %Y output.
_TOKEN_MAP = [
    ("YYYY", "%Y"),
    ("MM", "%m"),
    ("DD", "%d"),
    ("HH", "%H"),
    ("MI", "%M"),
    ("SS", "%S"),
]

# Config-driven: router sets S2T_DESTINATION / S2T_FILENAME from the
# magic-word block in config.json.
TARGET_DIR: str = (
    os.environ.get("S2T_DESTINATION")
    or "/srv/Obsidian/Inbox"
)

FILENAME_PATTERN: str = (
    os.environ.get("S2T_FILENAME")
    or "notes.md"
)


def expand_filename(pattern: str, now: datetime) -> str:
    """Expand date/time tokens in *pattern* using *now*.

    Tokens: YYYY MM DD HH MI SS  (MI = minutes, to avoid clash
    with MM = month).  Unknown text is passed through verbatim.
    """
    fmt = pattern
    for token, strftime_code in _TOKEN_MAP:
        fmt = fmt.replace(token, strftime_code)
    return now.strftime(fmt)


def main() -> int:
    """Entry point: validate input, append text, report result."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: append_handler.py <text>")
        return 1

    text = sys.argv[1].strip()
    now = datetime.now()
    filename = expand_filename(FILENAME_PATTERN, now)
    filepath = os.path.join(TARGET_DIR, filename)

    try:
        os.makedirs(TARGET_DIR, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except PermissionError as exc:
        print(f"Error: permission denied — {exc}")
        return 2
    except OSError as exc:
        print(f"Error: could not write — {exc}")
        return 2

    print(f"Appended to {filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
