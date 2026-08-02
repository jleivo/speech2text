"""Structured JSON logging for processed transcriptions."""
import json
from datetime import datetime, timezone


def log_transcription(log_path, audio_file, transcription, action, success, *, error=None):  # pylint: disable=too-many-arguments
    """Append one structured JSON record to the transcription log.

    ``error`` carries a human-readable failure reason when ``success`` is
    False (or records a recovered-via-fallback note); it is omitted from the
    record when None so successful entries stay compact. ``error`` is
    keyword-only to keep call sites explicit.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audio_file": audio_file,
        "transcription": transcription,
        "action": action,
        "success": success,
    }
    if error is not None:
        record["error"] = error
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
