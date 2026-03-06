#!/usr/bin/env python3
"""Example action script: appends text to a log file."""
import os
import sys

text = sys.argv[1] if len(sys.argv) > 1 else ""
log_path = "/tmp/notes/log.txt"

os.makedirs(os.path.dirname(log_path), exist_ok=True)
with open(log_path, "a") as f:
    f.write(text + "\n")
print(f"Appended to: {log_path}")
