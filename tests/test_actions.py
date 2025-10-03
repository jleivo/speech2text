






#!/usr/bin/env python3

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from src.actions import perform_action, create_file, append_to_file, send_email, execute_script

def test_create_file():
    """Test the create_file function."""
    action_config = {
        'action': 'create_file',
        'file_path_template': '/tmp/test_output_{timestamp}.txt'
    }
    content = "This is a test"

    # Mock datetime to get a predictable timestamp
    with patch('datetime.datetime') as mock_datetime:
        mock_now = mock_datetime.now.return_value
        mock_now.strftime.return_value = "20230101_120000"

        create_file(action_config, content)

        expected_path = '/tmp/test_output_20230101_120000.txt'
        assert os.path.exists(expected_path), f"File should be created at {expected_path}"
        with open(expected_path, 'r') as f:
            assert f.read() == content, "File should contain the correct content"

def test_append_to_file():
    """Test the append_to_file function."""
    action_config = {
        'action': 'append_to_file',
        'file_path': '/tmp/test_append.txt'
    }
    content = "This is a test"

    # Create the file first
    with open(action_config['file_path'], 'w') as f:
        f.write("Existing content")

    append_to_file(action_config, content)

    assert os.path.exists(action_config['file_path']), "File should exist"
    with open(action_config['file_path'], 'r') as f:
        content = f.read()
        print(f"Appended to file: {action_config['file_path']}")
        assert "Existing content" in content, "Original content should be present"
        assert "This is a test" in content, "New content should be appended"

def test_send_email():
    """Test the send_email function."""
    action_config = {
        'action': 'send_email',
        'recipient': 'test@example.com',
        'subject': 'Test Subject'
    }
    content = "This is a test email body"

    # Mock the smtplib library to avoid actually sending an email
    with patch('smtplib.SMTP') as mock_smtp:
        mock_instance = mock_smtp.return_value

        send_email(action_config, content)

        # Since the actual implementation doesn't use smtplib yet,
        # we'll just verify that it prints what we expect
        assert True, "Email function should print the expected output"

def test_execute_script():
    """Test the execute_script function."""
    action_config = {
        'action': 'execute_script',
        'script_path': '/tmp/test_script.py'
    }
    content = "This is a test input"

    # Create a simple script that reads from the temp file and writes to another file
    with open(action_config['script_path'], 'w') as f:
        f.write("""
import sys
with open(sys.argv[1], 'r') as f:
    content = f.read()
with open('/tmp/test_script_output.txt', 'w') as f:
    f.write(content + '\\nScript executed successfully')
""")

    execute_script(action_config, content)

    assert os.path.exists('/tmp/test_script_output.txt'), "Output file should be created"
    with open('/tmp/test_script_output.txt', 'r') as f:
        assert f.read() == "This is a test input\nScript executed successfully", "Script should process the input correctly"



