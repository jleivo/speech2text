# Configurable Systemd Hardening

## Problem

The systemd service uses `ProtectSystem=strict` with a hardcoded `ReadWritePaths=/srv/speech2text`. Handler scripts that need to write to other directories (e.g., `/srv/Obsidian/Inbox`) fail with `OSError: [Errno 30] Read-only file system`.

## Design

### 1. Config field: `writable_paths`

Add a top-level optional array field `writable_paths` to `config.json` and its jsonschema:

```json
"writable_paths": {
    "type": "array",
    "items": {"type": "string"}
}
```

Default: `[]` (no extra writable paths beyond `/srv/speech2text`). Example:

```json
{
    "writable_paths": ["/srv/Obsidian/Inbox", "/var/log/speech2text"]
}
```

The `config.py` DEFAULTS dict gets `"writable_paths": []`.

### 2. Service template

Rename `deploy/speech2text.service` to `deploy/speech2text.service.tmpl`. Replace the hardcoded `ReadWritePaths=/srv/speech2text` line with:

```ini
ReadWritePaths={{READ_WRITE_PATHS}}
```

### 3. Setup script

`deploy/setup.sh` reads `writable_paths` from `config/config.json`, prepends `/srv/speech2text` (always required), joins all paths with `:`, and substitutes `{{READ_WRITE_PATHS}}` in the template to produce `/etc/systemd/system/speech2text.service`.

Generation logic:

```bash
# Read writable_paths from config
WRITABLE_PATHS=$(python3 -c "
import json
with open('/srv/speech2text/config/config.json') as f:
    cfg = json.load(f)
paths = ['/srv/speech2text'] + cfg.get('writable_paths', [])
print(':'.join(paths))
")

# Generate service file from template
sed "s|{{READ_WRITE_PATHS}}|${WRITABLE_PATHS}|g" \
    deploy/speech2text.service.tmpl > /etc/systemd/system/speech2text.service
```

### 4. Auto-detection from handler scripts

The setup script will not auto-detect writable paths from handler scripts — this is too fragile and handler directories don't necessarily correspond to write targets. Users declare what they need in `writable_paths` explicitly.

### 5. Documentation

Update `docs/systemd-setup.md` to:
- Document the `writable_paths` config field
- Explain the template-based service generation
- Show how to add new writable paths

## Files Changed

- `src/config.py` — add `writable_paths` to schema and defaults
- `config/config.json` — add `writable_paths` example
- `deploy/speech2text.service` → `deploy/speech2text.service.tmpl` — template with placeholder
- `deploy/setup.sh` — read config, generate service file from template
- `docs/systemd-setup.md` — document `writable_paths` and template generation