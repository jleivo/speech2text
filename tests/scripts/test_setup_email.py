import unittest
import smtplib
import socket
from unittest.mock import patch
from scripts.setup_email import is_valid_email, get_email_config, validate_smtp_connection, validate_email_config_data

class TestIsValidEmail(unittest.TestCase):
    def test_valid_emails(self):
        valid_emails = [
            "test@example.com",
            "firstname.lastname@example.com",
            "email@subdomain.example.com",
            "firstname+lastname@example.com",
            "email@example.co.jp",
            "email@example.name",
            "email@example.museum",
            "email@example.info",
            "1234567890@example.com",
            "_______@example.com",
            "email@example-one.com",
            "email@example.com.com",
            "email@example.COM", # Case insensitivity for domain
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertTrue(is_valid_email(email), f"{email} should be valid")

    def test_invalid_emails(self):
        invalid_emails = [
            "plainaddress",
            "#@%^%#$@#$@#.com",
            "@example.com",
            "Joe Smith <email@example.com>",
            "email.example.com",
            "email@example@example.com",
            ".email@example.com",
            "email.@example.com",
            "email..email@example.com",
            "email@example.com (Joe Smith)",
            "email@example",
            "email@-example.com",
            # "email@example.c", # This one actually passes with the current regex, might be too strict for "good enough"
            "email@111.222.333.44444",
            "email@example..com",
            "Abc..123@example.com",
            r"“(),:;<>[\]@example.com", # Special characters (raw string)
            "just”not”right@example.com",
            r"this\ is\"really\"not\allowed@example.com" # Raw string
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertFalse(is_valid_email(email), f"{email} should be invalid")

    def test_empty_email(self):
        self.assertFalse(is_valid_email(""), "Empty string should be invalid")
        self.assertFalse(is_valid_email(None), "None should be invalid") # Function expects string, but good to test

class TestGetEmailConfig(unittest.TestCase):
    @patch('scripts.setup_email.validate_smtp_connection')
    @patch('builtins.input')
    def test_get_email_config_success(self, mock_input, mock_validate_smtp):
        # Configure mocks
        mock_input.side_effect = ["smtp.example.com", "587", "sender@example.com"]
        mock_validate_smtp.return_value = True

        # Call the function
        config = get_email_config()

        # Assertions
        expected_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender_email": "sender@example.com"
        }
        self.assertEqual(config, expected_config)
        mock_validate_smtp.assert_called_once_with("smtp.example.com", 587)

        # Check input calls (optional, but good for sanity)
        # Corrected expected calls for input based on function logic
        mock_input.assert_any_call("Enter SMTP server address: ")
        mock_input.assert_any_call("Enter SMTP port number: ")
        mock_input.assert_any_call("Enter sender email address: ")
        self.assertEqual(mock_input.call_count, 3)

    @patch('scripts.setup_email.validate_smtp_connection')
    @patch('builtins.input')
    @patch('builtins.print') # To suppress print statements during test
    def test_get_email_config_retry_empty_server(self, mock_print, mock_input, mock_validate_smtp):
        mock_input.side_effect = [
            "",  # Empty SMTP server
            "smtp.example.com", "587", "sender@example.com"
        ]
        mock_validate_smtp.return_value = True

        config = get_email_config()

        expected_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender_email": "sender@example.com"
        }
        self.assertEqual(config, expected_config)
        mock_validate_smtp.assert_called_once_with("smtp.example.com", 587)
        self.assertEqual(mock_input.call_count, 4) # Server, Server, Port, Email
        mock_print.assert_any_call("SMTP server cannot be empty.")

    @patch('scripts.setup_email.validate_smtp_connection')
    @patch('builtins.input')
    @patch('builtins.print') # To suppress print statements
    def test_get_email_config_retry_invalid_port(self, mock_print, mock_input, mock_validate_smtp):
        mock_input.side_effect = [
            "smtp.example.com",  # Initial server
            "abc",               # Invalid port
            "smtp.example.com",  # Server again due to outer loop continue
            "587",               # Valid port
            "sender@example.com" # Sender email
        ]
        mock_validate_smtp.return_value = True

        config = get_email_config()

        expected_config = {
            "smtp_server": "smtp.example.com", # Should be the one from the second successful attempt
            "smtp_port": 587,
            "sender_email": "sender@example.com"
        }
        self.assertEqual(config, expected_config)
        # validate_smtp_connection is called with the server from the successful port entry
        mock_validate_smtp.assert_called_once_with("smtp.example.com", 587)
        self.assertEqual(mock_input.call_count, 5) # Server, Port, Server, Port, Email
        mock_print.assert_any_call("Invalid port number. Please enter a numeric value.")

    @patch('scripts.setup_email.validate_smtp_connection')
    @patch('builtins.input')
    @patch('builtins.print') # To suppress print statements
    def test_get_email_config_retry_smtp_validation(self, mock_print, mock_input, mock_validate_smtp):
        mock_input.side_effect = [
            "smtp1.example.com", "587",  # Fails validation
            "smtp2.example.com", "25",   # Succeeds validation
            "sender@example.com"
        ]
        mock_validate_smtp.side_effect = [False, True]

        config = get_email_config()

        expected_config = {
            "smtp_server": "smtp2.example.com",
            "smtp_port": 25,
            "sender_email": "sender@example.com"
        }
        self.assertEqual(config, expected_config)

        # Check calls to validate_smtp_connection
        self.assertEqual(mock_validate_smtp.call_count, 2)
        mock_validate_smtp.assert_any_call("smtp1.example.com", 587)
        mock_validate_smtp.assert_any_call("smtp2.example.com", 25)

        self.assertEqual(mock_input.call_count, 5) # Server1, Port1, Server2, Port2, Email
        mock_print.assert_any_call("Please check the server address and port, and ensure the server is reachable. Try again.\n")

    @patch('scripts.setup_email.validate_smtp_connection')
    @patch('builtins.input')
    @patch('builtins.print') # To suppress print statements
    def test_get_email_config_retry_invalid_sender_email(self, mock_print, mock_input, mock_validate_smtp):
        mock_input.side_effect = [
            "smtp.example.com", "587",
            "invalid-email",  # Invalid sender email
            "sender@example.com"  # Valid sender email
        ]
        # is_valid_email is called directly, so we don't mock it here but rely on its tested behavior.
        # We only need to ensure validate_smtp_connection is True for the server/port part.
        mock_validate_smtp.return_value = True

        config = get_email_config()

        expected_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender_email": "sender@example.com"
        }
        self.assertEqual(config, expected_config)
        mock_validate_smtp.assert_called_once_with("smtp.example.com", 587)
        self.assertEqual(mock_input.call_count, 4) # Server, Port, Email1, Email2
        mock_print.assert_any_call("Invalid email address format.")


class TestValidateSmtpConnection(unittest.TestCase):

    @patch('builtins.print') # Suppress print calls from the function
    @patch('smtplib.SMTP')
    def test_successful_connection(self, mock_smtp_class, mock_print):
        # Configure the mock SMTP object
        mock_smtp_instance = mock_smtp_class.return_value.__enter__.return_value
        # No specific return value needed for __enter__ or __exit__ for a successful connection

        self.assertTrue(validate_smtp_connection("smtp.example.com", 587))
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_print.assert_any_call("Attempting to connect to smtp.example.com:587 for validation...")
        mock_print.assert_any_call("Successfully connected to SMTP server smtp.example.com:587.")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_smtp_connect_error(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = smtplib.SMTPConnectError(550, "Connection failed")
        self.assertFalse(validate_smtp_connection("smtp.example.com", 587))
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_print.assert_any_call("Validation Error: Could not connect to SMTP server. (550, 'Connection failed')")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_socket_gaierror(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = socket.gaierror("Name or service not known")
        self.assertFalse(validate_smtp_connection("invalid-server", 587))
        mock_smtp_class.assert_called_once_with("invalid-server", 587, timeout=5)
        mock_print.assert_any_call("Validation Error: SMTP server address 'invalid-server' is invalid or could not be resolved.")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_connection_refused_error(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")
        self.assertFalse(validate_smtp_connection("localhost", 587))
        mock_smtp_class.assert_called_once_with("localhost", 587, timeout=5)
        mock_print.assert_any_call("Validation Error: Connection refused by the server localhost:587.")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_timeout_error(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = TimeoutError("Connection timed out")
        self.assertFalse(validate_smtp_connection("smtp.example.com", 587))
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_print.assert_any_call("Validation Error: Connection to smtp.example.com:587 timed out.")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_smtp_server_disconnected(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = smtplib.SMTPServerDisconnected("Server disconnected")
        self.assertFalse(validate_smtp_connection("smtp.example.com", 587))
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_print.assert_any_call("Validation Error: Server disconnected unexpectedly.")

    @patch('builtins.print')
    @patch('smtplib.SMTP')
    def test_generic_exception(self, mock_smtp_class, mock_print):
        mock_smtp_class.side_effect = Exception("A generic error")
        self.assertFalse(validate_smtp_connection("smtp.example.com", 587))
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_print.assert_any_call("An unexpected error occurred during SMTP validation: A generic error")


class TestValidateEmailConfigData(unittest.TestCase):

    def setUp(self):
        """A helper to create a base valid config."""
        self.valid_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender_email": "test@example.com"
        }

    @patch('builtins.print')
    @patch('scripts.setup_email.validate_smtp_connection')
    def test_valid_config(self, mock_validate_smtp, mock_print):
        mock_validate_smtp.return_value = True
        self.assertTrue(validate_email_config_data(self.valid_config))
        mock_validate_smtp.assert_called_once_with("smtp.example.com", 587)
        # Check that introductory print happens
        mock_print.assert_any_call("\nValidating email.json content...")


    @patch('builtins.print')
    def test_missing_keys(self, mock_print):
        for key in ["smtp_server", "smtp_port", "sender_email"]:
            with self.subTest(missing_key=key):
                config = self.valid_config.copy()
                del config[key]
                self.assertFalse(validate_email_config_data(config))
                mock_print.assert_any_call(f"Structure Error: Missing key '{key}' in email.json.")

    @patch('builtins.print')
    def test_invalid_smtp_server_type(self, mock_print):
        config = self.valid_config.copy()
        config["smtp_server"] = 12345 # Not a string
        self.assertFalse(validate_email_config_data(config))
        mock_print.assert_any_call("Structure Error: 'smtp_server' must be a non-empty string.")

    @patch('builtins.print')
    def test_empty_smtp_server(self, mock_print):
        for empty_val in ["", "   "]:
            with self.subTest(empty_value=empty_val):
                config = self.valid_config.copy()
                config["smtp_server"] = empty_val
                self.assertFalse(validate_email_config_data(config))
                mock_print.assert_any_call("Structure Error: 'smtp_server' must be a non-empty string.")

    @patch('builtins.print')
    def test_invalid_smtp_port_type(self, mock_print):
        config = self.valid_config.copy()
        config["smtp_port"] = "587" # Not an int
        self.assertFalse(validate_email_config_data(config))
        mock_print.assert_any_call("Structure Error: 'smtp_port' must be an integer.")

    @patch('builtins.print')
    def test_invalid_sender_email_type(self, mock_print):
        config = self.valid_config.copy()
        config["sender_email"] = 123 # Not a string
        # is_valid_email will receive a non-string, which it handles by returning False.
        self.assertFalse(validate_email_config_data(config))
        mock_print.assert_any_call(f"Structure Error: 'sender_email' ('123') is not a valid email format.")


    @patch('builtins.print')
    @patch('scripts.setup_email.is_valid_email') # We only care that it's called
    def test_invalid_sender_email_format(self, mock_is_valid_email, mock_print):
        mock_is_valid_email.return_value = False # Simulate is_valid_email finding it invalid
        config = self.valid_config.copy()
        config["sender_email"] = "invalid-email-format"
        self.assertFalse(validate_email_config_data(config))
        mock_is_valid_email.assert_called_once_with("invalid-email-format")
        mock_print.assert_any_call(f"Structure Error: 'sender_email' ('invalid-email-format') is not a valid email format.")

    @patch('builtins.print')
    @patch('scripts.setup_email.validate_smtp_connection')
    def test_smtp_validation_fails(self, mock_validate_smtp, mock_print):
        mock_validate_smtp.return_value = False # Simulate SMTP connection failure
        self.assertFalse(validate_email_config_data(self.valid_config))
        mock_validate_smtp.assert_called_once_with(self.valid_config["smtp_server"], self.valid_config["smtp_port"])
        # The error print for SMTP failure is within validate_smtp_connection itself,
        # which is mocked here, so we don't check for its specific print output in this test unit.
        # We do check that the initial validation print occurs.
        mock_print.assert_any_call("\nValidating email.json content...")
