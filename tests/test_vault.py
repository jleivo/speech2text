from unittest.mock import patch, mock_open, MagicMock
from src.vault import vault_client


@patch("src.vault.hvac.Client")
def test_vault_client_host_level(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    file_contents = {
        "/etc/vault/vault_addr": "https://vault.example.com:8200\n",
        "/etc/vault/host/role_id": "host-role-123\n",
        "/etc/vault/host/secret_id": "host-secret-456\n",
    }

    with patch("builtins.open", mock_open(read_data="")) as mock_file:
        def open_side_effect(path, *args, **kwargs):
            mock_file.return_value.read = lambda: file_contents[path]
            return mock_file.return_value

        mock_file.side_effect = open_side_effect

        result = vault_client()

    mock_client_class.assert_called_once_with(url="https://vault.example.com:8200")
    mock_client.auth.approle.login.assert_called_once_with(
        role_id="host-role-123",
        secret_id="host-secret-456",
    )
    assert result == mock_client


@patch("src.vault.hvac.Client")
def test_vault_client_service_level(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    file_contents = {
        "/etc/vault/vault_addr": "https://vault.example.com:8200\n",
        "/etc/vault/services/speech2text/role_id": "svc-role-789\n",
        "/etc/vault/services/speech2text/secret_id": "svc-secret-012\n",
    }

    with patch("builtins.open", mock_open(read_data="")) as mock_file:
        def open_side_effect(path, *args, **kwargs):
            mock_file.return_value.read = lambda: file_contents[path]
            return mock_file.return_value

        mock_file.side_effect = open_side_effect

        result = vault_client(service="speech2text")

    mock_client_class.assert_called_once_with(url="https://vault.example.com:8200")
    mock_client.auth.approle.login.assert_called_once_with(
        role_id="svc-role-789",
        secret_id="svc-secret-012",
    )
    assert result == mock_client