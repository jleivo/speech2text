


#!/usr/bin/env python3

import os
import sys
import json
from watchdog.observers import Observer
from src.folder_watcher import FolderWatcherHandler

def load_config(config_path):
    """Load the configuration file."""
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config

def main():
    # Default config path
    config_path = '../config/config.json'

    # Load configuration
    config = load_config(config_path)

    # Create an observer that will monitor the folder for new files
    event_handler = FolderWatcherHandler(config)
    observer = Observer()
    observer.schedule(event_handler, path=config['folder_to_watch'], recursive=False)

    print(f"Starting to watch {config['folder_to_watch']} for new audio files...")

    # Start the observer
    observer.start()

    try:
        while True:
            pass  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()


