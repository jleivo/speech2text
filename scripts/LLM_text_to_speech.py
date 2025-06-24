#!/usr/bin/env python3
#
# Author: Juha Leivo
# Version: 2
# Date: 2025-06-24
#
# History
#   1 - 2024-01-03, initial write
#   2 - 2025-06-24, Jules: remove the magic word from output
#                   Juha: change model to turbo

import whisper
import argparse
import sys
import time
import os
import json
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

supported_files = [".mp3",".wav",".m4a"]

# our whisper AI model
class transciber:

    model_location = "/var/models"
    cpu_fp = {'fp16':False}
    smtp_server = ""
    smtp_port = ""
    sender_email = ""
    config = {}
    debuginfo = False

    def __init__(self,model_size = "turbo", debuginfo = False):
        self.model = whisper.load_model(model_size, download_root = self.model_location )
        self.debuginfo = debuginfo

    def transcribe(self,speech_file):
        result = self.model.transcribe(speech_file)
        return(result["text"])

    def load_config(self):
        # check if email server configuration is defined in /config.json
        if not os.path.isfile('/config.json'):
            print("No email configuration")
        else:
            with open('/config.json') as f:
                # try to load config file, exit out if not valid json
                try:
                    emaildata = json.load(f)
                except Exception as e:
                    print("Error loading email config file")
                    print(e)
                    sys.exit(1)
            # Set internal variables
            try:
                self.smtp_server = emaildata["smtp_server"]
                self.smtp_port = emaildata["smtp_port"]
                self.sender_email = emaildata["sender_email"]
            except Exception as e:
                print("Error loading email configuration")
                print(e)
                sys.exit(1)

        with open('/targets.json') as f:
            # try to load config file, exit out if not valid json
            try:
                config = json.load(f)
            except Exception as e:
                print("Error loading targets definition file")
                print(e)
                sys.exit(1)
        
        # verify that key default exists in the dictionary config
        if 'default' not in config: 
            print("Error: key default not found in config file"
                + "/targets.json"
                + "Exiting...."
            )
            sys.exit(1)

        self.config = config

        if self.debuginfo:
            print(f"Config: {self.config}")
            print(f"Sender email: {self.sender_email}")
            print(f"SMTP server: {self.smtp_server}")
            print(f"SMTP port: {self.smtp_port}")
            print(f"Model location: {self.model_location}")
            print(f"CPU FP: {self.cpu_fp}")
            print(f"Debuginfo: {self.debuginfo}")

    def __get_magic_word(self,text):
        """
            Function to get the magic word for evaluation.
            Everything that is not alphabet characters is removed and 
            lowercased.
        """
        magic_word = text.split()[0]
        magic_word = magic_word.strip('.,!?;:()[]"\'')
        magic_word = magic_word.lower()

        if self.debuginfo:
            print(f"DEBUG: Magic word: {magic_word}")
        
        return(magic_word)

    def __get_targeting_details(self,magic_word):
        """
            Function to get the targeting details for the magic word.
            If the magic word is not in the dictionary, the default 
            configuration is returned.
            2024-01-08 Missing sanity checking
        """
        if magic_word in self.config:
            # get the configurion from the dictionary
            details = self.config[magic_word]
        else:
            # if magic word is not in the dictionary, get the default
            details = self.config['default']
        
        if self.debuginfo:
            print(f"DEBUG: Targeting details: {details}")
        
        return(details)

    def __create_email_message(self,text,details,folder,filename):
        """
            Wrapper function for the send email function to massage the data
            based on details definitions.
            if the transcript doesn't have correct definitions, the message will
            be in the body and WARNING message is printed
        """
        if details['transcript'] == 'subject':
            subject = text
            body = "."
        else: 
            if not details['transcript'] == 'body':
                print(f"WARNING: Faulty transcript definition")
            body = text
            subject = "Whisper AI transcript"
        
        if self.debuginfo:
            print(f"DEBUG: Sending email to {details['email']}")
            print(f"DEBUG: Subject: {subject}")
            print(f"DEBUG: Body: {body}")
    
        if details['keepaudiofile']:
            if self.debuginfo:
                print(f"DEBUG: Attaching the audio file to the email.")
            self.__send_email(receiver_email = details['email'], \
                            subject = subject, message = body, \
                                attachment = folder + "/" + filename)
        else:
            self.__send_email(receiver_email = details['email'], \
                            subject = subject, message = body)
        if self.debuginfo:
            print(f"DEBUG: Email most likely sent.")
            print(f"DEBUG: removing audiofile")
        os.remove(folder + "/" + filename)

        return

    def handle_output(self,text,folder,filename):
        """
            Public function to handle the output of the transciption.

            First checked detail is the email definition, if that exists
            everything is handled as email and sent away. However, if the 
            email server definition is faulty the note is handled as indicated
            by the default configuration
        """

        if self.debuginfo:
            print(f"DEBUG: Folder is {folder} and the target filename \
                  is {filename}")
            print(f"DEBUG: {text}")

        potential_magic_word = self.__get_magic_word(text)
        details = self.__get_targeting_details(potential_magic_word)

        # Remove the magic word from the text only if it's a configured one
        # and not the 'default' configuration.
        # We use potential_magic_word for the check, as it's the actual first word found.
        if potential_magic_word in self.config and potential_magic_word != 'default':
            # Need to be careful if the original text didn't exactly start with potential_magic_word
            # due to __get_magic_word's transformations (lower, strip punctuation).
            # So, we re-evaluate the part to remove based on the original text.
            # A simple way is to check if the original text, after stripping and lowercasing its first word,
            # matches the potential_magic_word.

            first_word_original_text = text.split(maxsplit=1)[0]
            # Compare the processed first word of the original text with the potential_magic_word
            if self.__get_magic_word(first_word_original_text) == potential_magic_word:
                 # Remove the original first word (which corresponds to the magic word)
                text = text[len(first_word_original_text):].lstrip()

        if 'email' in details:
            if self.smtp_server == "" or self.smtp_port == "" or self.sender_email == "":
                print(f"WARNING: email configuration faulty!")
                details = self.__get_targeting_details("default")
            else:
                self.__create_email_message(text,details,folder,filename)
                return
            
            
        if not 'filename' in details:
            # filename is the same as the original filename, but the file type
            # is changed to md
            target_filename = filename.rsplit('.', 0)[0] + ".md"
        else:
            target_filename = details['filename']
        # Append the text to the file located in details['transcript'] folder 
        # with the filename details['filename']. Create file, if it doesn't exist
        with open("/target/" + details['transcript'] + "/" + target_filename, 'a') as f:
            # check if details require timestamp (timestamp: True) and prepend
            # timestamp to the text in the format of YYYY-MM-DD HH:MM:SS
            if 'timestamp' in details and details['timestamp']:
                text = time.strftime("%Y-%m-%d %H:%M:%S") + " " + text
            f.write(text + "\n")
            # Check if the audio file should be kept (keepaudiofile is not False)
            # If not False, move the audio file to the folder specified in keepaudiofile
            # and append a Markdown link to the file in the text
            if 'keepaudiofile' in details and details['keepaudiofile']:
                # check if target file name is already taken, if it is, append a unix 
                # epoch time stamp to the file name just before the file type
                if os.path.isfile("/target/" + details['keepaudiofile'] + "/" + filename):
                    print("File name already taken, appending unix epoch time stamp to file name")
                    filename_epoch = filename.rsplit('.', 0)[0] + "_" + str(int(time.time())) + "." + filename.split('.')[-1]
                    print(f"Moving audio file {filename_epoch} to {details['keepaudiofile']}")
                    # file rename using shutil.move in case the folders map to different filesystems
                    shutil.move(folder + "/" + filename, "/target/" + details['keepaudiofile'] + "/" + filename_epoch)
                    f.write(f"![[{filename_epoch}]]")
                else:
                    print(f"Moving audio file {filename} to {details['keepaudiofile']}")
                    shutil.move(folder + "/" + filename, "/target/" + details['keepaudiofile'] + "/" + filename)
                    f.write(f"![[{filename}]]")
            else:
                print(f"Removing file {filename}")
                os.remove(folder + "/" + filename)
                
            f.close()

    def __send_email(self, receiver_email, subject, message, attachment=None):

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        print(f"Sending email to {receiver_email}")

        body = message
        msg.attach(MIMEText(body, 'plain'))

        if attachment:
            filename = attachment
            attachment = open(attachment, "rb")

            part = MIMEBase('application', 'octet-stream')
            part.set_payload((attachment).read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', "attachment; filename= %s" % filename)

            msg.attach(part)

        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.sendmail(self.sender_email, receiver_email, msg.as_string())
        server.quit()
    


################################# FUNCTIONS ###################################

def init(arguments):
    parser = argparse.ArgumentParser(arguments, description='Speech-to-Text tool')
    parser.add_argument('-m','--model', required = False, help = 'Whisper AI \
                        model size to run: small, medium(default), large',
                        default = "medium")
    parser.add_argument('-f','--folder', required = False, help = 'Folder to \
                        monitor', default = "/audio")
    parser.add_argument('-d','--debug', default = False, action="store_true", \
                        help = 'Enable Debug mode')
    
    # verify that /targets.json exists
    if not os.path.isfile('/targets.json'):
        raise Exception("File /targets.json not found")
    try:
        results = parser.parse_args()
    except argparse.ArgumentError as e:
        raise(e)
    return results


################################### LOGIC #####################################

def main(arguments):
    try: 
        args = init(arguments)
    except Exception as e:
        print(e)
        sys.exit(1)

    print("Starting whisper AI with model {}".format(args.model))
    AI = transciber(args.model,args.debug)
    print("Whisper AI started")

    print("Loading config file")
    # Config files are always the /targets.json and /config.json
    AI.load_config()
    print("Config file(s) loaded")

    # start monitoring given folder to files
    print("Monitoring folder " + args.folder)
    while True:
        for filename in os.listdir(args.folder):
            # check if the file ending is one of the supported ones
            if not filename.endswith(tuple(supported_files)):
                continue
            print("Transcribing " + filename)
            text = AI.transcribe(args.folder + "/" + filename)
            print("Transcribed text from file " + filename)
            AI.handle_output(text,args.folder,filename)
            break
        time.sleep(1)

if __name__ == "__main__":
    main(sys.argv)