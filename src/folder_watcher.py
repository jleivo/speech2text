#!/usr/bin/env python3

import os
import time
import shutil
from watchdog.events import FileSystemEventHandler
from src.transcribe import transcribe_audio
from src.actions import perform_action, send_email, execute_script

class FolderWatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.wav', '.mp3', '.flac', '.m4a')):
            print(f"New audio file detected: {event.src_path}")
            self.process_audio_file(event.src_path)

    def process_audio_file(self, file_path):
        """Process a new audio file."""
        # Wait for the file to be completely written
        time.sleep(1)  # Simple delay - could be improved with better file monitoring

        try:
            # Transcribe the audio
            transcription = transcribe_audio(file_path)
            if not transcription:
                raise ValueError("Transcription failed or returned empty result")

            print(f"Transcription: {transcription}")

            # Check for magic words and perform actions
            self.check_for_magic_words(transcription)

        except Exception as e:
            print(f"Failed to transcribe: {file_path}. Error: {str(e)}")
            self.handle_failed_transcription(file_path)

    def handle_failed_transcription(self, file_path):
        """Handle a failed transcription by moving the file and notifying."""
        if 'failed' in self.config:
            failed_config = self.config['failed']
            destination_dir = failed_config.get('to', None)

            if destination_dir and os.path.exists(destination_dir):
                # Create directory if it doesn't exist
                os.makedirs(destination_dir, exist_ok=True)

                # Move the file to the failed directory
                filename = os.path.basename(file_path)
                dest_path = os.path.join(destination_dir, filename)

                try:
                    shutil.move(file_path, dest_path)
                    print(f"Moved failed audio file to: {dest_path}")

                    # Notify via email or script if configured
                    if 'inform' in failed_config and 'script' not in failed_config:
                        send_email(
                            recipient=failed_config['inform'],
                            subject=f"Transcription Failed for {filename}",
                            body=f"Transcribing failed for file {filename}"
                        )
                        print(f"Notified by email: {failed_config['inform']}")

                    elif 'script' in failed_config and 'inform' not in failed_config:
                        execute_script(
                            script_path=failed_config['script'],
                            message=f"transcribing failed for file {filename}"
                        )
                        print(f"Executed script: {failed_config['script']}")
                except Exception as e:
                    print(f"Failed to move or notify about the file: {str(e)}")
            else:
                print(f"Failed directory not configured properly: {destination_dir}")

    def check_for_magic_words(self, transcription):
        """Check the transcription for magic words and perform corresponding actions."""
        for keyword, action_config in self.config['magic_words'].items():
            if keyword.lower() in transcription.lower():
                print(f"Magic word '{keyword}' found. Performing action...")
                perform_action(action_config, transcription)
                break  # Only perform one action per transcription

