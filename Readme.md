# Speech to text 

A container which translates audio files to text files and places those text files to designated locations.

```text
/audio          - folder to which files appear
/target         - folder to which files should be created
/targets.json   - a text file describing the magic word which is used to move files
/email.json     - simple email integration - supports only very simple SMTP
/var/models     - location of the Whisper models, recommended to be cached with a volume
```

## targets.json

JSON structure for text file creation. Options are, keep the source audio file or not
, prepend a time stamp in the form of 2024-01-07 21:04 to the text, and to append to a
specific file - if not stated then the file will be the audiofile with .md file ending.

default describes the minimal requirement JSON structure requirement

```json
{
    "default": { "keepaudiofile": "path/to/folder", "transcript": "path/to/folder" }, 
    "magic word": { "keepaudiofile": "path/to/folder", "transcript": "path/to/folder", "filename":"filename_to_append_transcripts_to" },
    "magic word": { "keepaudiofile": "path/to/folder", "transcript": "path/to/folder", "filename":"filename_to_append_transcripts_to", "timestamp": true },
}
```

### email definition (expects email.json)

The `email.json` file is used for configuring email notifications. You can generate this file by running the setup script:
```bash
python3 scripts/setup_email.py
```
This script helps you create or manage your `email.json` configuration file.

**Workflow:**
- If `email.json` does not exist, the script will guide you through creating a new one, prompting for SMTP server details (with connection validation) and sender email address.
- If `email.json` already exists, you will be prompted to choose an action:
    - **(v)alidate:** Checks the structure of the existing `email.json` and tests the SMTP connection.
    - **(u)pdate:** Allows you to enter new configuration details.
        - Before updating, the script will back up your current `email.json` to `email.bck`.
        - If `email.bck` already exists, you will be warned and asked for confirmation before it's overwritten.
    - **(e)xit:** Exits the script without making any changes.

**Direct Validation:**
You can also directly validate an existing `email.json` file using the `--validate` flag:
```bash
python3 scripts/setup_email.py --validate
```
This performs the same checks as the interactive 'validate' option (structure and SMTP connection test).

**File Content:**
The `email.json` file itself should contain:
- `smtp_server`: The address of your SMTP server.
- `smtp_port`: The port number for your SMTP server.
- `sender_email`: The email address from which notifications will be sent.

Example content of `email.json`:
```json
{
    "smtp_server": "smtp.example.com",
    "smtp_port": 587,
    "sender_email": "noreply@example.com"
}
```

In addition to the `email.json` content, the `targets.json` file uses the following parameters for email actions:
- keepaudiofile: true or false (if true, file is put as a message attachment, if false file is destroyed)
- email: valid email address the receiver
- transcript subject or body (the transcripted text will place in this part of the email)

example:

```json
{ "magic word": {"keepaudiofile": true, "email": "target@email.me", "transcript": "subject"}}
```

## Running the container

```bash
docker run -it -v /host/system/audiofolder:/audio -v whisper_models:/var/models \
    -v /host/filedestinations:/target -v /host/user/targets.json:/targets.json \
    -v /host/user/email.json:/email.json  -u $(id -u ${USER}):$(id -g ${USER}) speech2text
```

## Testing

The project includes unit tests for the `scripts/setup_email.py` utility.

To run the tests, navigate to the root directory of the project and execute the following command:

```bash
python -m unittest discover -s tests
```

Alternatively, you can run a specific test file:
```bash
python -m unittest tests/scripts/test_setup_email.py
```
