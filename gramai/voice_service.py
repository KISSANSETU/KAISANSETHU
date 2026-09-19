"""Speech services for GRAM Saathi: Groq Whisper for speech-to-text, gTTS for
text-to-speech. Neither of these does any reasoning - Groq's chat pipeline in
chatbot_api.py remains the only LLM step. A transcribed message is handed to
that existing pipeline exactly like a typed one; this module only turns audio
into text and text into audio.
"""
from __future__ import annotations

import io
import os

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from gtts import gTTS
except Exception:  # pragma: no cover
    gTTS = None

from chatbot_api import LANG_NAMES

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_STT_MODEL = os.environ.get("GROQ_STT_MODEL", "whisper-large-v3").strip()

# gTTS wraps the public Google Translate voice endpoint - the same free,
# key-less provider style i18n_service.py already uses for text translation.
# Its Indic-language voice coverage is narrower than the 24 interface
# languages, so codes outside this map return a clear "unsupported" error
# instead of silently speaking English or failing oddly.
TTS_LANGS = {
    "en": "en", "hi": "hi", "mr": "mr", "ta": "ta", "te": "te", "bn": "bn",
    "gu": "gu", "kn": "kn", "ml": "ml", "pa": "pa", "ur": "ur", "ne": "ne",
}

# Whisper's verbose_json response names the detected language in English
# ("hindi", "marathi", ...) rather than as an ISO code.
_NAME_TO_CODE = {name.lower(): code for code, name in LANG_NAMES.items()}


class VoiceError(Exception):
    """User-facing voice failure - message is safe to show as-is."""


def _normalize_detected_lang(raw, hint):
    raw = (raw or "").strip().lower()
    if not raw:
        return hint or "en"
    if raw in LANG_NAMES:
        return raw
    return _NAME_TO_CODE.get(raw, hint or "en")


def transcribe(audio_bytes: bytes, filename: str, language_hint: str = None) -> dict:
    """Speech-to-text via Groq's Whisper endpoint. Returns {text, language}."""
    if not audio_bytes:
        raise VoiceError("The recording was empty")
    if not GROQ_API_KEY or not requests:
        raise VoiceError("Speech-to-text is not configured")

    files = {"file": (filename or "audio.webm", audio_bytes)}
    data = {"model": GROQ_STT_MODEL, "response_format": "verbose_json"}
    if language_hint and language_hint in LANG_NAMES:
        data["language"] = language_hint

    try:
        r = requests.post(
            GROQ_STT_URL,
            headers={"Authorization": "Bearer %s" % GROQ_API_KEY},
            files=files, data=data, timeout=60,
        )
    except Exception as e:
        raise VoiceError("Could not reach the speech service: %s" % e)

    if r.status_code != 200:
        raise VoiceError("Speech-to-text failed (%s)" % r.status_code)
    try:
        out = r.json()
    except Exception:
        raise VoiceError("Speech-to-text returned an invalid response")

    text = (out.get("text") or "").strip()
    if not text:
        raise VoiceError("No speech was recognised in the recording")

    lang = _normalize_detected_lang(out.get("language"), language_hint)
    return {"text": text, "language": lang}


def synthesize(text: str, lang: str) -> bytes:
    """Text-to-speech via gTTS. Returns MP3 bytes."""
    text = (text or "").strip()
    if not text:
        raise VoiceError("There is no answer to speak yet")
    if not gTTS:
        raise VoiceError("Text-to-speech is not configured")

    tl = TTS_LANGS.get((lang or "en").strip().lower())
    if not tl:
        raise VoiceError("Voice output is not available in this language yet")

    try:
        buf = io.BytesIO()
        gTTS(text=text[:1200], lang=tl).write_to_fp(buf)
        return buf.getvalue()
    except Exception as e:
        raise VoiceError("Could not generate speech: %s" % e)
