import hvac


def vault_client(service=None):
    base = f"/etc/vault/services/{service}" if service else "/etc/vault/host"
    client = hvac.Client(
        url=open("/etc/vault/vault_addr").read().strip(),
    )
    client.auth.approle.login(
        role_id=open(f"{base}/role_id").read().strip(),
        secret_id=open(f"{base}/secret_id").read().strip(),
    )
    return client


def fetch_api_key(vault_secret_path, service=None):
    client = vault_client(service=service)
    result = client.secrets.kv.v2.read_secret_version(path=vault_secret_path)
    return result["data"]["data"]["value"]