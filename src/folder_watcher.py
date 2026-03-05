import logging
import os
import time

from watchdog.events import FileSystemEventHandler

from src.logger import log_transcription
from src.router import route_transcription
from src.transcribe import transcribe_audio

logger = logging.getLogger(__name__)


def _wait_for_file_stable(file_path, interval=0.5, checks=3):
    previous_size = -1
    stable_count = 0
    while stable_count < checks:
        current_size = os.path.getsize(file_path)
        if current_size == previous_size:
            stable_count += 1
        else:
            stable_count = 0
        previous_size = current_size
        time.sleep(interval)


class FolderWatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.extensions = tuple(config.get("watched_extensions", []))

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(self.extensions):
            return
        logger.info("New audio file detected: %s", event.src_path)
        self.process_audio_file(event.src_path)

    def process_audio_file(self, file_path):
        try:
            _wait_for_file_stable(file_path)
            transcription = transcribe_audio(
                file_path,
                backend=self.config["backend"],
                model=self.config["model"],
            )
        except Exception:
            logger.exception("Failed to transcribe %s", file_path)
            return

        action, success = route_transcription(transcription, self.config)

        log_path = self.config.get("transcription_log")
        if log_path:
            log_transcription(log_path, file_path, transcription, action, success)

        if self.config.get("delete_after_processing") and success:
            os.remove(file_path)
            logger.info("Deleted %s", file_path)
