#!/usr/bin/env python3

import whisper
import argparse
import os

model_size = os.environ.get('MODEL',"medium")
cpu = {'fp16':False}

def transcribe_file(speech_file):
    model = whisper.load_model(name = model_size,download_root = "/var/models")
    result = model.transcribe(speech_file, **cpu)
    return(result["text"])

parser = argparse.ArgumentParser()
parser.add_argument('-f','--file',required = True)
args = parser.parse_args()

result = transcribe_file(args.file)
#trim leading white spaces
print(result.strip())