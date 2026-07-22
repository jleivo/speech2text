# Handler Installer — Usage Guide

`scripts/install_handler.py` installs speech2text handlers into
`config/config.json` by reading each handler's self-describing `MANIFEST`.
It can run interactively or fully flag-driven (for scripting/CI), validates
the result against the config schema before writing, and optionally updates
the systemd unit's `ReadWritePaths` for handlers that write to disk.

## How handlers describe themselves

Every handler in `handlers/` declares a module-level `MANIFEST` dict:

```python
MANIFEST = {
    "description": "Appends timestamped entries under the # Journal header in daily notes",
    "parameters": {
        "destination": {
            "description": "Base directory for daily notes (YYYY/MM/YYYY-MM-DD.md underneath)",
            "required": True,
            "default": "/srv/Obsidian/Archives/dailynotes",
            "type": "path",
        }
    },
}
```

- `description` — shown in the handler list.
- `parameters` — each key becomes a config entry and is forwarded to the
  handler as `S2T_<KEY>` (the router already does this).
- `type` — `"path"` means the value is a filesystem path the service must be
  able to write, so the installer knows to add it to the systemd
  `ReadWritePaths`. Other types (`"string"`, `"email"`, …) need no systemd
  change.
- `required` / `default` — drive the prompts and validation.

## Interactive mode

```bash
python scripts/install_handler.py
```

The wizard:

1. Lists handlers from `handlers/` and the words already configured, and
   suggests handlers not yet installed.
2. Asks you to pick a handler, enter the magic word (and optional
   comma-separated aliases), then prompts for each declared parameter
   (showing its description and default — press Enter to accept the default).
   Path parameters must be absolute.
3. Shows the resulting `magic_words` entry and asks for confirmation.
4. Validates the whole config against the schema (`src.config.load_config`)
   and writes `config/config.json` atomically, preserving existing content.
5. Checks the systemd unit's `ReadWritePaths`; if a path-type parameter is
   missing, offers to add it and reload/restart the service (via the
   passwordless sudo helper — see `docs/installer-setup.md`).

Re-running on an already-installed word shows the current entry and offers to
**edit** it rather than duplicate it.

## Non-interactive mode

```bash
python scripts/install_handler.py \
    --handler journal_handler \
    --word PAIVAKIRJA \
    --aliases JOURNAL,PAIVA \
    --param destination=/srv/Obsidian/Archives/dailynotes \
    --yes
```

| Flag | Meaning |
|------|---------|
| `--handler NAME` | Handler to install (filename without `.py`) |
| `--word WORD` | Magic word (uppercased automatically) |
| `--aliases A,B` | Comma-separated aliases |
| `--param KEY=VALUE` | Parameter value; repeatable |
| `--yes` | Skip confirmation prompts (overwrite existing word) |
| `--no-systemd` | Skip the systemd `ReadWritePaths` update |
| `--config PATH` | Config file (default `config/config.json`) |
| `--handlers-dir PATH` | Handler directory (default `handlers/`) |
| `--unit-path PATH` | Systemd unit (default `/etc/systemd/system/speech2text.service`) |
| `--helper-script PATH` | ReadWritePaths helper (default `deploy/update_readwrite_paths.sh`) |
| `--list` | List handlers + installed words and exit |

`--handler` and `--word` must be given together to trigger non-interactive
mode; omitting both runs the interactive wizard.

## Listing handlers

```bash
python scripts/install_handler.py --list
```

Prints each handler, its parameters (type, required, default), and whether it
is already installed, plus the set of configured words.

## The systemd update step

When a handler has a `path`-type parameter whose value is not already in the
unit's `ReadWritePaths`, the installer (unless `--no-systemd`) offers to run:

```bash
sudo deploy/update_readwrite_paths.sh --unit-path <unit> <path> [<path> ...]
```

The helper validates each path against a safe-character whitelist, appends
the missing paths to the `ReadWritePaths=` line (creating it if absent), then
runs `systemctl daemon-reload` and `systemctl restart speech2text`. It is
idempotent — paths already present are not duplicated.

This requires the passwordless sudo fragment from `docs/installer-setup.md`.
Without it, the installer prints the missing paths and tells you to add them
manually; the config write still succeeds.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (or user chose to skip an existing word) |
| 1 | Error (bad input, validation failure, helper failure) |
| 130 | Interrupted (Ctrl-C) |
