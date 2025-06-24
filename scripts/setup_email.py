#!/usr/bin/env python3

import json
import re
import smtplib
import socket
import argparse
import sys # For sys.exit
import os # For os.path.exists
import shutil # For shutil.copyfile

def is_valid_email(email):
    """Basic email validation."""
    if not email or not isinstance(email, str): # Ensure email is a non-empty string
        return False

    # Basic structure check with a lenient regex.
    # Allows most characters, focuses on @ and a TLD.
    # Further checks will refine this.
    base_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(base_regex, email):
        return False

    # Split into local and domain parts
    try:
        local_part, domain_part = email.rsplit('@', 1)
    except ValueError:
        return False # Should not happen if regex matched, but defensive

    # --- Local part checks ---
    if not local_part: # local part cannot be empty
        return False
    if local_part.startswith('.') or local_part.endswith('.'):
        return False
    if '..' in local_part:
        return False

    # --- Domain part checks ---
    if not domain_part: # domain part cannot be empty
        return False
    if '..' in domain_part: # No consecutive dots in domain part (e.g. domain..com)
        return False

    domain_labels = domain_part.split('.')
    if len(domain_labels) < 2: # Must have at least one dot (e.g. domain.com)
        return False

    for label in domain_labels:
        if not label: # Empty label (e.g., domain..com, caught by '..' check mostly, but also .com.)
            return False
        if label.startswith('-') or label.endswith('-'):
            return False
        if not re.match(r'^[a-zA-Z0-9-]+$', label): # Ensure only allowed characters in labels
             return False #This check might be redundant with base_regex but ensures per-label validity

    # TLD check (last label)
    tld = domain_labels[-1]
    if not (len(tld) >= 2 and tld.isalpha()): # Original TLD check was [a-zA-Z]{2,}
         # Allowing alphanumeric TLDs based on original regex [a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
         # The original regex was `[a-zA-Z]{2,}` for TLD. Let's stick to that.
         # The base_regex already has \.[a-zA-Z]{2,}$, so this specific check on TLD might be slightly redundant
         # but reinforces the TLD specific rules if base_regex was more lenient on TLD.
         # For now, the base_regex's TLD check is `[a-zA-Z]{2,}`.
         pass # Base regex already covers this: \.[a-zA-Z]{2,}$

    return True # If all checks pass

def get_email_config():
    """Prompts user for email configuration and returns a dictionary."""
    config = {}

    while True:
        smtp_server_val = input("Enter SMTP server address: ").strip()
        if not smtp_server_val:
            print("SMTP server cannot be empty.")
            continue

        smtp_port_str = input("Enter SMTP port number: ").strip()
        if not smtp_port_str.isdigit():
            print("Invalid port number. Please enter a numeric value.")
            continue

        smtp_port_val = int(smtp_port_str)

        # Validate connection using the centralized function
        if validate_smtp_connection(smtp_server_val, smtp_port_val):
            config["smtp_server"] = smtp_server_val
            config["smtp_port"] = smtp_port_val
            break # Exit loop if connection is successful
        else:
            # Error messages are printed by validate_smtp_connection
            print("Please check the server address and port, and ensure the server is reachable. Try again.\n")
            # Loop continues for another attempt

    while True:
        sender_email = input("Enter sender email address: ").strip()
        if is_valid_email(sender_email):
            config["sender_email"] = sender_email
            break
        else:
            print("Invalid email address format.")

    return config

def validate_smtp_connection(smtp_server, smtp_port):
    """Attempts to connect to the SMTP server. Returns True if successful, False otherwise."""
    try:
        print(f"Attempting to connect to {smtp_server}:{smtp_port} for validation...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server_conn:
            pass # Connection successful
        print(f"Successfully connected to SMTP server {smtp_server}:{smtp_port}.")
        return True
    except smtplib.SMTPConnectError as e:
        print(f"Validation Error: Could not connect to SMTP server. {e}")
    except socket.gaierror:
        print(f"Validation Error: SMTP server address '{smtp_server}' is invalid or could not be resolved.")
    except ConnectionRefusedError:
        print(f"Validation Error: Connection refused by the server {smtp_server}:{smtp_port}.")
    except TimeoutError:
        print(f"Validation Error: Connection to {smtp_server}:{smtp_port} timed out.")
    except smtplib.SMTPServerDisconnected:
        print(f"Validation Error: Server disconnected unexpectedly.")
    except Exception as e:
        print(f"An unexpected error occurred during SMTP validation: {e}")
    return False

def validate_email_config_data(config_data):
    """Validates the structure and content of loaded email configuration data."""
    print("\nValidating email.json content...")
    valid = True
    required_keys = ["smtp_server", "smtp_port", "sender_email"]

    for key in required_keys:
        if key not in config_data:
            print(f"Structure Error: Missing key '{key}' in email.json.")
            valid = False
    if not valid: # Stop further checks if structure is already wrong
        return False

    if not isinstance(config_data.get("smtp_server"), str) or not config_data.get("smtp_server").strip():
        print("Structure Error: 'smtp_server' must be a non-empty string.")
        valid = False

    if not isinstance(config_data.get("smtp_port"), int):
        print("Structure Error: 'smtp_port' must be an integer.")
        valid = False

    sender_email_val = config_data.get("sender_email")
    if not isinstance(sender_email_val, str) or not is_valid_email(sender_email_val):
        print(f"Structure Error: 'sender_email' ('{sender_email_val}') is not a valid email format.")
        valid = False

    if not valid: # Don't attempt SMTP connection if structure is bad
        return False

    # If structure is okay, try SMTP connection
    if not validate_smtp_connection(config_data["smtp_server"], config_data["smtp_port"]):
        valid = False

    return valid

def main():
    parser = argparse.ArgumentParser(description="Setup or validate email.json configuration.")
    parser.add_argument("--validate", action="store_true", help="Validate an existing email.json file.")
    args = parser.parse_args()

    filename = "email.json"
    backup_filename = "email.bck"
    action = 'n' # Default action is 'new'

    # --- Validation Mode ---
    if args.validate:
        print(f"Attempting to validate '{filename}'...")
        if not os.path.exists(filename):
            print(f"Error: '{filename}' not found. Cannot validate.")
            sys.exit(1)
        try:
            with open(filename, "r") as f:
                config_data = json.load(f)
            print(f"Successfully loaded '{filename}'.")
        except json.JSONDecodeError as e:
            print(f"Error: Could not parse '{filename}'. Invalid JSON: {e}")
            sys.exit(1)

        if validate_email_config_data(config_data):
            print(f"\nValidation successful: '{filename}' is correctly structured and SMTP connection test passed.")
            sys.exit(0)
        else:
            print(f"\nValidation failed for '{filename}'. Please check the errors above.")
            sys.exit(1)

    # --- Interactive Mode ---
    if os.path.exists(filename):
        while True:
            action = input(f"'{filename}' already exists. What would you like to do?\n"
                           "(v)alidate, (u)pdate, or (e)xit script? ").strip().lower()
            if action == 'v':
                print(f"Validating existing '{filename}'...")
                try:
                    with open(filename, "r") as f:
                        config_data = json.load(f)
                    if validate_email_config_data(config_data):
                        print(f"\nValidation successful: '{filename}' is correctly structured and SMTP connection test passed.")
                    else:
                        print(f"\nValidation failed for '{filename}'. Please check the errors above.")
                except FileNotFoundError: # Should not happen due to os.path.exists check, but good practice
                    print(f"Error: '{filename}' not found during validation attempt.")
                except json.JSONDecodeError as e:
                    print(f"Error: Could not parse '{filename}'. Invalid JSON: {e}")
                sys.exit(0) # Exit after validation attempt

            elif action == 'u':
                print(f"Proceeding to update '{filename}'...")
                if os.path.exists(backup_filename):
                    backup_choice = input(f"Existing backup '{backup_filename}' found. It WILL BE OVERRIDDEN. Continue (y/n)? ").strip().lower()
                    if backup_choice != 'y':
                        print("Update cancelled by user.")
                        sys.exit(0)
                try:
                    shutil.copyfile(filename, backup_filename)
                    print(f"Backup of '{filename}' created as '{backup_filename}'.")
                except IOError as e:
                    print(f"Error creating backup: {e}. Update cancelled.")
                    sys.exit(1)

                # Proceed to get new config and write it
                break # Exits the action prompt loop to proceed with get_email_config()

            elif action == 'e':
                print("Exiting script.")
                sys.exit(0)
            else:
                print("Invalid choice. Please enter 'v', 'u', or 'e'.")

    # If we reach here, it's either a new file setup or an update confirmed
    print("\nEmail Configuration Setup")
    print("-------------------------")

    email_config = get_email_config()

    try:
        with open(filename, "w") as f:
            json.dump(email_config, f, indent=4)
        if action == 'u': # Check if we were in update mode
            print(f"\nSuccessfully updated '{filename}' with the new configuration:")
        elif action == 'n': # Check if it was a new file creation
            print(f"\nSuccessfully created '{filename}' with the following configuration:")
        else: # Should ideally not happen with current logic, but as a fallback
            print(f"\nConfiguration saved to '{filename}':")
        print(json.dumps(email_config, indent=4))
        print(f"\nImportant: Ensure '{filename}' is placed in the correct directory (e.g., mapped to /email.json in Docker).")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

if __name__ == "__main__":
    main()
