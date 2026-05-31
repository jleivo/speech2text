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

# 5. Install systemd service
echo "Installing systemd service..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo cp "$SCRIPT_DIR/deploy/speech2text.service" /etc/systemd/system/
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
