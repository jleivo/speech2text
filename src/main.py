import logging
import os
import signal
import threading
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


def _validate_script_paths(config):
    """Validate that all script_path values in config exist (R2-m6, R3-M4)."""
    errors = []
    for keyword, word_config in config.get("magic_words", {}).items():
        path = word_config.get("script_path", "")
        if not os.path.exists(path):
            errors.append(f"magic_word '{keyword}': script_path '{path}' does not exist")

    default_action = config.get("default_action")
    if default_action:
        path = default_action.get("script_path", "")
        if not os.path.exists(path):
            errors.append(f"default_action: script_path '{path}' does not exist")

    if errors:
        for err in errors:
            logger.error("Config validation failed: %s", err)
        raise SystemExit(1)


def _startup_scan(handler, config):
    """Process any pre-existing files in the watch directory (R2-C2)."""
    watch_dir = config["folder_to_watch"]
    extensions_lower = tuple(ext.lower() for ext in config.get("watched_extensions", []))

    try:
        for fname in os.listdir(watch_dir):
            if fname.lower().endswith(extensions_lower):
                file_path = os.path.join(watch_dir, fname)
                if os.path.isfile(file_path):
                    logger.info("Startup scan: processing pre-existing file %s", file_path)
                    handler.process_audio_file(file_path)
    except OSError as e:
        logger.error("Failed to scan %s during startup: %s", watch_dir, e)


def main(config_path="config/config.json"):
    config = load_config(config_path)

    # Validate script paths at startup (R2-m6, R3-M4)
    _validate_script_paths(config)

    # Set API base from config (overrides any env var)
    api_base = config.get("api_base")
    if api_base:
        os.environ["OPENAI_API_BASE"] = api_base
        logger.info("Using API base: %s", api_base)

    vault_path = config.get("vault_secret_path")
    if vault_path:
        service = config.get("vault_service")
        key = config.get("vault_secret_key", "litellm_api")
        logger.info("Vault config: path=%s, service=%s, key=%s", vault_path, service, key)
        try:
            api_key = fetch_api_key(vault_path, service, key)
            os.environ["OPENAI_API_KEY"] = api_key
            logger.info("Fetched API key from Vault (path=%s, key=%s)", vault_path, key)
        except Exception as e:
            logger.error("Failed to fetch API key from Vault: %s", e)
            raise SystemExit(1)

    # In-flight processing tracking for graceful shutdown (R2-C3)
    in_flight_count = 0
    in_flight_done = threading.Condition()

    handler = FolderWatcherHandler(config)

    original_process = handler.process_audio_file

    def _tracked_process(file_path):
        nonlocal in_flight_count
        with in_flight_done:
            in_flight_count += 1
        try:
            return original_process(file_path)
        finally:
            with in_flight_done:
                in_flight_count -= 1
                if in_flight_count == 0:
                    in_flight_done.notify_all()

    handler.process_audio_file = _tracked_process

    observer = Observer()
    observer.schedule(handler, path=config["folder_to_watch"], recursive=False)

    logger.info("Watching %s for audio files...", config["folder_to_watch"])

    # SIGTERM handler for graceful shutdown (§103, R2-C3)
    running = True

    def _shutdown_handler(signum, frame):
        nonlocal running
        logger.info("Received SIGTERM, initiating graceful shutdown...")
        observer.stop()
        running = False

    signal.signal(signal.SIGTERM, _shutdown_handler)

    try:
        observer.start()

        # Startup scan: process any pre-existing files (§104, R2-C2)
        _startup_scan(handler, config)

        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()
        # Wait for in-flight tasks to complete (§105, R2-C3)
        with in_flight_done:
            while in_flight_count > 0:
                in_flight_done.wait(timeout=30)
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
