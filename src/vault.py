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