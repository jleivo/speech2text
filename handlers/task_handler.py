#!/usr/bin/env python3
# v1.0.0
"""Voice task handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1], uses an LLM to extract
task text and resolve relative dates, then appends formatted
Obsidian task lines to voice_tasks.md.

Usage:
    python task_handler.py "<transcription text>"

Environment (set by the router from config.json):
    S2T_DESTINATION     Directory for voice_tasks.md (default: /srv/Obsidian/Inbox)
    S2T_API_BASE        LiteLLM API base URL (default: http://litellm.intra.leivo:4000/v1)
    S2T_API_KEY         LiteLLM API key (required)
    S2T_MODEL           Model name for task parsing (default: gpt-4o-mini)
    S2T_CA_BUNDLE       Path to CA bundle for TLS verification (optional)

Exit codes:
    0  success
    1  missing input
    2  configuration / file / LLM error
"""

import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Installer-facing self-description
# ---------------------------------------------------------------------------
MANIFEST = {
    "description": (
        "Parses voice transcriptions into Obsidian tasks with date "
        "resolution via LLM, appending to voice_tasks.md"
    ),
    "parameters": {
        "destination": {
            "description": "Directory for voice_tasks.md",
            "required": True,
            "default": "/srv/Obsidian/Inbox",
            "type": "path",
        },
        "api_base": {
            "description": "LiteLLM API base URL",
            "required": False,
            "default": "http://litellm.intra.leivo:4000/v1",
            "type": "string",
        },
        "api_key": {
            "description": "LiteLLM API key",
            "required": True,
            "default": "",
            "type": "string",
        },
        "model": {
            "description": "Model name for task parsing (via LiteLLM)",
            "required": False,
            "default": "gpt-4o-mini",
            "type": "string",
        },
    },
}

# ---------------------------------------------------------------------------
# Config — forwarded by the router as S2T_<KEY> env vars
# ---------------------------------------------------------------------------
DESTINATION: str = (
    os.environ.get("S2T_DESTINATION") or "/srv/Obsidian/Inbox"
)
API_BASE: str = (
    os.environ.get("S2T_API_BASE")
    or "http://litellm.intra.leivo:4000/v1"
)
API_KEY: str = os.environ.get("S2T_API_KEY", "")
MODEL: str = os.environ.get("S2T_MODEL") or "gpt-4o-mini"
CA_BUNDLE: str = os.environ.get("S2T_CA_BUNDLE", "")

TASK_FILE: str = "voice_tasks.md"

# ---------------------------------------------------------------------------
# Frontmatter for voice_tasks.md (created on first write)
# ---------------------------------------------------------------------------

def _build_frontmatter() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        "---\n"
        f"created: {today}\n"
        "tags: [voice-tasks]\n"
        "---\n"
        "\n"
        "# Voice Tasks\n"
        "\n"
    )


# ---------------------------------------------------------------------------
# LLM task extraction
# ---------------------------------------------------------------------------

_TASK_EXTRACTION_PROMPT = """You are a task extraction assistant. The user spoke a voice command \
containing one or more tasks. Extract each task and resolve any relative \
dates to ISO 8601 format (YYYY-MM-DD).

Rules:
- Return a JSON array of task objects.
- Each object has 'text' (the task description) and 'due' (YYYY-MM-DD or null).
- Resolve relative dates ('tomorrow', 'next Friday', 'kesäkuun eka päivä', \
'viikon päästä') using {reference_date} as today.
- If no date is mentioned, 'due' is null.
- Preserve the original language of the task text (Finnish, English, etc.).
- Strip filler words and keep the task concise.
- If the input contains no actual task (small talk, etc.), return an empty \
array [].

Example input: 'Tomorrow fix my bike brakes'
Example output: [{{'text': 'fix bike brakes', 'due': '2025-06-16'}}]

Example input: 'Huomenna korjaa pyörän kumi'
Example output: [{{'text': 'korjaa pyörän kumi', 'due': '2025-06-16'}}]

Now process this transcription (reference date: {reference_date}):
{task_text}
"""


def extract_tasks(text: str) -> list[dict]:
    """Call the LLM to extract tasks from *text*.

    Returns a list of dicts with keys "text" and "due" (str or None).
    Raises RuntimeError on LLM / JSON parse failure.
    """
    # pylint: disable=import-outside-toplevel
    import litellm  # deferred — not needed for MANIFEST / pure helpers
    # pylint: enable=import-outside-toplevel

    litellm.api_base = API_BASE
    litellm.api_key = API_KEY
    if CA_BUNDLE:
        litellm.verbose = False

    ref_date = datetime.now().strftime("%Y-%m-%d")
    prompt = _TASK_EXTRACTION_PROMPT.format(reference_date=ref_date, task_text=text)

    response = litellm.completion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if the model wraps the JSON.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}\nRaw: {raw}") from e

    if not isinstance(data, list):
        # Some models wrap the array in an object; try common keys.
        if isinstance(data, dict):
            for key in ("tasks", "result", "output"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                raise RuntimeError(
                    f"LLM response is not a JSON array: {raw}"
                )
        else:
            raise RuntimeError(f"LLM response is not a JSON array: {raw}")

    return data


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _append_tasks(filepath: str, tasks: list[dict]) -> None:
    """Append task lines to *filepath*.

    Creates the file with frontmatter if it does not exist.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if os.path.exists(filepath):
        mode = "a"
        prefix = ""
    else:
        mode = "w"
        prefix = _build_frontmatter()

    lines = []
    for task in tasks:
        task_text = task.get("text", "").strip()
        if not task_text:
            continue
        line = f"- [ ] #tsk {task_text}"
        due = task.get("due")
        if due:
            line += f" [due::{due}]"
        lines.append(line + "\n")

    with open(filepath, mode, encoding="utf-8") as fh:
        fh.write(prefix)
        for line in lines:
            fh.write(line)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _execute(text: str):
    """Do the work.  Return ``(exit_code, message)``."""

    # -- validate configuration ------------------------------------------
    if not API_KEY:
        return 2, "Error: missing S2T_API_KEY configuration"

    # -- extract tasks via LLM -------------------------------------------
    llm_error = None
    tasks = []
    try:
        tasks = extract_tasks(text)
    except ImportError as exc:
        llm_error = f"Error: litellm not installed — {exc}"
    except RuntimeError as exc:
        llm_error = f"Error: task parsing failed — {exc}"
    except Exception as exc:  # pylint: disable=broad-except
        llm_error = f"Error: LLM call failed — {type(exc).__name__}: {exc}"

    if llm_error:
        return 2, llm_error

    if not tasks:
        return 1, "No tasks extracted from the transcription."

    # -- write to voice_tasks.md ----------------------------------------
    filepath = os.path.join(DESTINATION, TASK_FILE)
    write_error = None
    try:
        _append_tasks(filepath, tasks)
    except PermissionError as exc:
        write_error = f"Error: permission denied — {exc}"
    except OSError as exc:
        write_error = f"Error: could not write tasks — {exc}"

    if write_error:
        return 2, write_error

    count = len(tasks)
    label = "task" if count == 1 else "tasks"
    return 0, f"Added {count} {label} to {filepath}"


def main():
    """Validate input, delegate to _execute, report the result."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: task_handler.py <text>")
        return 1

    code, message = _execute(sys.argv[1].strip())
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
