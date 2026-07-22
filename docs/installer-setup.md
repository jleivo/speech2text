# Installer Setup — Passwordless sudo for the handler installer

The handler installer (`scripts/install_handler.py`) can update the systemd
unit's `ReadWritePaths` and reload/restart the `speech2text` service after
writing a new handler into `config.json`. Those operations require root, so
the installer shells out to `sudo`. To avoid an interactive password prompt
(and to keep the tool scriptable), a narrowly-scoped sudoers fragment grants
passwordless sudo for **only** the exact commands the installer needs.

## What the fragment grants

`deploy/sudoers.d/speech2text-installer` grants the install user `NOPASSWD`
for exactly four commands:

| Command | Purpose |
|---------|---------|
| `/usr/bin/systemctl daemon-reload` | Reload systemd after the unit file changes |
| `/usr/bin/systemctl restart speech2text` | Restart the service to pick up new `ReadWritePaths` |
| `/usr/bin/systemctl status speech2text` | Let the installer report service state |
| `/srv/speech2text/deploy/update_readwrite_paths.sh` | Add paths to `ReadWritePaths` + reload + restart in one step |

The helper script (`deploy/update_readwrite_paths.sh`) is the one that edits
`/etc/systemd/system/speech2text.service`. It runs as root (via the sudoers
entry) so it can write the unit file, then calls `systemctl daemon-reload`
and `systemctl restart speech2text` itself.

## Security rationale (principle of least privilege)

- **Exact binary + exact arguments.** Every entry names a full path and the
  precise arguments allowed. There are no glob wildcards, so the user cannot
  run arbitrary `systemctl` subcommands or append extra flags.
- **No shell escapes.** `sudo su`, `sudo bash`, `sudo -i`, and
  `sudo systemctl <anything-else>` are **not** granted. The only writable
  surface is the fixed, repo-controlled helper script.
- **The helper validates its input.** `update_readwrite_paths.sh` rejects any
  path that does not match the whitelist `^[a-zA-Z0-9/._-]+$` (same rule as
  `deploy/setup.sh`), so a malicious path cannot inject shell metacharacters
  into the unit file.
- **Root-mode hardening.** When the helper detects it is running as root
  (i.e. via sudo), it refuses to edit any file other than
  `/etc/systemd/system/speech2text.service` and pins `systemctl` to
  `/usr/bin/systemctl`. The `--unit-path` and `SYSTEMCTL` overrides are
  only honoured for non-root test runs, where there is no privilege to
  escalate.
- **Idempotent.** Re-running with paths already present in `ReadWritePaths`
  makes no change.

## How to install

1. **Edit the user.** Replace `jaxon` in the fragment with the account that
   will run the installer (the user who deploys handlers). If you prefer to
   grant it to a group instead, change the line prefix to `%groupname`.

2. **Validate the syntax** (must be run as root / with a password):

   ```bash
   sudo visudo -cf deploy/sudoers.d/speech2text-installer
   ```

   Expected output: `deploy/sudoers.d/speech2text-installer: parsed OK`

3. **Install the fragment:**

   ```bash
   sudo cp deploy/sudoers.d/speech2text-installer /etc/sudoers.d/speech2text-installer
   sudo chmod 0440 /etc/sudoers.d/speech2text-installer
   sudo chown root:root /etc/sudoers.d/speech2text-installer
   ```

   Files in `/etc/sudoers.d/` are included automatically by the main
   `/etc/sudoers` (`#includedir /etc/sudoers.d`).

4. **Verify** (as the install user, no password should be prompted):

   ```bash
   sudo -n /usr/bin/systemctl status speech2text
   ```

## Adjusting the helper path

The sudoers entry hard-codes `/srv/speech2text/deploy/update_readwrite_paths.sh`
(the production deploy location). If you run the installer from a checkout
elsewhere, either:

- copy the helper to `/srv/speech2text/deploy/`, or
- update the path in **both** the sudoers fragment and the installer's
  `--helper-script` flag so they agree.

## Removing

```bash
sudo rm /etc/sudoers.d/speech2text-installer
```

The installer degrades gracefully without it: the systemd update step fails
with a clear message and tells you to add the paths to the unit file
manually. The config write itself never needs sudo.
