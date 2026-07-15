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


def route_transcription(transcription, config):
    words = transcription.split(None, 1)
    first_word = words[0] if words else ""
    remaining = words[1] if len(words) > 1 else ""

    for keyword, word_config in config["magic_words"].items():
        if first_word.upper() == keyword.upper():
            success = _run_script(word_config["script_path"], remaining)
            return (keyword, success)

    if "default_action" in config:
        success = _run_script(config["default_action"]["script_path"], transcription)
        return ("default", success)

    return (None, True)


def _run_script(script_path, text):
    """Run a handler script with hardened subprocess settings.

    - Uses sys.executable instead of "python" (§200, R2-M10)
    - Passes minimal environment, excluding sensitive keys (§203, M1)
    - Applies timeout=30 to prevent hanging (§203, M2)
    - Sanitizes text input (null bytes) before passing (§201, R2-m3)
    """
    logger.info("Running script %s", script_path)

    # Sanitize text — strip null bytes (§201, R2-m3)
    safe_text = _sanitize_text(text)

    # Build minimal environment — exclude sensitive keys (§203, M1)
    safe_env = {k: v for k, v in os.environ.items() if k not in _SENSITIVE_ENV_KEYS}

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
