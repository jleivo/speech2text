import logging
import time

from watchdog.observers import Observer

from src.config import load_config
from src.folder_watcher import FolderWatcherHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main(config_path="config/config.json"):
    config = load_config(config_path)

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
