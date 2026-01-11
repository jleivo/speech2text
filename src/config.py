#!/usr/bin/env python3

import os
import json
import jsonschema
from pathlib import Path

# JSON schema for the configuration file
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "folder_to_watch": {"type": "string"},
        "magic_words": {
            "type": "object",
            "patternProperties": {
                "^[A-Z]+$": {  # Magic words should be uppercase
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "file_path_template": {"type": "string"},
                        "file_path": {"type": "string"},
                        "recipient": {"type": "string"},
                        "subject": {"type": "string"},
                        "script_path": {"type": "string"}
                    },
                    "required": ["action"]
                }
            },
            "additionalProperties": False
        }
    },
    "required": ["folder_to_watch", "magic_words"]
}

def load_config(config_path):
    """Load and validate the configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Validate against schema
    jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)

    return config

def create_default_config(output_dir='../config'):
    """Create a default configuration file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    default_config = {
        "folder_to_watch": str(output_dir / "audio"),
        "magic_words": {
            "FILE": {
                "action": "create_file",
                "file_path_template": str(output_dir / "{timestamp}.txt")
            },
            "APPEND": {
                "action": "append_to_file",
                "file_path": str(output_dir / "log.txt")
            }
        }
    }

    config_path = output_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=4)

    print(f"Default configuration created at: {config_path}")
    return config_path

