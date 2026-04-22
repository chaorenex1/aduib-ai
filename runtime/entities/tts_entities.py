from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TTSVoice(BaseModel):
    """TTS Voice entity representing a voice option."""

    voice_id: str = Field(description="Unique identifier for the voice")
    name: str = Field(description="Human-readable name of the voice")
    language: Optional[str] = Field(default=None, description="Primary language code (e.g., 'en-US')")
    gender: Optional[str] = Field(default=None, description="Gender of the voice (e.g., 'female', 'male')")


class TTSRequest(BaseModel):
    """TTS Request entity for text-to-speech conversion."""

    model: str = Field(description="TTS model name (e.g., 'tts-1', 'tts-1-hd')")
    input: str = Field(description="Text content to be converted to speech", max_length=10000)
    voice: str = Field(description="Voice ID to use for synthesis (e.g., 'alloy', 'echo', 'fable')")
    response_format: Literal["mp3", "opus", "aac", "flac"] = Field(
        default="mp3", description="Audio format (mp3, opus, aac, flac)"
    )
    speed: Optional[float] = Field(default=1.0, description="Speech speed (0.25 to 4.0)")
    user: Optional[str] = Field(default=None, description="Unique user identifier")

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.25 or v > 4.0):
            raise ValueError("speed must be between 0.25 and 4.0")
        return v


class TTSResponse(BaseModel):
    """TTS Response entity containing the audio content."""

    model: str = Field(description="Model used for synthesis")
    audio_data: bytes = Field(description="Binary audio content")
    duration: Optional[float] = Field(default=None, description="Audio duration in seconds")


__all__ = ["TTSRequest", "TTSResponse", "TTSVoice"]
