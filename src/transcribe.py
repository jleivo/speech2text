import logging

import litellm
import whisper

logger = logging.getLogger(__name__)


def transcribe_audio(file_path, backend="litellm", model="whisper-1"):
    if backend == "litellm":
        try:
            return _transcribe_litellm(file_path, model)
        except Exception as e:
            logger.warning("LiteLLM failed (%s), falling back to local Whisper", e)
            return _transcribe_local(file_path, model="turbo")
    else:
        return _transcribe_local(file_path, model)


def _transcribe_litellm(file_path, model):
    with open(file_path, "rb") as audio_file:
        response = litellm.transcription(model=model, file=audio_file)
    return response.text


def _transcribe_local(file_path, model):
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(file_path, language=None)
    return result["text"]
