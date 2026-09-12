"""Voice endpoints for GRAM Saathi.

Speech-to-text and text-to-speech only - no reasoning happens here. The
frontend sends the transcript from /transcribe into the existing /api/ai
chat pipeline exactly like a typed message, then sends that pipeline's
answer to /speak. This router never talks to Groq's chat/completions
endpoint; voice_service.py only calls Groq's separate audio endpoint (STT)
and gTTS (TTS).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional

from voice_service import transcribe, synthesize, VoiceError

router = APIRouter(prefix="/api/voice", tags=["GRAM Saathi Voice"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


def get_user_dep():
    # Late import mirrors chatbot_api and avoids a circular import.
    from app import user
    return user


@router.post("/transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    u=Depends(get_user_dep()),
):
    data = await audio.read()
    if not data:
        raise HTTPException(400, "No audio was received")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(400, "Recording is too large (max 10 MB)")
    try:
        return transcribe(data, audio.filename or "audio.webm", language)
    except VoiceError as e:
        raise HTTPException(400, str(e))


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    lang: str = Field(default="en", max_length=12)


@router.post("/speak")
def voice_speak(body: SpeakIn, u=Depends(get_user_dep())):
    try:
        audio = synthesize(body.text, body.lang)
    except VoiceError as e:
        raise HTTPException(400, str(e))
    return Response(content=audio, media_type="audio/mpeg",
                     headers={"Cache-Control": "no-store"})
