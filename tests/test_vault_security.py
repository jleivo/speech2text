"""Test vault security measures.

Covers:
  - HTTPS enforcement: non-HTTPS URLs are rejected
  - verify=True: TLS verification is enforced
  - timeout=10: client has a timeout
  - fetch_api_key calls vault_client with correct service
"""
from unittest.mock import patch, mock_open, MagicMock
import pytest

from src.vault import vault_client, fetch_api_key


def _mock_file_contents(contents):
    """Create a mock_open side_effect that returns different content per path."""
    mock_f = mock_open(read_data="")
    def side_effect(path, *args, **kwargs):
        mock_f.return_value.read = lambda: contents.get(path, "")
        return mock_f.return_value
    mock_f.side_effect = side_effect
    return mock_f


def test_vault_url_must_be_https():
    """Non-HTTPS vault URLs are rejected with ValueError."""
    file_contents = {
        "/etc/vault/vault_addr": "http://insecure.example.com:8200\n",
    }

    with patch("builtins.open", _mock_file_contents(file_contents)):
        with pytest.raises(ValueError, match="Vault URL must use HTTPS"):
            vault_client()


def test_vault_client_uses_verify_true():
    """Vault client is created with verify=True (TLS verification)."""
    file_contents = {
        "/etc/vault/vault_addr": "https://vault.example.com:8200\n",
        "/etc/vault/host/role_id": "role-123\n",
        "/etc/vault/host/secret_id": "secret-456\n",
    }

    with patch("src.vault.hvac.Client") as mock_client_class:
        with patch("builtins.open", _mock_file_contents(file_contents)):
            vault_client()

    mock_client_class.assert_called_once()
    call_kwargs = mock_client_class.call_args[1]
    assert call_kwargs["verify"] is True


def test_vault_client_has_timeout():
    """Vault client is created with timeout=10."""
    file_contents = {
        "/etc/vault/vault_addr": "https://vault.example.com:8200\n",
        "/etc/vault/host/role_id": "role-123\n",
        "/etc/vault/host/secret_id": "secret-456\n",
    }

    with patch("src.vault.hvac.Client") as mock_client_class:
        with patch("builtins.open", _mock_file_contents(file_contents)):
            vault_client()

    call_kwargs = mock_client_class.call_args[1]
    assert call_kwargs["timeout"] == 10


def test_fetch_api_key_calls_vault_client_with_service():
    """fetch_api_key passes service parameter to vault_client."""
    with patch("src.vault.vault_client") as mock_vc:
        mock_client = MagicMock()
        mock_vc.return_value = mock_client
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"litellm_api": "sk-test"}}
        }

        fetch_api_key("secret/hosts/myhost/litellm", service="speech2text")

        mock_vc.assert_called_once_with(service="speech2text")
