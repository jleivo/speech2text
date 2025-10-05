




#!/usr/bin/env python3

import os
import datetime
import subprocess
import smtplib
from email.mime.text import MIMEText

def perform_action(action_config, content):
    """
    Perform an action based on the configuration.

    Args:
        action_config (dict): The action configuration from the config file
        content (str): The content to use for the action
    """
    action_type = action_config['action']

    if action_type == 'create_file':
        create_file(action_config, content)
    elif action_type == 'append_to_file':
        append_to_file(action_config, content)
    elif action_type == 'send_email':
        send_email(action_config, content)
    elif action_type == 'execute_script':
        execute_script(action_config, content)
    else:
        print(f"Unknown action: {action_type}")

def create_file(action_config, content):
    """Create a new file with the given content."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = action_config['file_path_template'].replace('{timestamp}', timestamp)

    # Create parent directories if they don't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Created file: {file_path}")

def append_to_file(action_config, content):
    """Append the given content to an existing file."""
    file_path = action_config['file_path']

    with open(file_path, 'a') as f:
        f.write(content + '\n')

    print(f"Appended to file: {file_path}")

def send_email(recipient, subject, body):
    """
    Send an email with the given content.

    Args:
        recipient (str): The email address to send to
        subject (str): The subject of the email
        body (str): The body of the email
    """
    # For real-world usage, you would configure and use a proper SMTP server here
    print(f"Would send email to {recipient} with subject '{subject}' and body:\n{body}")

def execute_script(script_path, message):
    """
    Execute a script with the given message.

    Args:
        script_path (str): The path to the script to execute
        message (str): The message to pass to the script
    """
    # Execute the script with the message as input
    result = subprocess.run(['bash', script_path], input=message, text=True)

    if result.returncode == 0:
        print(f"Successfully executed script: {script_path}")
    else:
        print(f"Failed to execute script: {script_path}, return code: {result.returncode}")

def send_email_old(action_config, content):
    """Send an email with the given content (legacy function)."""
    # TODO: Implement actual email sending
    recipient = action_config.get('recipient', '')
    subject = action_config.get('subject', 'New transcription')

    print(f"Would send email to {recipient} with subject '{subject}' and body:\n{content}")

def execute_script_old(action_config, content):
    """Execute a script with the given content as input (legacy function)."""
    script_path = action_config['script_path']

    # Write content to a temporary file
    temp_file_path = '/tmp/speech2text_input.txt'
    with open(temp_file_path, 'w') as f:
        f.write(content)

    # Execute the script
    result = subprocess.run(['python', script_path, temp_file_path])

    if result.returncode == 0:
        print(f"Successfully executed script: {script_path}")
    else:
        print(f"Failed to execute script: {script_path}, return code: {result.returncode}")

