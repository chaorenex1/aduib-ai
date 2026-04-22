"""ASR (Audio Speech Recognition) entities."""

from typing import Optional

from pydantic import BaseModel, Field


class ASRRequest(BaseModel):
    """ASR Request entity for speech-to-text conversion."""

    model: str = Field(description="ASR model name (e.g., 'whisper-1')")
    file: bytes = Field(description="Binary audio content")
    language: Optional[str] = Field(default=None, description="Language code (e.g., 'en', 'zh')")
    prompt: Optional[str] = Field(default=None, description="Optional prompt to guide the model")
    response_format: Optional[str] = Field(default="json", description="Response format (json, text, srt, verbose_json)")
    temperature: Optional[float] = Field(default=0.0, description="Sampling temperature (0.0 to 1.0)")
    format: Optional[str] = Field(default="mp3", description="Audio format (mp3, mp4, mpeg, mpga, m4a, wav, webm, flac)")
    user: Optional[str] = Field(default=None, description="Unique user identifier")


class ASRResponse(BaseModel):
    """ASR Response entity containing the transcription."""

    model: str = Field(description="Model used for transcription")
    text: str = Field(description="Transcribed text")
    duration: Optional[float] = Field(default=None, description="Audio duration in seconds")
    language: Optional[str] = Field(default=None, description="Detected language code")


__all__ = ["ASRRequest", "ASRResponse"]
