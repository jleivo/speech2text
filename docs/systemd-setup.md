# Systemd Deployment Guide

This guide covers deploying speech2text as a systemd service for production use.

## Prerequisites

- Root or sudo access
- Python 3.10+ installed
- Vault CLI available at `/usr/local/bin/vault.sh`
- LiteLLM server accessible at `http://litellm.intra.leivo`

## Quick Deploy

Run the deployment script from the repository root:

```bash
sudo deploy/setup.sh
```

This script:
1. Creates the `speech2text` system user
2. Sets up `/srv/speech2text` directory structure
3. Installs dependencies in a virtual environment
4. Registers and starts the systemd service

## Manual Installation

If you prefer to install manually:

### 1. Create User and Directories

```bash
sudo useradd -r -s /bin/false -m /srv/speech2text speech2text
sudo adduser speech2text vault-readers
sudo mkdir -p /srv/speech2text/audio_transfer
sudo chmod 777 /srv/speech2text/audio_transfer
sudo chown -R speech2text:speech2text /srv/speech2text
```

### 2. Deploy Application

```bash
cd /srv/speech2text
# Copy your application files here
# Or use rsync: rsync -av /path/to/repo/ /srv/speech2text/
mv /srv/speech2text/src/main.py /srv/speech2text/main.py
```

### 3. Install Dependencies

```bash
python3 -m venv .venv --prompt speech2text
.venv/bin/pip install -r requirements.txt
```

### 4. Install Service

```bash
sudo cp deploy/speech2text.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable speech2text.service
sudo systemctl start speech2text.service
```

## Service Configuration

### Environment Variables

The service is configured in `/etc/systemd/system/speech2text.service`:

- `OPENAI_API_BASE` - LiteLLM server URL
- `OPENAI_API_KEY` - Retrieved dynamically from vault at startup
- `PATH` - Includes virtual environment binaries

### Vault Integration

Secrets are retrieved inline at service startup via `ExecStartPre`. No secrets are stored on disk.

```bash
ExecStartPre=/bin/bash -c '/usr/local/bin/vault.sh get secret/hosts/tuvlnxsrvp04/litellm-speech2text | xargs -I {} systemctl set-environment OPENAI_API_KEY={}'
```

If your vault command differs, update this line in the service file.

### Writable Paths

Handler scripts may need write access to directories outside `/srv/speech2text`. Configure `writable_paths` in `config/config.json`:

```json
{
    "writable_paths": ["/srv/Obsidian/Inbox", "/var/log/speech2text"],
    ...
}
```

During deployment, `setup.sh` reads `writable_paths` from config and generates the systemd `ReadWritePaths` directive automatically. `/srv/speech2text` is always included.

To add a new writable path:
1. Add the path to `writable_paths` in `config/config.json`
2. Re-run `sudo deploy/setup.sh` (or manually regenerate the service file)
3. Restart: `sudo systemctl restart speech2text`

### Watch Directory

Configure the audio folder in `config/config.json`:

```json
{
  "folder_to_watch": "/srv/speech2text/audio_transfer",
  ...
}
```

Place audio files in this directory for automatic processing.

## Service Management

### Check Status

```bash
systemctl status speech2text
```

### View Logs

```bash
# Real-time logs
journalctl -u speech2text -f

# Last 100 lines
journalctl -u speech2text -n 100

# Since boot
journalctl -u speech2text -b
```

### Restart Service

```bash
systemctl restart speech2text
```

### Stop/Start

```bash
systemctl stop speech2text
systemctl start speech2text
```

### Disable (prevent auto-start on boot)

```bash
systemctl disable speech2text
```

## Troubleshooting

### Service Won't Start

Check the logs:

```bash
journalctl -u speech2text -n 50 --no-pager
```

Common issues:
- Vault command fails - verify `/usr/local/bin/vault.sh` is accessible
- Missing dependencies - check virtual environment setup
- Permission issues - ensure `/srv/speech2text` is owned by `speech2text`

### Vault Authentication Failures

If vault.sh requires authentication:

1. Check if the `speech2text` user has vault access
2. You may need to configure vault agent or use a token file
3. Update `ExecStartPre` to handle your auth method

Example with token file:
```bash
ExecStartPre=/bin/bash -c 'VAULT_TOKEN=$(cat /etc/speech2text/vault-token) /usr/local/bin/vault.sh get secret/hosts/tuvlnxsrvp04/litellm-speech2text | xargs -I {} systemctl set-environment OPENAI_API_KEY={}'
```

### Audio Files Not Being Processed

1. Check file permissions - files must be readable by `speech2text` user
2. Verify watched directory in config matches actual drop location
3. Check logs for transcription errors

### High Memory Usage

The service has `MemoryMax=2G` limit. Adjust in service file if needed:

```bash
# Edit service
sudo systemctl edit speech2text

# Add override
[Service]
MemoryMax=4G
```

Then reload: `sudo systemctl daemon-reload`

## Security Notes

- Service runs as unprivileged `speech2text` user
- No secrets written to disk
- `NoNewPrivileges=true` prevents privilege escalation
- `ProtectSystem=strict` makes filesystem read-only except specified paths (auto-generated from `writable_paths` in config)
- `ProtectHome=true` prevents access to user home directories

## Updates

To update the application:

```bash
# Stop service
sudo systemctl stop speech2text

# Deploy new files
sudo rsync -av /path/to/new/repo/ /srv/speech2text/

# Update dependencies
sudo -u speech2text /srv/speech2text/.venv/bin/pip install -r /srv/speech2text/requirements.txt

# Restart
sudo systemctl start speech2text
```

## Uninstall

```bash
# Stop and disable service
sudo systemctl stop speech2text
sudo systemctl disable speech2text

# Remove service file
sudo rm /etc/systemd/system/speech2text.service
sudo systemctl daemon-reload

# Remove application (optional)
sudo rm -rf /srv/speech2text

# Remove user (optional)
sudo userdel speech2text
```
