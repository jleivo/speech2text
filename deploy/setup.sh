#!/bin/bash
set -e

echo "=== Speech2Text Deployment Setup ==="

# 1. Create dedicated user
echo "Creating speech2text user..."
if ! id -u speech2text >/dev/null 2>&1; then
    useradd -r -s /bin/false speech2text
fi

# 2. Create directory structure
echo "Setting up directories..."
mkdir -p /srv/speech2text/audio_transfer

# 3. Copy application files (run from repo root)
echo "Deploying application files..."
rsync -av --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    --exclude 'tests' --exclude 'docs' /srv/speech2text/ /srv/speech2text/
mv /srv/speech2text/src/main.py /srv/speech2text/main.py
chown -R speech2text:speech2text /srv/speech2text
chmod 777 /srv/speech2text/audio_transfer

# 4. Install virtual environment
echo "Setting up Python virtual environment..."
cd /srv/speech2text
if [ ! -d ".venv" ]; then
    python3 -m venv .venv --prompt speech2text
fi
/srv/speech2text/.venv/bin/pip install -r requirements.txt --upgrade

# 5. Generate and install systemd service
echo "Generating systemd service from template..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="/srv/speech2text/config/config.json"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Config not found at $CONFIG_PATH" >&2
    exit 1
fi

# Read config, build ReadWritePaths, and substitute template in one Python call
python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    cfg = json.load(f)
paths = ['/srv/speech2text'] + cfg.get('writable_paths', [])
rw_paths = ':'.join(paths)
with open(sys.argv[2]) as tmpl:
    content = tmpl.read().replace('{{READ_WRITE_PATHS}}', rw_paths)
with open(sys.argv[3], 'w') as out:
    out.write(content)
" "$CONFIG_PATH" "$SCRIPT_DIR/speech2text.service.tmpl" /etc/systemd/system/speech2text.service
sudo systemctl daemon-reload

# 6. Enable and start service
echo "Enabling and starting service..."
sudo systemctl enable speech2text.service
systemctl start speech2text.service

# 7. Verify
echo ""
echo "=== Deployment Complete ==="
echo "Service status: $(systemctl is-active speech2text.service)"
echo "Watch directory: /srv/speech2text/audio_transfer"
echo ""
echo "Management commands:"
echo "  systemctl status speech2text"
echo "  journalctl -u speech2text -f"
echo "  sudo systemctl restart speech2text"
