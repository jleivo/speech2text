#!/usr/bin/env python3
# v1.0.0
"""Journal handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1] and appends a timestamped
entry under the '# Journal' header in today's daily note.

Daily note path: <base_dir>/YYYY/MM/YYYY-MM-DD.md

Usage:
    python journal_handler.py "<transcription text>"

Environment:
    S2T_JOURNAL_DIR  Base directory for daily notes
                     (default: /srv/Obsidian/Archives/dailynotes)

Exit codes:
    0  success
    1  missing input
    2  file / directory error
"""

import os
import sys
from datetime import datetime

JOURNAL_DIR: str = os.environ.get(
    "S2T_JOURNAL_DIR", "/srv/Obsidian/Archives/dailynotes"
)

JOURNAL_HEADER = "# Journal"


def _daily_note_path(now: datetime) -> str:
    """Build the path to today's daily note: <base>/YYYY/MM/YYYY-MM-DD.md"""
    return os.path.join(
        JOURNAL_DIR,
        now.strftime("%Y"),
        now.strftime("%m"),
        now.strftime("%Y-%m-%d") + ".md",
    )


def _insert_entry(content: str, entry: str) -> str:
    """Insert a journal entry under the '# Journal' header.

    The entry is appended after existing lines in the Journal section,
    just before the next top-level '#' header (or end of file).
    If no '# Journal' header exists, a new section is appended at EOF.
    """
    lines = content.split("\n")

    # Find the Journal header
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip() == JOURNAL_HEADER:
            header_idx = i
            break

    if header_idx is None:
        # No Journal header — append a new section at end of file
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(JOURNAL_HEADER)
        lines.append("")
        lines.append(entry)
        return "\n".join(lines)

    # Skip blank lines immediately after the header
    insert_idx = header_idx + 1
    while insert_idx < len(lines) and not lines[insert_idx].strip():
        insert_idx += 1

    # Find where the Journal section ends — next top-level '# ' header
    section_end = insert_idx
    while section_end < len(lines):
        stripped = lines[section_end].strip()
        if stripped.startswith("# ") and stripped != JOURNAL_HEADER:
            break
        section_end += 1

    # Walk back past trailing blank lines before the next header
    while section_end > insert_idx and not lines[section_end - 1].strip():
        section_end -= 1

    lines.insert(section_end, entry)
    return "\n".join(lines)


def main() -> int:
    """Entry point: validate input, locate today's note, insert entry."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: journal_handler.py <text>")
        return 1

    text = sys.argv[1].strip()
    now = datetime.now()  # Local time — journal entries use local timestamps

    entry = now.strftime("%H:%M") + " " + text
    filepath = _daily_note_path(now)

    if not os.path.isfile(filepath):
        print(f"Error: daily note not found — {filepath}")
        return 2

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        print(f"Error: could not read daily note — {exc}")
        return 2

    updated = _insert_entry(content, entry)

    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(updated)
    except PermissionError as exc:
        print(f"Error: permission denied — {exc}")
        return 2
    except OSError as exc:
        print(f"Error: could not write daily note — {exc}")
        return 2

    print(f"Journal entry added to {filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
