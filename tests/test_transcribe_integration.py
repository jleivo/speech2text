import os
import pytest
import requests
from src.transcribe import transcribe_audio

LITELLM_BASE_URL = os.environ.get(
    "LITELLM_BASE_URL", "http://tuprpisrvp02.intra.leivo:4000"
)
LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "whisper-1")


def _server_available():
    try:
        requests.get(f"{LITELLM_BASE_URL}/health", timeout=3)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


skip_no_server = pytest.mark.skipif(
    not _server_available(),
    reason=f"LiteLLM server not available at {LITELLM_BASE_URL}",
)


@skip_no_server
def test_transcribe_voice_001():
    """Transcribe Finnish test audio file 001 via LiteLLM."""
    os.environ.setdefault("OPENAI_API_BASE", LITELLM_BASE_URL)

    audio_path = os.path.join(
        os.path.dirname(__file__), "audio", "Voice 001_W_20250624_111642.m4a"
    )
    result = transcribe_audio(audio_path, backend="litellm", model=LITELLM_MODEL)

    assert "testitallennus" in result.lower()


@skip_no_server
def test_transcribe_voice_002():
    """Transcribe Finnish test audio file 002 via LiteLLM."""
    os.environ.setdefault("OPENAI_API_BASE", LITELLM_BASE_URL)

    audio_path = os.path.join(
        os.path.dirname(__file__), "audio", "Voice 002_W_20250624_111750.m4a"
    )
    result = transcribe_audio(audio_path, backend="litellm", model=LITELLM_MODEL)

    assert "testitallennus" in result.lower()
