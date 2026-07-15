import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from src.main import main


@patch("src.main._validate_script_paths")
@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_starts_observer(mock_handler_class, mock_observer_class, mock_validate):
    """Main starts observer on configured folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        mock_observer.start.side_effect = KeyboardInterrupt

        main(config_path)

        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()


def test_main_missing_config():
    """Main raises FileNotFoundError for missing config."""
    import pytest
    with pytest.raises(FileNotFoundError):
        main("/nonexistent/config.json")


@patch("src.main._validate_script_paths")
@patch("src.main.fetch_api_key")
@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_fetches_api_key_from_vault(mock_handler_class, mock_observer_class, mock_fetch, mock_validate):
    mock_fetch.return_value = "sk-vault-key-123"
    mock_observer = MagicMock()
    mock_observer_class.return_value = mock_observer
    mock_observer.start.side_effect = KeyboardInterrupt

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
            "vault_secret_path": "secret/hosts/myhost/litellm",
            "vault_service": "speech2text",
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        old_key = os.environ.get("OPENAI_API_KEY")
        main(config_path)

        mock_fetch.assert_called_once_with("secret/hosts/myhost/litellm", "speech2text")
        assert os.environ["OPENAI_API_KEY"] == "sk-vault-key-123"
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)


@patch("src.main._validate_script_paths")
@patch("src.main.fetch_api_key")
@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_skips_vault_when_not_configured(mock_handler_class, mock_observer_class, mock_fetch, mock_validate):
    mock_observer = MagicMock()
    mock_observer_class.return_value = mock_observer
    mock_observer.start.side_effect = KeyboardInterrupt

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        main(config_path)

        mock_fetch.assert_not_called()


@patch("src.main.fetch_api_key")
@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_exits_on_vault_failure(mock_handler_class, mock_observer_class, mock_fetch):
    mock_fetch.side_effect = Exception("Vault unreachable")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        watch_dir = os.path.join(tmpdir, "audio")
        os.makedirs(watch_dir)
        config = {
            "folder_to_watch": watch_dir,
            "magic_words": {"FILE": {"script_path": "/bin/handler.py"}},
            "vault_secret_path": "secret/hosts/myhost/litellm",
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        with pytest.raises(SystemExit):
            main(config_path)
