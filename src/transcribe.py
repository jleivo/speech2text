import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import litellm
import whisper

logger = logging.getLogger(__name__)

# Module-level Whisper model cache (_cache_lock protects _whisper_cache)
_whisper_cache: dict = {}
_cache_lock = threading.Lock()


def _get_whisper_model(model_name):
    if model_name not in _whisper_cache:
        with _cache_lock:
            if model_name not in _whisper_cache:
                _whisper_cache[model_name] = whisper.load_model(model_name)
    return _whisper_cache[model_name]


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
    # LiteLLM requires a provider prefix (e.g. "openai/model-name").
    # When talking to an OpenAI-compatible endpoint (LiteLLM proxy),
    # auto-prefix with "openai/" if no provider is specified.
    if "/" not in model:
        model = f"openai/{model}"
    with open(file_path, "rb") as audio_file:
        response = litellm.transcription(model=model, file=audio_file, timeout=60)
    return response.text


def _transcribe_local(file_path, model, timeout=300):
    whisper_model = _get_whisper_model(model)

    def _run():
        return whisper_model.transcribe(file_path, language=None)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        result = future.result(timeout=timeout)

    return result["text"]
