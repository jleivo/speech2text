#!/bin/bash
# v1.0.0
# update_readwrite_paths.sh — add paths to the speech2text systemd unit's
# ReadWritePaths directive, then reload and restart the service.
#
# Invoked by scripts/install_handler.py via passwordless sudo (see
# deploy/sudoers.d/speech2text-installer). Runs as root so it can edit
# /etc/systemd/system/speech2text.service.
#
# Usage:
#   update_readwrite_paths.sh [--unit-path PATH] PATH [PATH ...]
#
#   --unit-path PATH   Unit file to edit (default:
#                      /etc/systemd/system/speech2text.service)
#
# Idempotent: paths already present in ReadWritePaths are not duplicated.
# Input is validated to a safe character whitelist before touching the file.

set -euo pipefail

UNIT_PATH="/etc/systemd/system/speech2text.service"
# systemctl path is overridable for testing; defaults to the exact path
# granted in deploy/sudoers.d/speech2text-installer.
SYSTEMCTL="${SYSTEMCTL:-/usr/bin/systemctl}"
PATHS=()

# Fixed unit path enforced when running as root (see hardening below).
ALLOWED_UNIT="/etc/systemd/system/speech2text.service"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unit-path)
            UNIT_PATH="$2"
            shift 2
            ;;
        --unit-path=*)
            UNIT_PATH="${1#*=}"
            shift
            ;;
        -*)
            echo "ERROR: unknown option '$1'" >&2
            exit 1
            ;;
        *)
            PATHS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
    echo "ERROR: no paths supplied" >&2
    exit 1
fi

# --- Root hardening -------------------------------------------------------
# This script is granted passwordless sudo (see deploy/sudoers.d/). When it
# runs as root it may ONLY edit the speech2text unit and call the exact
# systemctl binary the sudoers fragment allows. Any --unit-path override or
# SYSTEMCTL env var is rejected/ignored so a caller cannot redirect the edit
# to an arbitrary file (e.g. /etc/sudoers.d/*) or swap the systemctl binary.
# The --unit-path / SYSTEMCTL overrides remain available for non-root test
# runs, where there is no privilege to escalate.
if [[ "$(id -u)" -eq 0 ]]; then
    if [[ "$UNIT_PATH" != "$ALLOWED_UNIT" ]]; then
        echo "ERROR: refusing to edit '$UNIT_PATH' as root." >&2
        echo "       Only '$ALLOWED_UNIT' is permitted under sudo." >&2
        exit 1
    fi
    SYSTEMCTL="/usr/bin/systemctl"
fi
# --------------------------------------------------------------------------

if [[ ! -f "$UNIT_PATH" ]]; then
    echo "ERROR: unit file not found: $UNIT_PATH" >&2
    exit 1
fi

# Validate each path against a strict whitelist (mirrors deploy/setup.sh).
# Rejects whitespace, newlines, and anything outside [a-zA-Z0-9/._-].
SAFE_RE='^[a-zA-Z0-9/._-]+$'
for p in "${PATHS[@]}"; do
    if [[ ! "$p" =~ $SAFE_RE ]]; then
        echo "ERROR: rejected unsafe path: $p" >&2
        exit 1
    fi
done

# Determine which paths are actually missing.
existing_rw="$(grep -E '^ReadWritePaths=' "$UNIT_PATH" | sed 's/^ReadWritePaths=//' | tr ' ' '\n' | sort -u || true)"

to_add=()
for p in "${PATHS[@]}"; do
    if ! echo "$existing_rw" | grep -qxF "$p"; then
        to_add+=("$p")
    fi
done

if [[ ${#to_add[@]} -eq 0 ]]; then
    echo "All paths already present in ReadWritePaths. Nothing to do."
else
    addition="${to_add[*]}"
    echo "Adding to ReadWritePaths: $addition"

    # Append the new paths to the ReadWritePaths line. If the directive
    # already exists, extend it; otherwise insert it into [Service].
    if grep -qE '^ReadWritePaths=' "$UNIT_PATH"; then
        # Extend the existing ReadWritePaths value in place.
        python3 - "$UNIT_PATH" "$addition" <<'PY'
import sys
unit_path, addition = sys.argv[1], sys.argv[2]
with open(unit_path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
out = []
for line in lines:
    if line.startswith("ReadWritePaths="):
        current = line.split("=", 1)[1].split()
        current.extend(addition.split())
        # de-dupe, preserve order
        seen = set()
        merged = [p for p in current if not (p in seen or seen.add(p))]
        out.append("ReadWritePaths=" + " ".join(merged))
    else:
        out.append(line)
with open(unit_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
PY
    else
        # No ReadWritePaths line — insert one after the [Service] header.
        python3 - "$UNIT_PATH" "$addition" <<'PY'
import sys
unit_path, addition = sys.argv[1], sys.argv[2]
with open(unit_path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
out = []
inserted = False
for line in lines:
    out.append(line)
    if not inserted and line.strip() == "[Service]":
        out.append("ReadWritePaths=" + addition)
        inserted = True
if not inserted:
    out.append("[Service]")
    out.append("ReadWritePaths=" + addition)
with open(unit_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
PY
    fi

    echo "Reloading systemd and restarting speech2text..."
    "$SYSTEMCTL" daemon-reload
    "$SYSTEMCTL" restart speech2text
    echo "Done. ReadWritePaths updated and service restarted."
fi
