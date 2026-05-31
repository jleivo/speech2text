# Vault Secret Integration Design

## Problem

The app's secret handling doesn't follow the guidance in `docs/SECRETS.md`. Currently the
`OPENAI_API_KEY` is expected as an environment variable, and the systemd unit uses an
`ExecStartPre` shell hack (`vault.sh`) to fetch it. SECRETS.md prescribes using the
`hvac` library with `vault_client()` AppRole authentication from within Python. Additionally,
the API key location (Vault secret path) should be configurable in `config.json`.

## Decision

Add a `src/vault.py` module implementing the SECRETS.md `vault_client()` pattern. The
config gains `vault_secret_path` and `vault_service` fields. At startup, if Vault is
configured, the app fetches the API key and injects it into `OPENAI_API_KEY` before any
transcription runs.

## Config Schema Changes

Two new optional fields in `config.json`:

| Field              | Type   | Description                                                        |
| ------------------ | ------ | ------------------------------------------------------------------ |
| `vault_secret_path` | string | Vault KV v2 path to the secret containing the API key (e.g. `secret/hosts/myhost/litellm-speech2text`) |
| `vault_service`    | string | Service name for AppRole auth. Uses `/etc/vault/services/<service>/` credentials. When omitted, uses host-level `/etc/vault/host/` credentials. |

Both are optional. If `vault_secret_path` is absent, the app uses `OPENAI_API_KEY` env var
as-is (current behavior unchanged). Backward compatible — existing configs without these
fields continue working.

Schema additions in `src/config.py`:

```python
"vault_secret_path": {"type": "string"},
"vault_service": {"type": "string"},
```

## Vault Module (`src/vault.py`)

New module implementing the `vault_client()` pattern from SECRETS.md plus a high-level
`fetch_api_key()` function.

### `vault_client(service=None)`

Direct implementation of the SECRETS.md pattern:

- If `service` is provided, reads credentials from `/etc/vault/services/<service>/`
- If `service` is None, reads credentials from `/etc/vault/host/`
- Reads Vault URL from `/etc/vault/vault_addr`
- Authenticates via AppRole (`role_id` + `secret_id`)
- Returns authenticated `hvac.Client`
- Client is created fresh each call, never cached (1h TTL per SECRETS.md)
- TLS verification left to system trust store (never `verify=False`)

### `fetch_api_key(vault_secret_path, service=None)`

- Calls `vault_client(service)` to get an authenticated client
- Reads the secret at the given path using KV v2 `read_secret_version`
- Returns `result["data"]["data"]["value"]`
- Never logs or prints the secret value

## Startup Integration (`src/main.py`)

After loading config, before starting the observer:

1. Check if `vault_secret_path` is in config
2. If present, call `fetch_api_key(vault_path, config.get("vault_service"))`
3. Set `os.environ["OPENAI_API_KEY"]` with the returned value
4. If `vault_secret_path` is absent, do nothing — `OPENAI_API_KEY` env var is used as-is

**Error handling:** Vault fetch failure when `vault_secret_path` is configured is a fatal
startup error. The app logs the error and exits. No silent fallback to env var when Vault
is explicitly configured (that would mask misconfiguration).

**Precedence:** When `vault_secret_path` is configured, the Vault-fetched key overrides any
existing `OPENAI_API_KEY` env var. Vault is the authoritative source when configured.

## Impact on Existing Modules

| Module               | Change                                                                 |
| --------------------- | ---------------------------------------------------------------------- |
| `src/transcribe.py`  | None — already uses litellm which reads `OPENAI_API_KEY` from env      |
| `src/config.py`      | Schema additions only (two new optional string properties)             |
| `src/folder_watcher.py` | None                                                               |
| `src/router.py`      | None                                                                   |
| `src/logger.py`      | None                                                                   |
| `deploy/speech2text.service` | Remove `ExecStartPre` vault.sh hack; app now handles Vault internally |
| `requirements.txt`   | Add `hvac>=2.0.0`                                                      |

## Testing

### Unit tests for `vault_client()`

- Mock `open()` to return fake `role_id`, `secret_id`, `vault_addr`
- Mock `hvac.Client`
- Verify AppRole login called with correct file paths for host-level (no service)
- Verify AppRole login called with correct file paths for service-level auth
- Verify `vault_addr` is read from `/etc/vault/vault_addr`

### Unit tests for `fetch_api_key()`

- Mock `vault_client()` return value
- Verify `read_secret_version` called with correct `vault_secret_path`
- Verify return value is `result["data"]["data"]["value"]`

### Unit tests for `main.py` integration

- Mock `fetch_api_key`
- Verify `OPENAI_API_KEY` env var is set when `vault_secret_path` is configured
- Verify `fetch_api_key` is not called when `vault_secret_path` is absent
- Verify fatal error on Vault failure when `vault_secret_path` is configured

### Integration tests

No changes needed — they already set `OPENAI_API_KEY` env var directly.

### Test dependencies

`hvac` is mocked in all unit tests. No real Vault server needed.