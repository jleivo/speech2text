import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.main import main


@patch("src.main.Observer")
@patch("src.main.FolderWatcherHandler")
def test_main_starts_observer(mock_handler_class, mock_observer_class):
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
