#!/usr/bin/env python3
# v1.0.0
"""Google Docs handler for speech2text tool.

Standalone script — no dependency on core tool modules.
Receives transcribed text via sys.argv[1] and appends it as a new
line under a configured header line in a Google Doc.

The "header" is a plain-text line in the document (not a heading
style).  The handler finds the first paragraph whose text matches
the header, walks forward past consecutive non-empty paragraphs
(existing entries), and inserts the new entry at the end of that
section.

Usage:
    python gdocs_handler.py "<transcription text>"

Environment (set by the router from config.json):
    S2T_DOCUMENT_ID   Google Doc ID (the long string in the URL).
    S2T_HEADER        Exact text of the line that marks the section.
    S2T_CREDENTIALS   Path to a Google service account JSON key file.
    S2T_SOURCE_FILE   Original audio file path (optional, unused).

Exit codes:
    0  success
    1  missing input
    2  configuration / API / document error
"""

import os
import sys

# ---------------------------------------------------------------------------
# Installer-facing self-description
# ---------------------------------------------------------------------------
MANIFEST = {
    "description": (
        "Appends transcribed text under a plain-text header line "
        "in a Google Doc"
    ),
    "parameters": {
        "document_id": {
            "description": "Google Doc ID (the long string in the doc URL)",
            "required": True,
            "default": "",
            "type": "string",
        },
        "header": {
            "description": (
                "Exact text of the line that marks the section "
                "(e.g. KAUPPA)"
            ),
            "required": True,
            "default": "",
            "type": "string",
        },
        "credentials": {
            "description": (
                "Path to the Google service account JSON key file"
            ),
            "required": True,
            "default": "",
            "type": "string",
        },
    },
}

# ---------------------------------------------------------------------------
# Config — forwarded by the router as S2T_<KEY> env vars
# ---------------------------------------------------------------------------
DOCUMENT_ID: str = os.environ.get("S2T_DOCUMENT_ID", "")
HEADER_TEXT: str = os.environ.get("S2T_HEADER", "")
CREDENTIALS_PATH: str = os.environ.get("S2T_CREDENTIALS", "")

SCOPES = ["https://www.googleapis.com/auth/documents"]


# ---------------------------------------------------------------------------
# Document helpers (pure functions — unit-testable without Google libs)
# ---------------------------------------------------------------------------
def extract_paragraphs(document):
    """Return [(text, start_index, end_index)] for every paragraph.

    *document* is the raw response from ``documents.get``.  Non-paragraph
    structural elements (section breaks, tables) are skipped.  Multiple
    text runs inside a single paragraph are concatenated.
    """
    paragraphs = []
    for element in document.get("body", {}).get("content", []):
        para = element.get("paragraph")
        if para is None:
            continue
        text = "".join(
            run.get("textRun", {}).get("content", "")
            for run in para.get("elements", [])
        )
        paragraphs.append(
            (text, element["startIndex"], element["endIndex"])
        )
    return paragraphs


def find_insertion_index(paragraphs, header):
    """Return the character index at which to insert a new entry.

    Walks *paragraphs* (as returned by :func:`extract_paragraphs`) and
    finds the first paragraph whose stripped text equals *header*
    (case-insensitive).  From there it advances past every consecutive
    non-empty paragraph (the existing entries).  The returned index is
    the ``endIndex`` of the last paragraph in that section — inserting
    text there places it on a new line right after the last entry.

    Returns ``None`` when *header* is not found.
    """
    header_lower = header.strip().lower()
    header_idx = None

    for i, (text, _start, _end) in enumerate(paragraphs):
        if text.strip().lower() == header_lower:
            header_idx = i
            break

    if header_idx is None:
        return None

    # Advance past consecutive non-empty paragraphs (existing entries).
    # Stop at a blank line OR a repeat of the header (new section).
    last_idx = header_idx
    for j in range(header_idx + 1, len(paragraphs)):
        stripped = paragraphs[j][0].strip()
        if not stripped:
            break
        if stripped.lower() == header_lower:
            break
        last_idx = j

    return paragraphs[last_idx][2]  # endIndex


# ---------------------------------------------------------------------------
# Google Docs API
# ---------------------------------------------------------------------------
def build_service(credentials_path):
    """Build a Docs API service from a service-account key file.

    Imports are deferred so the rest of the module (MANIFEST, pure
    helpers) stays importable even when the Google libraries are not
    installed.
    """
    # pylint: disable=import-outside-toplevel
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES,
    )
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def append_under_header(service, doc_id, header, entry_text):
    """Append *entry_text* as a new line under *header* in the doc.

    Returns the document title on success.
    Raises ``RuntimeError`` when the header line is not found.
    """
    doc = service.documents().get(documentId=doc_id).execute()
    title = doc.get("title", "(untitled)")
    paragraphs = extract_paragraphs(doc)
    index = find_insertion_index(paragraphs, header)

    if index is None:
        raise RuntimeError(
            f"Header '{header}' not found in document '{title}'. "
            "Add the header text as a line in the document first."
        )

    requests = [{
        "insertText": {
            "location": {"index": index},
            "text": entry_text + "\n",
        },
    }]
    service.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests},
    ).execute()
    return title


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _execute(text):
    """Do the work.  Return ``(exit_code, message)``."""
    # -- validate configuration ------------------------------------------
    missing = []
    if not DOCUMENT_ID:
        missing.append("S2T_DOCUMENT_ID")
    if not HEADER_TEXT:
        missing.append("S2T_HEADER")
    if not CREDENTIALS_PATH:
        missing.append("S2T_CREDENTIALS")
    if missing:
        return 2, f"Error: missing configuration: {', '.join(missing)}"

    # -- call the API ----------------------------------------------------
    try:
        if not os.path.isfile(CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"credentials file not found: {CREDENTIALS_PATH}"
            )
        service = build_service(CREDENTIALS_PATH)
        title = append_under_header(
            service, DOCUMENT_ID, HEADER_TEXT, text,
        )
    except ImportError as exc:
        return 2, f"Error: Google API libraries not installed — {exc}"
    except RuntimeError as exc:
        return 2, f"Error: {exc}"
    except (PermissionError, OSError) as exc:
        return 2, f"Error: {exc}"
    except Exception as exc:  # pylint: disable=broad-except
        return (
            2,
            f"Error: Google Docs API failure — "
            f"{type(exc).__name__}: {exc}",
        )

    return 0, f"Added to '{title}' under '{HEADER_TEXT}': {text}"


def main():
    """Validate input, delegate to _execute, report the result."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Error: no text provided. Usage: gdocs_handler.py <text>")
        return 1

    code, message = _execute(sys.argv[1].strip())
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
