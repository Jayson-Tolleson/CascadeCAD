from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class SttConfig:
    mime_type: str = "audio/webm;codecs=opus"
    language_code: str = "en-US"


class SttUnavailable(RuntimeError):
    pass


def _encoding_for_mime(mime_type: str, speech: Any):
    lower = (mime_type or "").lower()
    enc = speech.RecognitionConfig.AudioEncoding
    if "ogg" in lower:
        return enc.OGG_OPUS
    if "webm" in lower:
        return enc.WEBM_OPUS
    return enc.ENCODING_UNSPECIFIED


def provider_status() -> dict:
    settings = get_settings()
    try:
        import google.cloud.speech  # noqa: F401
        dependency = True
    except Exception:
        dependency = False
    return {
        "enabled": settings.stt_enabled,
        "provider": settings.stt_provider,
        "language_code": settings.stt_language_code,
        "google_cloud_speech_dependency": dependency,
        "chunk_seconds": settings.stt_chunk_seconds,
    }


def transcribe_audio_chunk(audio: bytes, cfg: SttConfig) -> str:
    settings = get_settings()
    if not settings.stt_enabled:
        raise SttUnavailable("server STT disabled")
    if len(audio) < 800:
        return ""
    provider = settings.stt_provider.strip().lower()
    if provider not in {"google", "google_cloud", "auto"}:
        raise SttUnavailable(f"server STT provider {settings.stt_provider!r} not supported")
    try:
        from google.cloud import speech
    except Exception as exc:  # pragma: no cover - depends on optional cloud package
        raise SttUnavailable("google-cloud-speech is not installed") from exc

    client = speech.SpeechClient()
    config_kwargs: dict[str, Any] = {
        "encoding": _encoding_for_mime(cfg.mime_type, speech),
        "language_code": cfg.language_code or settings.stt_language_code,
        "enable_automatic_punctuation": True,
        "model": settings.stt_model,
    }
    if "opus" in (cfg.mime_type or "").lower():
        config_kwargs["sample_rate_hertz"] = settings.stt_sample_rate_hz
    config = speech.RecognitionConfig(**config_kwargs)
    response = client.recognize(config=config, audio=speech.RecognitionAudio(content=audio))
    parts: list[str] = []
    for result in response.results:
        if result.alternatives:
            text = result.alternatives[0].transcript.strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()
