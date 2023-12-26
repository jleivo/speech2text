# Speech to text 

A container which translates audio files to text files and places those text files to designated locations.

/audio          - folder to which files appear
/target         - folder to which files should be created
/targets.json   - a text file describing the magic word which is used to move files
/var/models     - location of the Whisper models, recommended to be cached with a volume


## targets.txt

default,inbox			Where to place audio notes when they don't match any known magic word
file,Resources/Obsidian/media	Where to store files
task,email@address.com		A magic word which causes email creation to happen

