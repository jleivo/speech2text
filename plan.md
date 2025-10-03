
# Speech2Text Application Development Plan

## 1. Project Setup
- Create a new Python project structure
- Set up virtual environment
- Install required dependencies:
  - openai-whisper for speech-to-text conversion
  - watchdog for folder monitoring
  - pytest for testing
  - json schema validation (jsonschema)
  - other utilities (email sending, file operations)

## 2. Core Functionality Development

### 2.1 Folder Monitoring
- Implement a service that monitors a user-defined folder for new audio files
- Use the `watchdog` library to detect new files

### 2.2 Speech-to-Text Conversion
- Create a function that takes an audio file path as input and returns the transcribed text
- Use the `openai-whisper` package for transcription

### 2.3 Magic Word Analysis and Actions
- Implement a function that analyzes the first word of the transcribed text for magic words
- Users define their own magic words in the configuration file, with each magic word associated with:
  - A predefined action type (FILE, APPEND, EMAIL)
  - Action-specific parameters

#### Example Configuration Entries:

1. Magic Word: `KONE`
   - Action: `EMAIL`
   - Parameters:
     - to: juha@leivo.org

2. Magic Word: `food`
   - Action: `APPEND`
   - Parameters:
     - to: files/Resources/fooddiary.md

#### Predefined Actions and Their Parameters:

- `FILE`: Create a new file with the transcribed text
  - Required parameter: `to` (file path)

- `APPEND`: Append the transcribed text to an existing file
  - Required parameter: `to` (file path)

- `EMAIL`: Send the transcribed text via email
  - Required parameters:
    - `to` (email address)
    - `subject` (optional, default: "Transcription")
    - `from` (optional, if not configured globally)

## 3. Configuration Management
- Create a JSON configuration schema that includes:
  - Monitored folder path (required)
  - Global email settings (optional):
    - from: default sender email address
    - smtp_server: SMTP server address
    - smtp_port: SMTP port number
    - smtp_username: SMTP username
    - smtp_password: SMTP password
  - Magic words configuration:
    - Each magic word has an associated action and parameters:
      - action: one of FILE, APPEND, EMAIL (required)
      - to: destination path or email address (required)
      - subject: optional parameter for EMAIL action

### 3.1 Configuration Validation
- Implement validation using jsonschema to ensure all required fields are present

### 3.2 Interactive Configuration Script
- Create a script that allows users to interactively add or update configuration entries:
  - Validate user inputs before adding them to the configuration file
  - Ensure all required fields are provided for each action type

## 4. Testing
- Write pytest tests for all core functionality:
  - Folder monitoring service
  - Speech-to-text conversion function
  - Magic word analysis function
  - Action implementation functions
  - Configuration validation and loading
  - Interactive configuration script

## 5. Documentation
- Write documentation for:
  - Installation and setup
  - Usage instructions
  - Configuration options (with examples)
  - JSON schema reference

## 6. Packaging and Distribution
- Package the application for distribution
- Create a README with installation and usage instructions
