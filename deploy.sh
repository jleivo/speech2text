#!/bin/bash
#
# Deploy speech2text to remote server via rsync.
# Default: dry-run (--dry-run + --info=NAME). Pass --apply to execute.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TGT="juha@tuvlnxsrvp04.intra.leivo:/srv/speech2text/"

RSYNC_OPTS=(-avz --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    --exclude 'tests' --exclude 'docs' \
    --exclude '*.pyc' --exclude '.hermes')

DRY_RUN_OPTS=(--dry-run --info=NAME)

case "${1:-}" in
    --apply|--commit)
        exec rsync "${RSYNC_OPTS[@]}" "$REPO_ROOT/" "juha@tuvlnxsrvp04.intra.leivo:$TGT"
        ;;
    --help|-h)
        echo "Usage: $0 [--apply|--commit]"
        echo "Default is dry-run. Use --apply to deploy."
        exit 0
        ;;
    *)
        exec rsync "${RSYNC_OPTS[@]}" "${DRY_RUN_OPTS[@]}" "$REPO_ROOT/" "juha@tuvlnxsrvp04.intra.leivo:$TGT"
        ;;
esac
