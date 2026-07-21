import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

# Keys that must never be leaked to handler subprocesses (§203, M1)
_SENSITIVE_ENV_KEYS = frozenset({"OPENAI_API_KEY"})


def _sanitize_text(text):
    """Strip null bytes from transcription text before passing to subprocess (§201, R2-m3)."""
    return text.replace("\x00", "")


def route_transcription(transcription, config, source_file=None):
    words = transcription.split(None, 1)
    first_word = words[0] if words else ""
    remaining = words[1] if len(words) > 1 else ""

    for keyword, word_config in config["magic_words"].items():
        if first_word.upper() == keyword.upper():
            success = _run_script(word_config["script_path"], remaining, source_file)
            return (keyword, success)

    if "default_action" in config:
        success = _run_script(config["default_action"]["script_path"], transcription, source_file)
        return ("default", success)

    # No magic word matched and no default_action configured.
    # Report failure so the file is NOT deleted — nothing handled it (§164).
    logger.warning(
        "No action matched transcription (first word: %r) and no default_action "
        "configured. File will be preserved.",
        first_word,
    )
    return (None, False)


def _run_script(script_path, text, source_file=None):
    """Run a handler script with hardened subprocess settings.

    - Uses sys.executable instead of "python" (§200, R2-M10)
    - Passes minimal environment, excluding sensitive keys (§203, M1)
    - Applies timeout=30 to prevent hanging (§203, M2)
    - Sanitizes text input (null bytes) before passing (§201, R2-m3)
    - Passes S2T_SOURCE_FILE env var so handlers can include it in output
    """
    logger.info("Running script %s", script_path)

    # Sanitize text — strip null bytes (§201, R2-m3)
    safe_text = _sanitize_text(text)

    # Build minimal environment — exclude sensitive keys (§203, M1)
    safe_env = {k: v for k, v in os.environ.items() if k not in _SENSITIVE_ENV_KEYS}

    # Pass source file path to handler for metadata
    if source_file:
        safe_env["S2T_SOURCE_FILE"] = source_file

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
