#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="/srv/speech2text/config/config.json"
DEPLOY_DIR="/srv/speech2text"

# --- Utility functions ---

sanitize_paths() {
    # Read config, sanitize writable_paths, write back.
    # Only allows [a-zA-Z0-9/._-] characters; rejects newlines and injection.
    python3 -c "
import json, re, sys, os

with open(sys.argv[1]) as f:
    cfg = json.load(f)

raw = cfg.get('writable_paths', [])
sanitized = []
pat = re.compile(r'^[a-zA-Z0-9/._-]+$')
for p in raw:
    # Reject anything with newlines, tabs, spaces, or characters outside whitelist
    if not isinstance(p, str):
        continue
    if re.search(r'[\n\r\t ]', p):
        continue
    # Collapse multiple slashes, strip trailing slash
    p = re.sub(r'/+', '/', p).rstrip('/')
    if not pat.fullmatch(p):
        print(f'WARNING: rejected path \"{p}\" — contains disallowed characters', file=sys.stderr)
        continue
    sanitized.append(p)

cfg['writable_paths'] = sanitized
# Write back atomically
out = sys.argv[1] + '.tmp'
with open(out, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
os.replace(out, sys.argv[1])
" "$CONFIG_PATH"
}

generate_service() {
    echo "Generating systemd service from template..."
    if [ ! -f "$CONFIG_PATH" ]; then
        echo "ERROR: Config not found at $CONFIG_PATH" >&2
        exit 1
    fi

    python3 -c "
import json, sys, re

with open(sys.argv[1]) as f:
    cfg = json.load(f)

# Sanitize paths for systemd ReadWritePaths (only safe chars)
paths = ['/srv/speech2text'] + cfg.get('writable_paths', [])
pat = re.compile(r'^[a-zA-Z0-9/._-]+$')
safe_paths = [p for p in paths if pat.fullmatch(p)]
rw_paths = ' '.join(safe_paths)

with open(sys.argv[2]) as tmpl:
    content = tmpl.read().replace('{{READ_WRITE_PATHS}}', rw_paths)
with open(sys.argv[3], 'w') as out:
    out.write(content)
" "$CONFIG_PATH" "$SCRIPT_DIR/speech2text.service.tmpl" \
        /etc/systemd/system/speech2text.service
    sudo systemctl daemon-reload
}

# --- Update-only mode ---

if [ "${1:-}" = "--update-service" ]; then
    generate_service
    sudo systemctl restart speech2text.service
    echo ""
    echo "=== Service Updated ==="
    echo "ReadWritePaths regenerated from $CONFIG_PATH"
    echo "Service restarted."
    exit 0
fi

# --- Full setup (idempotent) ---

echo "=== Speech2Text Deployment Setup ==="

# 1. Create dedicated user
echo "Creating speech2text user..."
if ! id -u speech2text >/dev/null 2>&1; then
    useradd -r -s /bin/false speech2text
fi

# 2. Create directory structure
echo "Setting up directories..."
mkdir -p "$DEPLOY_DIR/audio_transfer"
mkdir -p "$DEPLOY_DIR/config"

# 3. Deploy application files
echo "Deploying application files..."
if [ "$REPO_ROOT" != "$DEPLOY_DIR" ]; then
    # Copy from repo to deploy dir (only if they're different locations)
    command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync is required but not installed" >&2; exit 1; }
    rsync -av --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
        --exclude 'tests' --exclude 'docs' "$REPO_ROOT/" "$DEPLOY_DIR/"
else
    echo "Repo is already at $DEPLOY_DIR — skipping rsync"
    # Clean excluded artifacts that may exist from git
    find "$DEPLOY_DIR" -maxdepth 1 -name '__pycache__' -type d -exec rm -rf {} +
fi
mv "$DEPLOY_DIR/src/main.py" "$DEPLOY_DIR/main.py"

# 3a. Config: copy example only if no local config exists (preserves local edits)
EXAMPLE_CONFIG="$DEPLOY_DIR/config/config.json.example"
if [ ! -f "$CONFIG_PATH" ] && [ -f "$EXAMPLE_CONFIG" ]; then
    echo "No config found — copying from example..."
    cp "$EXAMPLE_CONFIG" "$CONFIG_PATH"
fi

# 4. Set ownership and permissions
chown -R speech2text:speech2text "$DEPLOY_DIR"

# 4a. audio_transfer: open for syncthing (777)
chmod 777 "$DEPLOY_DIR/audio_transfer"

# 4b. Config file: restricted permissions (640)
if [ -f "$CONFIG_PATH" ]; then
    chmod 640 "$CONFIG_PATH"
    chown speech2text:speech2text "$CONFIG_PATH"
fi

# 5. Install virtual environment
echo "Setting up Python virtual environment..."
cd "$DEPLOY_DIR"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv --prompt speech2text
fi
"$DEPLOY_DIR/.venv/bin/pip" install -r requirements.txt --upgrade

# 6. Sanitize config paths before generating service
echo "Sanitizing config paths..."
sanitize_paths

# 7. Generate and install systemd service
generate_service

# 8. Enable and start service
echo "Enabling and starting service..."
sudo systemctl enable speech2text.service
systemctl start speech2text.service

# 9. Verify
echo ""
echo "=== Deployment Complete ==="
echo "Service status: $(systemctl is-active speech2text.service)"
echo "Watch directory: $DEPLOY_DIR/audio_transfer"
echo ""
echo "Management commands:"
echo "  systemctl status speech2text"
echo "  journalctl -u speech2text -f"
echo "  sudo systemctl restart speech2text"
