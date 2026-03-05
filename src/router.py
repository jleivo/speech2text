import logging
import subprocess

logger = logging.getLogger(__name__)


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
    logger.info("Running script %s", script_path)
    result = subprocess.run(["python", script_path, text], check=False)
    if result.returncode != 0:
        logger.error("Script %s failed with return code %d", script_path, result.returncode)
        return False
    return True
