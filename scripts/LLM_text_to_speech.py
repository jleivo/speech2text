#!/usr/bin/env python3
#
# Author: Juha Leivo
# Version: 1
# Date: 2024-01-03
#
# History
#   1 - 2024-01-03, initial write

import whisper
import argparse
import sys
import time
import os
import json

# our whisper AI model
class transciber:

    model_location = "/var/models"
    cpu_fp = {'fp16':False}

    def __init__(self,model_size = "medium"):
        self.model = whisper.load_model(model_size, download_root = self.model_location )

    def transcribe(self,speech_file):
        result = self.model.transcribe(speech_file)
        return(result["text"])



################################# FUNCTIONS ###################################

def init(arguments):
    parser = argparse.ArgumentParser(arguments, description='Speech-to-Text tool')
    parser.add_argument('-m','--model', required = False, help = 'Whisper AI \
                        model size to run: small, medium(default), large',
                        default = "medium")
    parser.add_argument('-f','--folder', required = False, help = 'Folder to \
                        monitor', default = "/audio")
    
    # verify that /targets.json exists
    if not os.path.isfile('/targets.json'):
        raise Exception("File /targets.json not found")

    try:
        results = parser.parse_args()
    except argparse.ArgumentError as e:
        raise(e)
    return results

def load_config():
    with open('/targets.json') as f:
        # try to load config file, exit out if not valid json
        try:
            config = json.load(f)
        except Exception as e:
            print("Error loading config file")
            print(e)
            sys.exit(1)
    
    # verify that key default exists in the dictionary config
    if 'default' not in config: 
        print("Error: key default not found in config file"
              + "/targets.json"
              + "Exiting...."
           )
        sys.exit(1)

    return config

# Check what to do with the given text, based on the first word
# in the text. It is matched against the dictionary and actions are taken
# accordingly
def handle_output(text,config,folder,filename):

    # magic word is first word from the variable text
    magic_word = text.split()[0]
    # check if magic word is in the dictionary config
    if magic_word in config:
        # get the configurion from the dictionary
        details = config[magic_word]
    else:
        # if magic word is not in the dictionary, get the default
        details = config['default']
    if not 'filename' in details:
        # filename is the same as the original filename, but the file type
        # is changed to md
        details['filename'] = filename.rsplit('.', 1)[0] + ".md"
    # Append the text to the file located in details['transcript'] folder 
    # with the filename details['filename']. Create file, if it doesn't exist
    with open("/target/" + details['transcript'] + "/" + details['filename'], 'a') as f:
        # check if details require timestamp (timestamp: True) and prepend
        # timestamp to the text in the format of YYYY-MM-DD HH:MM:SS
        if 'timestamp' in details and details['timestamp']:
            text = time.strftime("%Y-%m-%d %H:%M:%S") + " " + text
        f.write(text + "\n")
        # Check if the audio file should be kept (keepaudiofile is not False)
        # If not False, move the audio file to the folder specified in keepaudiofile
        # and append a Markdown link to the file in the text
        if 'keepaudiofile' in details and details['keepaudiofile']:
            os.rename(folder + "/" + filename, "/target/" + details['keepaudiofile'] + "/" + filename)
            f.write("![](" + filename + ")\n")
        f.close()
        

################################### LOGIC #####################################

def main(arguments):
    try: 
        args = init(arguments)
    except Exception as e:
        print(e)
        sys.exit(1)

    print("Starting whisper AI with model {}".format(args.model))
    AI = transciber(args.model)

    print("loading config file")
    # Config file is always the /targets.json
    config = load_config()
    print("Config file loaded")

    # start monitoring given folder to files
    print("Monitoring folder " + args.folder)
    while True:
        for filename in os.listdir(args.folder):
            print("Transcribing " + filename)
            text = AI.transcribe(args.folder + "/" + filename)
            print("Transcribed text from file " + filename)
            handle_output(text,config,args.folder,filename)
            os.remove(args.folder + "/" + filename)
            break
        time.sleep(1)

if __name__ == "__main__":
    main(sys.argv)