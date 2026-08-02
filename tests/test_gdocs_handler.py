#!/usr/bin/env python3
"""Tests for gdocs_handler.py.

Runs the handler as a subprocess (matching how the router invokes it)
for input-validation and config-validation tests.  Pure helper functions
are imported directly for unit tests — no Google libraries required.
"""
import os
import subprocess
import sys

SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "handlers", "gdocs_handler.py",
)

# Import pure helpers directly (no Google deps needed).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "handlers")
)
from gdocs_handler import (  # noqa: E402  pylint: disable=wrong-import-position
    extract_paragraphs,
    find_insertion_index,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _run(text=None, env_override=None):
    """Run handler as subprocess. Return (stdout, returncode)."""
    cmd = [sys.executable, SCRIPT]
    if text is not None:
        cmd.append(text)
    env = os.environ.copy()
    # Clear any real config so tests are deterministic.
    for key in ("S2T_DOCUMENT_ID", "S2T_HEADER", "S2T_CREDENTIALS"):
        env.pop(key, None)
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=30,
    )
    return result.stdout.strip(), result.returncode


def _make_document(paragraphs):
    """Build a minimal documents.get response from a list of texts.

    Each paragraph gets startIndex/endIndex spaced by len(text)+1
    (the +1 accounts for the implicit newline Google Docs appends).
    """
    content = []
    idx = 1  # index 0 is reserved by the API
    for text in paragraphs:
        end = idx + len(text) + 1
        content.append({
            "startIndex": idx,
            "endIndex": end,
            "paragraph": {
                "elements": [
                    {"textRun": {"content": text + "\n"}},
                ],
            },
        })
        idx = end
    return {"title": "Test Doc", "body": {"content": content}}


FULL_CONFIG = {
    "S2T_DOCUMENT_ID": "fake-doc-id",
    "S2T_HEADER": "KAUPPA",
    "S2T_CREDENTIALS": "/nonexistent/creds.json",
}


# -----------------------------------------------------------------------
# Input validation (subprocess)
# -----------------------------------------------------------------------
class TestInputValidation:
    """Exit code 1 for missing/empty text."""

    def test_no_args_returns_error(self):
        stdout, rc = _run()
        assert rc == 1
        assert "no text provided" in stdout.lower()

    def test_empty_string_returns_error(self):
        stdout, rc = _run("")
        assert rc == 1

    def test_whitespace_only_returns_error(self):
        stdout, rc = _run("   ")
        assert rc == 1


# -----------------------------------------------------------------------
# Configuration validation (subprocess)
# -----------------------------------------------------------------------
class TestConfigValidation:
    """Exit code 2 for missing or invalid configuration."""

    def test_missing_all_config(self):
        stdout, rc = _run("maitoa")
        assert rc == 2
        assert "missing configuration" in stdout.lower()
        assert "S2T_DOCUMENT_ID" in stdout
        assert "S2T_HEADER" in stdout
        assert "S2T_CREDENTIALS" in stdout

    def test_missing_document_id(self):
        env = {k: v for k, v in FULL_CONFIG.items()}
        del env["S2T_DOCUMENT_ID"]
        stdout, rc = _run("maitoa", env_override=env)
        assert rc == 2
        assert "S2T_DOCUMENT_ID" in stdout
        assert "S2T_HEADER" not in stdout

    def test_missing_header(self):
        env = {k: v for k, v in FULL_CONFIG.items()}
        del env["S2T_HEADER"]
        stdout, rc = _run("maitoa", env_override=env)
        assert rc == 2
        assert "S2T_HEADER" in stdout

    def test_missing_credentials(self):
        env = {k: v for k, v in FULL_CONFIG.items()}
        del env["S2T_CREDENTIALS"]
        stdout, rc = _run("maitoa", env_override=env)
        assert rc == 2
        assert "S2T_CREDENTIALS" in stdout

    def test_credentials_file_not_found(self):
        stdout, rc = _run("maitoa", env_override=FULL_CONFIG)
        assert rc == 2
        assert "credentials file not found" in stdout.lower()


# -----------------------------------------------------------------------
# Pure helper unit tests — extract_paragraphs
# -----------------------------------------------------------------------
class TestExtractParagraphs:
    """Unit tests for extract_paragraphs (no Google libs needed)."""

    def test_basic_extraction(self):
        doc = _make_document(["KAUPPA", "maitoa", "leipää"])
        paras = extract_paragraphs(doc)
        assert len(paras) == 3
        # Text includes the trailing newline from the API response.
        assert paras[0][0] == "KAUPPA\n"
        assert paras[1][0] == "maitoa\n"
        assert paras[2][0] == "leipää\n"

    def test_indices_are_sequential(self):
        doc = _make_document(["A", "BB", "CCC"])
        paras = extract_paragraphs(doc)
        # Each endIndex should be the next paragraph's startIndex.
        for i in range(len(paras) - 1):
            assert paras[i][2] == paras[i + 1][1]

    def test_empty_document(self):
        doc = {"body": {"content": []}}
        assert extract_paragraphs(doc) == []

    def test_non_paragraph_elements_skipped(self):
        doc = {
            "body": {
                "content": [
                    {"startIndex": 1, "endIndex": 2,
                     "sectionBreak": {}},
                    {"startIndex": 2, "endIndex": 8,
                     "paragraph": {
                         "elements": [
                             {"textRun": {"content": "hello\n"}},
                         ],
                     }},
                ],
            },
        }
        paras = extract_paragraphs(doc)
        assert len(paras) == 1
        assert paras[0][0] == "hello\n"

    def test_multi_run_paragraph(self):
        """Multiple textRuns in one paragraph are concatenated."""
        doc = {
            "body": {
                "content": [
                    {"startIndex": 1, "endIndex": 12,
                     "paragraph": {
                         "elements": [
                             {"textRun": {"content": "Hello "}},
                             {"textRun": {"content": "World\n"}},
                         ],
                     }},
                ],
            },
        }
        paras = extract_paragraphs(doc)
        assert paras[0][0] == "Hello World\n"


# -----------------------------------------------------------------------
# Pure helper unit tests — find_insertion_index
# -----------------------------------------------------------------------
class TestFindInsertionIndex:
    """Unit tests for find_insertion_index."""

    def test_header_with_entries(self):
        doc = _make_document(["KAUPPA", "maitoa", "leipää", "", "MUUTA"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        # Should be the endIndex of "leipää" paragraph.
        assert idx == paras[2][2]

    def test_header_no_entries(self):
        doc = _make_document(["KAUPPA", "", "MUUTA"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        # No entries — insert right after the header itself.
        assert idx == paras[0][2]

    def test_header_at_end_of_doc(self):
        doc = _make_document(["MUUTA", "stuff", "KAUPPA"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        assert idx == paras[2][2]

    def test_header_not_found(self):
        doc = _make_document(["MUUTA", "stuff"])
        paras = extract_paragraphs(doc)
        assert find_insertion_index(paras, "KAUPPA") is None

    def test_case_insensitive_match(self):
        doc = _make_document(["kauppa", "maitoa"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        assert idx is not None
        assert idx == paras[1][2]

    def test_header_with_surrounding_whitespace(self):
        doc = _make_document(["  KAUPPA  ", "maitoa"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        assert idx is not None

    def test_entries_stop_at_blank_line(self):
        """Blank line terminates the section."""
        doc = _make_document(["KAUPPA", "maitoa", "", "should not count"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        # Insert after "maitoa", NOT after "should not count".
        assert idx == paras[1][2]

    def test_multiple_headers_uses_first(self):
        doc = _make_document(["KAUPPA", "eka", "KAUPPA", "toka"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "KAUPPA")
        # First KAUPPA section: "eka" is the only entry.
        assert idx == paras[1][2]

    def test_unicode_header(self):
        doc = _make_document(["PÄIVÄKIRJA", "tekstiä"])
        paras = extract_paragraphs(doc)
        idx = find_insertion_index(paras, "PÄIVÄKIRJA")
        assert idx == paras[1][2]


# -----------------------------------------------------------------------
# MANIFEST
# -----------------------------------------------------------------------
class TestManifest:
    """MANIFEST is well-formed for the installer."""

    def test_manifest_exists(self):
        from gdocs_handler import MANIFEST  # noqa: F811
        assert "description" in MANIFEST
        assert "parameters" in MANIFEST

    def test_all_params_have_required_fields(self):
        from gdocs_handler import MANIFEST  # noqa: F811
        for name, param in MANIFEST["parameters"].items():
            assert "description" in param, f"{name} missing description"
            assert "required" in param, f"{name} missing required"
            assert "type" in param, f"{name} missing type"

    def test_no_path_type_params(self):
        """This handler writes to Google, not the local filesystem."""
        from gdocs_handler import MANIFEST  # noqa: F811
        for name, param in MANIFEST["parameters"].items():
            assert param["type"] != "path", (
                f"{name} should not be type 'path' — no local writes"
            )
