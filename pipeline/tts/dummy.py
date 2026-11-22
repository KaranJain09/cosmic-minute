"""Offline test voice: a soft blip per word at ~165 wpm. For pipeline tests only, never for uploads."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..ffmpeg import write_wav
from .base import TTSBackend, Word, estimate_words


class DummyTTS(TTSBackend):
    name = "dummy"
    ext = "wav"

    def synthesize(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        sr = 48000
        n_words = len(text.split())
        total = n_words * 0.36 + 0.1
        words = estimate_words(text, total)
        audio = np.zeros(int(total * sr), dtype=np.float32)
        for w in words:
            i = int(w.start * sr)
            n = min(int(0.12 * sr), len(audio) - i)
            t = np.arange(n) / sr
            audio[i : i + n] += 0.25 * np.sin(2 * np.pi * 330 * t) * np.hanning(n)
        write_wav(out_path, audio, sr)
        return words
