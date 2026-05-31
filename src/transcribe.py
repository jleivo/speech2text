import logging

import litellm
import whisper

logger = logging.getLogger(__name__)


def transcribe_audio(file_path, backend="litellm", model="whisper-1", litellm_base_url=None):
    if backend == "litellm":
        try:
            return _transcribe_litellm(file_path, model, litellm_base_url)
        except Exception as e:
            logger.warning("LiteLLM failed (%s), falling back to local Whisper", e)
            return _transcribe_local(file_path, model="turbo")
    else:
        return _transcribe_local(file_path, model)


def _transcribe_litellm(file_path, model, litellm_base_url=None):
    kwargs = {"model": model, "file": open(file_path, "rb")}
    if litellm_base_url:
        kwargs["api_base"] = litellm_base_url
    try:
        response = litellm.transcription(**kwargs)
    finally:
        kwargs["file"].close()
    return response.text


def _transcribe_local(file_path, model):
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(file_path, language=None)
    return result["text"]
