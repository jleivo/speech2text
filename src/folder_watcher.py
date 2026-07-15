import logging
import os
import time

from watchdog.events import FileSystemEventHandler

from src.logger import log_transcription
from src.router import route_transcription
from src.transcribe import transcribe_audio

logger = logging.getLogger(__name__)


def _wait_for_file_stable(file_path, interval=0.5, checks=3, max_wait=30):
    """Wait for file to stabilize by size, with a max_wait timeout (§156, R2-C1).

    Returns True if file stabilized, False if timeout was reached.
    """
    previous_size = -1
    stable_count = 0
    elapsed = 0
    while stable_count < checks and elapsed < max_wait:
        current_size = os.path.getsize(file_path)
        if current_size == previous_size:
            stable_count += 1
        else:
            stable_count = 0
        previous_size = current_size
        time.sleep(interval)
        elapsed += interval
    return stable_count >= checks


class FolderWatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        # Store extensions in lowercase for case-insensitive matching (§306, R2-M4)
        self.extensions = tuple(ext.lower() for ext in config.get("watched_extensions", []))

    def _match_extension(self, path):
        """Case-insensitive extension matching (§306, R2-M4)."""
        return path.lower().endswith(self.extensions)

    def on_moved(self, event):
        if event.is_directory:
            return
        if not self._match_extension(event.dest_path):
            return
        logger.info("New audio file detected via rename: %s", event.dest_path)
        self.process_audio_file(event.dest_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if not self._match_extension(event.src_path):
            return
        logger.info("New audio file detected: %s", event.src_path)
        self.process_audio_file(event.src_path)

    def process_audio_file(self, file_path):
        # Skip symlinks (§163, R2-M8)
        if os.path.islink(file_path):
            logger.warning("Skipping symlink: %s", file_path)
            return

        # Wait for file to stabilize with timeout
        if not _wait_for_file_stable(file_path):
            logger.warning("File did not stabilize within timeout: %s", file_path)
            return

        try:
            transcription = transcribe_audio(
                file_path,
                backend=self.config["backend"],
                model=self.config["model"],
            )
        except Exception:
            logger.exception("Failed to transcribe %s", file_path)
            return

        # Guard against empty/whitespace transcription — skip dispatch (§164, R2-m5)
        if not transcription or not transcription.strip():
            logger.warning("Empty transcription for %s, skipping dispatch", file_path)
            return

        # route_transcription in its own try/except (§162, R2-C4, M3)
        action = None
        success = False
        try:
            action, success = route_transcription(transcription, self.config)
        except Exception:
            logger.exception("Failed to route transcription for %s", file_path)

        # log_transcription in its own try/except (§162, R2-C5, M3)
        log_path = self.config.get("transcription_log")
        if log_path:
            try:
                log_transcription(log_path, file_path, transcription, action, success)
            except Exception:
                logger.exception("Failed to log transcription for %s", file_path)

        # os.remove in its own try/except (§162, M3)
        if self.config.get("delete_after_processing") and success:
            try:
                os.remove(file_path)
                logger.info("Deleted %s", file_path)
            except OSError:
                logger.exception("Failed to delete %s", file_path)
