import json
import os
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
        "api_base": {"type": "string"},
        "model": {"type": "string"},
        "default_action": {
            "type": "object",
            "properties": {"script_path": {"type": "string"}},
            "required": ["script_path"],
        },
        "vault_secret_path": {"type": "string"},
        "vault_secret_key": {"type": "string"},
        "vault_service": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]+$",
        },
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
    "additionalProperties": False,
}

DEFAULTS = {
    "watched_extensions": DEFAULT_EXTENSIONS,
    "delete_after_processing": False,
    "backend": "litellm",
    "model": "whisper-1",
    "writable_paths": [],
}

# Path fields that must be absolute and without .. components
_PATH_FIELDS = {
    "folder_to_watch",
    "transcription_log",
}


def _validate_path(value, field):
    if not os.path.isabs(value):
        raise ValueError(f"{field}: path must be absolute, got '{value}'")
    parts = value.split(os.sep)
    if ".." in parts:
        raise ValueError(f"{field}: path must not contain '..' components, got '{value}'")


def load_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)

    jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)

    for field in _PATH_FIELDS:
        if field in config and isinstance(config[field], str):
            _validate_path(config[field], field)

    for key, value in DEFAULTS.items():
        config.setdefault(key, value)

    return config
