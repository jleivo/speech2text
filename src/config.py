import json
import jsonschema

DEFAULT_EXTENSIONS = [".wav", ".mp3", ".flac", ".m4a", ".ogg"]

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "folder_to_watch": {"type": "string"},
        "watched_extensions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "delete_after_processing": {"type": "boolean"},
        "transcription_log": {"type": "string"},
        "backend": {"type": "string"},
        "model": {"type": "string"},
        "default_action": {
            "type": "object",
            "properties": {"script_path": {"type": "string"}},
            "required": ["script_path"],
        },
        "vault_secret_path": {"type": "string"},
        "vault_service": {"type": "string"},
        "writable_paths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "magic_words": {
            "type": "object",
            "patternProperties": {
                "^[A-Z]+$": {
                    "type": "object",
                    "properties": {"script_path": {"type": "string"}},
                    "required": ["script_path"],
                }
            },
            "additionalProperties": False,
        },
    },
    "required": ["folder_to_watch", "magic_words"],
}

DEFAULTS = {
    "watched_extensions": DEFAULT_EXTENSIONS,
    "delete_after_processing": False,
    "backend": "litellm",
    "model": "whisper-1",
    "writable_paths": [],
}


def load_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)

    jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)

    for key, value in DEFAULTS.items():
        config.setdefault(key, value)

    return config
