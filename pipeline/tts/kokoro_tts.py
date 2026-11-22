"""Kokoro-82M: free, open-source (Apache 2.0), runs locally on CPU, very natural voices, word timestamps.
First run downloads the model (~330 MB) from Hugging Face; after that it works offline."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..ffmpeg import write_wav
from .base import TTSBackend, Word, align_to_script, estimate_words

_PIPES: dict[str, object] = {}


def _pipeline(lang: str):
    if lang not in _PIPES:
        from kokoro import KPipeline

        _PIPES[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    return _PIPES[lang]


class KokoroTTS(TTSBackend):
    name = "kokoro"
    ext = "wav"
    SR = 24000

    def synthesize(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        c = self.cfg.get("kokoro", {})
        vid = voice.get("voice_id") or c.get("voice", "am_michael")
        speed = float(voice.get("speed") or c.get("speed", 1.05))
        lang = vid[0] if vid[0] in "abefhijpz" else "a"  # a=US English, b=UK English
        pipe = _pipeline(lang)
        chunks, words, offset = [], [], 0.0
        for res in pipe(text, voice=vid, speed=speed, split_pattern=None):
            audio = res.audio
            if audio is None:
                continue
            a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
            a = a.astype(np.float32).reshape(-1)
            for t in res.tokens or []:
                st, en = getattr(t, "start_ts", None), getattr(t, "end_ts", None)
                if st is None or en is None or not any(ch.isalnum() for ch in t.text):
                    continue
                words.append(Word(t.text, offset + float(st), offset + float(en)))
            chunks.append(a)
            offset += len(a) / self.SR
        if not chunks:
            raise RuntimeError(f"kokoro produced no audio for: {text[:60]}")
        audio = np.concatenate(chunks)
        write_wav(out_path, audio, self.SR)
        if not words:
            words = estimate_words(text, len(audio) / self.SR)
        return align_to_script(text, words)
