#!/usr/bin/env python3
# v1.0.0
"""General note handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives full transcribed text via sys.argv[1] and creates a
uniquely-named note file in the Obsidian inbox.

Usage:
    python general_handler.py "<full transcription text>"

Exit codes:
    0  success
    1  missing input
    2  file / directory error
"""

import os
import re
import sys
from datetime import datetime, timezone

# Installer-facing self-description (see journal_handler.py for details).
MANIFEST = {
    "description": "Creates a uniquely-named markdown note in the Obsidian inbox",
    "parameters": {
        "destination": {
            "description": "Directory where note files are created (created if missing)",
            "required": True,
            "default": "/srv/Obsidian/Inbox",
            "type": "path",
        }
    },
}

# The Obsidian inbox directory where notes are created.
# S2T_DESTINATION is set by the router from config.json ("destination" key).
# S2T_NOTE_DIR is the legacy fallback. Override either for testing.
NOTE_DIR: str = (
    os.environ.get("S2T_DESTINATION")
    or os.environ.get("S2T_NOTE_DIR")
    or "/srv/Obsidian/Inbox"
)


def _slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a filesystem-safe slug.

    - Lowercase
    - Replace whitespace and punctuation with hyphens
    - Collapse consecutive hyphens
    - Strip leading/trailing hyphens
    - Truncate to max_len
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def _build_filename(slug: str, timestamp: datetime) -> str:
    """Build a unique filename: <slug>-<YYYYMMDD>-<HHMMSS>.md"""
    date_part = timestamp.strftime("%Y%m%d")
    time_part = timestamp.strftime("%H%M%S")
    return f"{slug}-{date_part}-{time_part}.md"


def _build_frontmatter(timestamp: datetime, source_file: str = "") -> str:
    """Build YAML frontmatter for the note."""
    date_str = timestamp.strftime("%Y-%m-%d")
    datetime_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")
    # Format timezone with colon (e.g., +00:00)
    if datetime_str[-4:].isdigit():
        datetime_str = datetime_str[:-2] + ":" + datetime_str[-2:]

    lines = [
        "---",
        f"created: {date_str}",
        f"transcribed: {datetime_str}",
        "tags: [voice-note]",
    ]
    if source_file:
        lines.append(f"source: {source_file}")
    lines.append("---")
    return "\n".join(lines)


def _truncate_for_slug(text: str, max_words: int = 8) -> str:
    """Take the first N words of the text for the slug."""
    words = text.split()[:max_words]
    return " ".join(words)


def main() -> int:
    """Entry point: validate input, write a uniquely-named note file."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: general_handler.py <text>")
        return 1

    text = sys.argv[1].strip()
    timestamp = datetime.now(timezone.utc)

    # Source audio file path, if provided via env
    source_file = os.environ.get("S2T_SOURCE_FILE", "")

    # Build unique filename from first few words of the transcription
    slug_text = _truncate_for_slug(text)
    slug = _slugify(slug_text)

    if not slug:
        # Fallback if slugification produced nothing (e.g., all punctuation)
        slug = "note"

    filename = _build_filename(slug, timestamp)
    filepath = os.path.join(NOTE_DIR, filename)

    # Handle filename collision (unlikely but possible if two notes in the same second)
    if os.path.exists(filepath):
        # Add microseconds to disambiguate
        time_part = timestamp.strftime("%H%M%S%f")
        filename = f"{slug}-{timestamp.strftime('%Y%m%d')}-{time_part}.md"
        filepath = os.path.join(NOTE_DIR, filename)

    try:
        os.makedirs(NOTE_DIR, exist_ok=True)

        frontmatter = _build_frontmatter(timestamp, source_file)
        content = f"{frontmatter}\n\n{text}\n"

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)

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
