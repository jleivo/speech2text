#!/usr/bin/env python3
# v1.2.0
"""Append-to-file handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1] and appends it as a
new line to a file.  The filename supports date/time tokens
(YYYY, MM, DD, HH, MI, SS) that are expanded at runtime, so a
single config entry can route entries to date-stamped files.

When the target file does not yet exist and a template is
configured (S2T_TEMPLATE), the template content is written first
to seed the file structure.  Templates may use either the
handler's own token syntax (YYYY-MM-DD) or a safe subset of
Obsidian Templater tags (<% tp.date.now("YYYY-MM-DD") %>,
<% tp.file.title %>, <% tp.file.creation_date(...) %>).
Unsupported Templater tags (interactive prompts, file moves,
user scripts) are left intact with a warning on stderr.

Usage:
    python append_handler.py "<transcription text>"

Environment (set by the router from config.json):
    S2T_DESTINATION  Target directory for the file.
    S2T_FILENAME     Filename pattern, e.g. "blogi-YYYY-MM-DD.md".
    S2T_TEMPLATE     Path to a template file used to seed new
                     files.  Relative paths resolve against the
                     repository root (parent of handlers/).
    S2T_SOURCE_FILE  Original audio file path (optional, unused).

Exit codes:
    0  success
    1  missing input
    2  file / directory error
"""

import os
import re
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# MANIFEST
# ---------------------------------------------------------------------------
MANIFEST = {
    "description": (
        "Appends each transcription as a new line to a file. "
        "Filename and template support date tokens and a safe "
        "subset of Obsidian Templater tags."
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
        "template": {
            "description": (
                "Path to a template file that seeds new files. "
                "Supports handler tokens and safe Templater tags. "
                "Relative paths resolve against the repo root."
            ),
            "required": False,
            "default": "",
            "type": "string",
        },
    },
}

# ---------------------------------------------------------------------------
# Handler's own date/time token syntax
# ---------------------------------------------------------------------------
_TOKEN_MAP = [
    ("YYYY", "%Y"),
    ("MM", "%m"),
    ("DD", "%d"),
    ("HH", "%H"),
    ("MI", "%M"),
    ("SS", "%S"),
]

# ---------------------------------------------------------------------------
# Moment.js format conversion (for Templater tag expansion)
# ---------------------------------------------------------------------------
# Matches [literal] blocks or known Moment tokens, longest first
# within each family so the regex engine picks the right one.
_MOMENT_PATTERN = re.compile(
    r"\[([^\]]*)\]"
    r"|(YYYY|YY"
    r"|MMMM|MMM|MM|M"
    r"|Do|DD|D"
    r"|dddd|ddd|dd|d"
    r"|HH|H|hh|h"
    r"|mm|m"
    r"|ss|s"
    r"|WW|ww"
    r"|A|a|X|x|Q)"
)

_MOMENT_TO_STRFTIME = {
    "YYYY": "%Y", "YY": "%y",
    "MMMM": "%B", "MMM": "%b", "MM": "%m", "M": "%-m",
    "DD": "%d", "D": "%-d",
    "dddd": "%A", "ddd": "%a", "dd": "%a", "d": "%w",
    "HH": "%H", "H": "%-H", "hh": "%I", "h": "%-I",
    "mm": "%M", "m": "%-M",
    "ss": "%S", "s": "%-S",
    "A": "%p",
    "X": "%s",
    "WW": "%W", "ww": "%U",
}

# ---------------------------------------------------------------------------
# Templater tag parsing
# ---------------------------------------------------------------------------
# Handles <% ... %>, <%- ... %>, <% ... -%>, <%- ... -%>.
_TEMPLATER_TAG_RE = re.compile(
    r"<%-?\s*(.*?)\s*-?%>", re.DOTALL
)

_UNSAFE_PREFIXES = (
    "tp.system.",
    "tp.file.cursor",
    "tp.file.move",
    "tp.file.rename",
    "tp.file.delete",
    "tp.file.create_new",
    "tp.user.",
    "tp.obsidian.",
    "tp.web.",
    "tp.hooks.",
)

# ---------------------------------------------------------------------------
# Config-driven variables
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

TARGET_DIR: str = (
    os.environ.get("S2T_DESTINATION")
    or "/srv/Obsidian/Inbox"
)

FILENAME_PATTERN: str = (
    os.environ.get("S2T_FILENAME")
    or "notes.md"
)

TEMPLATE_PATH: str = os.environ.get("S2T_TEMPLATE", "")


# ---------------------------------------------------------------------------
# Moment.js helpers
# ---------------------------------------------------------------------------
def _ordinal(day: int) -> str:
    """Return the English ordinal for a day (1st, 2nd, 3rd…)."""
    if 11 <= day <= 13:
        return f"{day}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _format_moment(fmt: str, dt: datetime) -> str:
    """Format *dt* using a Moment.js format string.

    Handles common Moment tokens; [literal] blocks pass through
    unchanged.  Unrecognised tokens are left as-is.
    """
    def _replace(match: re.Match) -> str:
        if match.group(1) is not None:
            return match.group(1)  # [literal] text
        token = match.group(2)
        special = {
            "Do": lambda: _ordinal(dt.day),
            "x": lambda: str(int(dt.timestamp() * 1000)),
            "Q": lambda: str((dt.month - 1) // 3 + 1),
            "a": lambda: dt.strftime("%p").lower(),
        }
        if token in special:
            return special[token]()
        strftime_code = _MOMENT_TO_STRFTIME.get(token)
        if strftime_code is None:
            return token  # unknown — pass through
        return dt.strftime(strftime_code)

    return _MOMENT_PATTERN.sub(_replace, fmt)


# ---------------------------------------------------------------------------
# Templater tag expansion
# ---------------------------------------------------------------------------
def _split_args(raw: str) -> list:
    """Split on commas, respecting quoted substrings."""
    parts: list = []
    current: list = []
    in_quote = None
    for char in raw:
        if char in "\"'" and in_quote is None:
            in_quote = char
            current.append(char)
        elif char == in_quote:
            in_quote = None
            current.append(char)
        elif char == "," and in_quote is None:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _parse_date_now(expr: str, now: datetime) -> str:
    """Expand a tp.date.now(...) expression to a formatted date.

    Supports tp.date.now("FORMAT") and tp.date.now("FORMAT", N)
    where N is an integer day offset.  Further arguments
    (reference date) are accepted but ignored.
    """
    inner = expr[expr.index("(") + 1: expr.rindex(")")]
    parts = _split_args(inner)

    fmt = "YYYY-MM-DD"
    if parts and parts[0].strip():
        fmt = parts[0].strip().strip("\"'")

    offset_days = 0
    if len(parts) > 1:
        try:
            offset_days = int(parts[1].strip())
        except ValueError:
            print(
                f"Warning: non-numeric offset in "
                f"tp.date.now: {parts[1].strip()!r}; using 0",
                file=sys.stderr,
            )

    target = now + timedelta(days=offset_days)
    return _format_moment(fmt, target)


def _parse_creation_date(expr: str, now: datetime) -> str:
    """Expand tp.file.creation_date(...) — treated as *now*.

    The file is being created at this moment, so creation date
    equals the current time.
    """
    inner = expr[expr.index("(") + 1: expr.rindex(")")]
    parts = _split_args(inner)
    fmt = "YYYY-MM-DD"
    if parts and parts[0].strip():
        fmt = parts[0].strip().strip("\"'")
    return _format_moment(fmt, now)


def expand_templater(
    content: str, now: datetime, file_title: str
) -> str:
    """Expand safe Templater tags in *content*.

    Supported: tp.date.now, tp.file.title,
    tp.file.creation_date.  Unsupported tags are left intact
    with a warning on stderr so they can still be rendered by
    Obsidian if the file is opened there.
    """
    warnings: list = []

    def _replace(match: re.Match) -> str:
        expr = match.group(1).strip()

        if expr.startswith("tp.date.now"):
            return _parse_date_now(expr, now)
        if expr.startswith("tp.file.creation_date"):
            return _parse_creation_date(expr, now)
        if expr == "tp.file.title":
            return file_title

        warnings.append(expr)
        return match.group(0)  # leave intact

    result = _TEMPLATER_TAG_RE.sub(_replace, content)

    for expr in warnings:
        print(
            f"Warning: unsupported Templater tag left "
            f"unexpanded: <% {expr} %>",
            file=sys.stderr,
        )

    return result


# ---------------------------------------------------------------------------
# Handler's own token expansion
# ---------------------------------------------------------------------------
def expand_tokens(pattern: str, now: datetime) -> str:
    """Expand YYYY/MM/DD/HH/MI/SS tokens in *pattern*."""
    fmt = pattern
    for token, strftime_code in _TOKEN_MAP:
        fmt = fmt.replace(token, strftime_code)
    return now.strftime(fmt)


def _expand_bare_tokens_outside_tags(
    content: str, now: datetime
) -> str:
    """Expand handler tokens only in text outside <% %> tags.

    Prevents bare-token expansion from mangling unsupported
    Templater tags that were intentionally left intact.
    """
    result: list = []
    last_end = 0
    for match in _TEMPLATER_TAG_RE.finditer(content):
        result.append(
            expand_tokens(content[last_end:match.start()], now)
        )
        result.append(match.group(0))
        last_end = match.end()
    result.append(expand_tokens(content[last_end:], now))
    return "".join(result)


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
def _resolve_template_path(raw: str) -> str:
    """Absolute as-is; relative resolves against the repo root."""
    if os.path.isabs(raw):
        return raw
    return os.path.join(_REPO_ROOT, raw)


def _read_template(
    path: str, now: datetime, file_title: str
) -> str:
    """Read a template and expand all supported tokens.

    Templater tags are expanded first (their inner Moment format
    strings must not be double-processed by the bare-token pass),
    then the handler's own tokens in text outside any remaining
    (unsupported) tags.
    """
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    content = expand_templater(content, now, file_title)
    content = _expand_bare_tokens_outside_tags(content, now)
    return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Entry point: validate input, append text, report result."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(
            "Error: no text provided. "
            "Usage: append_handler.py <text>"
        )
        return 1

    text = sys.argv[1].strip()
    now = datetime.now()
    filename = expand_tokens(FILENAME_PATTERN, now)
    filepath = os.path.join(TARGET_DIR, filename)
    file_is_new = not os.path.exists(filepath)

    # tp.file.title = filename without extension
    file_title = os.path.splitext(filename)[0]

    try:
        os.makedirs(TARGET_DIR, exist_ok=True)

        if file_is_new and TEMPLATE_PATH:
            tmpl_path = _resolve_template_path(TEMPLATE_PATH)
            template_content = _read_template(
                tmpl_path, now, file_title
            )
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(template_content)
                if not template_content.endswith("\n"):
                    fh.write("\n")

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
