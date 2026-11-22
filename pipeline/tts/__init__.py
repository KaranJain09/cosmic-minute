from __future__ import annotations

from .base import TTSBackend, Word


def get_tts(engine: str, cfg: dict) -> TTSBackend:
    if engine == "edge":
        from .edge import EdgeTTS

        return EdgeTTS(cfg)
    if engine == "elevenlabs":
        from .elevenlabs import ElevenLabsTTS

        return ElevenLabsTTS(cfg)
    if engine == "kokoro":
        from .kokoro_tts import KokoroTTS

        return KokoroTTS(cfg)
    if engine == "dummy":
        from .dummy import DummyTTS

        return DummyTTS(cfg)
    raise ValueError(f"unknown tts engine '{engine}' (kokoro | edge | elevenlabs | dummy)")


__all__ = ["get_tts", "TTSBackend", "Word"]
