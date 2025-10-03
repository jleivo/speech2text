

# Speech2Text Repository Overview

## Purpose
The purpose of this repository is to develop a Python-based speech-to-text application that:
- Monitors a folder for new audio files
- Transcribes the audio using OpenAI Whisper
- Analyzes the first word of the transcription for "magic words"
- Performs actions based on the magic words (create file, append to file, send email, or execute script)

## General Setup
- Python project with virtual environment
- Uses openai-whisper for speech-to-text conversion
- Uses watchdog for folder monitoring
- Configuration-driven behavior via JSON config file
- Interactive script for updating configuration
- Comprehensive pytest test suite

## Repository Structure
- `plan.md`: Development plan and requirements
- `.openhands/microagents/repo.md`: Repository overview
- `config/` (future): Configuration files and schemas
- `scripts/` (future): Helper scripts including interactive config updater
- `src/` (future): Main application code
  - `monitor.py`: Folder monitoring service
  - `transcribe.py`: Speech-to-text conversion functions
  - `actions.py`: Action implementations for magic words
  - `config.py`: Configuration loading and validation
- `tests/` (future): Pytest test suite

