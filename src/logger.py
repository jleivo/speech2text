import json
from datetime import datetime, timezone


def log_transcription(log_path, audio_file, transcription, action, success):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audio_file": audio_file,
        "transcription": transcription,
        "action": action,
        "success": success,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
