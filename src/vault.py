import hvac

_SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"


def vault_client(service=None):
    base = f"/etc/vault/services/{service}" if service else "/etc/vault/host"

    with open("/etc/vault/vault_addr") as f:
        url = f.read().strip()

    if not url.startswith("https://"):
        raise ValueError(
            f"Vault URL must use HTTPS, got '{url}'"
        )

    client = hvac.Client(
        url=url,
        verify=_SYSTEM_CA_BUNDLE,
        timeout=10,
    )

    with open(f"{base}/role_id") as f:
        role_id = f.read().strip()
    with open(f"{base}/secret_id") as f:
        secret_id = f.read().strip()

    client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id,
    )
    return client


def fetch_api_key(vault_secret_path, service=None, key="litellm_api"):
    client = vault_client(service=service)
    result = client.secrets.kv.v2.read_secret_version(path=vault_secret_path)
    return result["data"]["data"][key]
