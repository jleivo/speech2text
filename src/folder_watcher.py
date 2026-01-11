#!/usr/bin/env python3

import os
import time
from watchdog.events import FileSystemEventHandler
from src.transcribe import transcribe_audio
from src.actions import perform_action

class FolderWatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.wav', '.mp3', '.flac')):
            print(f"New audio file detected: {event.src_path}")
            self.process_audio_file(event.src_path)

    def process_audio_file(self, file_path):
        """Process a new audio file."""
        # Wait for the file to be completely written
        time.sleep(1)  # Simple delay - could be improved with better file monitoring

        # Transcribe the audio
        transcription = transcribe_audio(file_path)
        if not transcription:
            print(f"Failed to transcribe: {file_path}")
            return

        print(f"Transcription: {transcription}")

        # Check for magic words and perform actions
        self.check_for_magic_words(transcription)

    def check_for_magic_words(self, transcription):
        """Check the transcription for magic words and perform corresponding actions."""
        for keyword, action_config in self.config['magic_words'].items():
            if keyword.lower() in transcription.lower():
                print(f"Magic word '{keyword}' found. Performing action...")
                perform_action(action_config, transcription)
                break  # Only perform one action per transcription

