# Speech to text 

A container which translates audio files to text files and places those text files to designated locations.

```text
/audio          - folder to which files appear
/target         - folder to which files should be created
/targets.json   - a text file describing the magic word which is used to move files
/config.json    - simple email integration - supports only very simple SMTP
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

### email definition (expets config.json)

required parameters and valid values:
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
    -v /host/user/config.json./config.json  -u $(id -u ${USER}):$(id -g ${USER}) speech2text
```