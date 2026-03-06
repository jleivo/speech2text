#!/usr/bin/env python3
"""Example action script: creates a timestamped note file."""
import os
import sys
from datetime import datetime

text = sys.argv[1] if len(sys.argv) > 1 else ""
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
path = f"/tmp/notes/{timestamp}.txt"

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    f.write(text)
print(f"Created note: {path}")
