# Speech to text 

A container which translates audio files to text files and places those text files to designated locations.

```text
/audio          - folder to which files appear
/target         - folder to which files should be created
/targets.json   - a text file describing the magic word which is used to move files
/var/models     - location of the Whisper models, recommended to be cached with a volume
```

## targets.json

```JSON
[ 
	{ magicword: "uni", keepaudiofile: "relative/folder", transcript: "relative/file", email: "email@address.fake" },
	{ magicword: "uni", keepaudiofile: "relative/folder", transcript: "relative/file", filename:"uniseuranta", email: "email@address.fake" },
	{ magicword: "default", keepaudiofile: "relative/folder", transcript: "relative/file"}
]
```
### key things

```Text
"magicword": "default" - the default entry for all things
"keepaudiofile": "false" - remove audio file upon translation
"keepaudiofile": anyvalue other value than false, when "email" - field is defined => file is attached to the email
```
