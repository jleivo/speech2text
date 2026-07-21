import logging
import hvac

logger = logging.getLogger(__name__)

_SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"


def vault_client(service=None):
    base = f"/etc/vault/services/{service}" if service else "/etc/vault/host"

    with open("/etc/vault/vault_addr") as f:
        url = f.read().strip()

    if not url.startswith("https://"):
        raise ValueError(
            f"Vault URL must use HTTPS, got '{url}'"
        )

    logger.debug("Connecting to Vault at %s (CA: %s)", url, _SYSTEM_CA_BUNDLE)

    client = hvac.Client(
        url=url,
        verify=_SYSTEM_CA_BUNDLE,
        timeout=10,
    )

    with open(f"{base}/role_id") as f:
        role_id = f.read().strip()
    with open(f"{base}/secret_id") as f:
        secret_id = f.read().strip()

    logger.debug("Authenticating with AppRole (creds from %s)", base)
    client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id,
    )
    logger.debug("Vault authentication successful")
    return client


def fetch_api_key(vault_secret_path, service=None, key="litellm_api"):
    client = vault_client(service=service)
    logger.debug("Reading secret at path=%s, key=%s", vault_secret_path, key)
    result = client.secrets.kv.v2.read_secret_version(path=vault_secret_path)
    available_keys = list(result["data"]["data"].keys())
    logger.debug("Secret keys available: %s", available_keys)
    if key not in result["data"]["data"]:
        raise KeyError(
            f"Key '{key}' not found in secret at '{vault_secret_path}'. "
            f"Available keys: {available_keys}"
        )
    return result["data"]["data"][key]
