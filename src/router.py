"""Route transcriptions to handler scripts based on magic words.

The router inspects the first word of a transcription, matches it against
configured magic words (and their aliases), and dispatches the remaining
text to the corresponding handler as a subprocess. Handler parameters are
forwarded from config as S2T_<KEY> environment variables.
"""
import logging
import os
import subprocess
import sys
import unicodedata

logger = logging.getLogger(__name__)

# Keys that must never be leaked to handler subprocesses (§203, M1)
_SENSITIVE_ENV_KEYS = frozenset({"OPENAI_API_KEY"})

# Reserved config keys that are NOT forwarded to handlers as S2T_* env vars.
# script_path selects the handler; aliases are router-level trigger words.
_RESERVED_CONFIG_KEYS = frozenset({"script_path", "aliases"})


def _sanitize_text(text):
    """Strip null bytes from transcription text before passing to subprocess (§201, R2-m3)."""
    return text.replace("\x00", "")


def _normalize_trigger(word):
    """Strip surrounding punctuation/symbols from a trigger word for matching.

    Whisper attaches sentence punctuation to the first word — e.g. a spoken
    "Journal" is transcribed as "Journal." — which would break an exact match
    against the configured magic word. This strips leading/trailing Unicode
    punctuation (P*) and symbols (S*) so "Journal.", "PÄIVÄKIRJA," and
    "(WORK)" all match their bare keywords. Interior characters are preserved,
    and the returned value is uppercased for case-insensitive comparison.
    """
    stripped = word.strip()
    while stripped and unicodedata.category(stripped[0])[0] in ("P", "S"):
        stripped = stripped[1:]
    while stripped and unicodedata.category(stripped[-1])[0] in ("P", "S"):
        stripped = stripped[:-1]
    return stripped.upper()


def _matches(word_config, first_word):
    """Return True if first_word matches the primary keyword or any alias.

    Matching is case-insensitive and ignores surrounding punctuation (see
    _normalize_trigger). Aliases are read from the optional "aliases" list
    in the magic-word config.
    """
    target = _normalize_trigger(first_word)
    if target == word_config.get("_keyword", "").upper():
        return True
    return any(target == alias.upper() for alias in word_config.get("aliases", []))


def route_transcription(transcription, config, source_file=None):
    """Route a transcription to the matching handler script.

    Splits off the first word and matches it (case-insensitively, ignoring
    surrounding punctuation) against each magic word and its aliases. On a
    match, runs that handler with the remaining text. Otherwise falls back
    to default_action (with the full text), or returns (None, False) if no
    default is configured so the audio file is preserved.
    """
    words = transcription.split(None, 1)
    first_word = words[0] if words else ""
    remaining = words[1] if len(words) > 1 else ""

    for keyword, word_config in config["magic_words"].items():
        # Tag the primary keyword so _matches can compare against it without
        # mutating the caller's config dict.
        match_config = dict(word_config, _keyword=keyword)
        if _matches(match_config, first_word):
            success = _run_script(word_config, remaining, source_file)
            return (keyword, success)

    if "default_action" in config:
        success = _run_script(config["default_action"], transcription, source_file)
        return ("default", success)

    # No magic word matched and no default_action configured.
    # Report failure so the file is NOT deleted — nothing handled it (§164).
    logger.warning(
        "No action matched transcription (first word: %r) and no default_action "
        "configured. File will be preserved.",
        first_word,
    )
    return (None, False)


def _handler_env(word_config, source_file=None):
    """Build the subprocess environment for a handler.

    - Starts from the current environment, excluding sensitive keys (§203, M1)
    - Forwards every non-reserved config key as S2T_<KEY> (uppercased) so a
      handler's parameters live entirely in config.json — the handler declares
      which keys it reads, the router passes whatever is defined.
    - Passes S2T_SOURCE_FILE so handlers can record the originating audio file.
    """
    safe_env = {k: v for k, v in os.environ.items() if k not in _SENSITIVE_ENV_KEYS}

    for key, value in word_config.items():
        if key in _RESERVED_CONFIG_KEYS:
            continue
        safe_env["S2T_" + key.upper()] = str(value)

    if source_file:
        safe_env["S2T_SOURCE_FILE"] = source_file

    return safe_env


def _run_script(word_config, text, source_file=None):
    """Run a handler script with hardened subprocess settings.

    - Uses sys.executable instead of "python" (§200, R2-M10)
    - Passes minimal environment, excluding sensitive keys (§203, M1)
    - Forwards handler parameters from config as S2T_<KEY> env vars
    - Applies timeout=30 to prevent hanging (§203, M2)
    - Sanitizes text input (null bytes) before passing (§201, R2-m3)

    word_config is the magic-word (or default_action) config dict; it must
    contain "script_path" and may contain any handler-specific parameters.
    """
    script_path = word_config["script_path"]
    logger.info("Running script %s", script_path)

    # Sanitize text — strip null bytes (§201, R2-m3)
    safe_text = _sanitize_text(text)

    safe_env = _handler_env(word_config, source_file)

    result = subprocess.run(
        [sys.executable, script_path, safe_text],
        env=safe_env,
        check=False,
        timeout=30,  # Prevent hanging subprocesses (§203, M2)
    )
    if result.returncode != 0:
        logger.error("Script %s failed with return code %d", script_path, result.returncode)
        return False
    return True
