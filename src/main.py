import logging
import os
import time

from watchdog.observers import Observer

from src.config import load_config
from src.folder_watcher import FolderWatcherHandler
from src.vault import fetch_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main(config_path="config/config.json"):
    config = load_config(config_path)

    vault_path = config.get("vault_secret_path")
    if vault_path:
        service = config.get("vault_service")
        try:
            api_key = fetch_api_key(vault_path, service)
            os.environ["OPENAI_API_KEY"] = api_key
            logger.info("Fetched API key from Vault (path=%s)", vault_path)
        except Exception as e:
            logger.error("Failed to fetch API key from Vault: %s", e)
            raise SystemExit(1)

    handler = FolderWatcherHandler(config)
    observer = Observer()
    observer.schedule(handler, path=config["folder_to_watch"], recursive=False)

    logger.info("Watching %s for audio files...", config["folder_to_watch"])

    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
