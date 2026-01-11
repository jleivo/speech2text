#!/usr/bin/env python3

import os
import json
from src.config import load_config, create_default_config

def main():
    config_dir = '../config'
    config_path = os.path.join(config_dir, 'config.json')

    if not os.path.exists(config_path):
        print(f"Configuration file not found. Creating a default one...")
        config_path = create_default_config(config_dir)

    # Load the current configuration
    config = load_config(config_path)
    print("Current configuration:")
    print(json.dumps(config, indent=2))

    # Ask user for updates
    print("\nPlease enter new values or press Enter to keep existing ones:")

    folder_to_watch = input(f"Folder to watch ({config['folder_to_watch']}): ") or config['folder_to_watch']

    updated_magic_words = {}
    for keyword, action_config in config['magic_words'].items():
        print(f"\nUpdating magic word: {keyword}")
        print(f"Current action: {action_config['action']}")

        action = input("Action (create_file, append_to_file, send_email, execute_script): ") or action_config['action']

        if action == 'create_file':
            file_path_template = input(f"File path template ({action_config.get('file_path_template', '')}): ") or action_config['file_path_template']
            updated_magic_words[keyword] = {'action': action, 'file_path_template': file_path_template}
        elif action == 'append_to_file':
            file_path = input(f"File path ({action_config.get('file_path', '')}): ") or action_config['file_path']
            updated_magic_words[keyword] = {'action': action, 'file_path': file_path}
        elif action == 'send_email':
            recipient = input(f"Recipient email ({action_config.get('recipient', '')}): ") or action_config['recipient']
            subject = input(f"Subject ({action_config.get('subject', '')}): ") or action_config['subject']
            updated_magic_words[keyword] = {'action': action, 'recipient': recipient, 'subject': subject}
        elif action == 'execute_script':
            script_path = input(f"Script path ({action_config.get('script_path', '')}): ") or action_config['script_path']
            updated_magic_words[keyword] = {'action': action, 'script_path': script_path}

    # Update the configuration
    updated_config = {
        'folder_to_watch': folder_to_watch,
        'magic_words': updated_magic_words
    }

    # Save the updated configuration
    with open(config_path, 'w') as f:
        json.dump(updated_config, f, indent=4)

    print(f"\nUpdated configuration saved to: {config_path}")

if __name__ == "__main__":
    main()



