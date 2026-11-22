"""Optional premium voice. Needs ELEVENLABS_API_KEY in .env. Uses the with-timestamps endpoint for word timings."""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from ..config import env
from .base import TTSBackend, Word, align_to_script


class ElevenLabsTTS(TTSBackend):
    name = "elevenlabs"
    ext = "mp3"

    def synthesize(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        key = env("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("ELEVENLABS_API_KEY not set in .env (or switch tts.engine to 'edge')")
        c = self.cfg["elevenlabs"]
        vid = voice.get("voice_id") or c["voice_id"]
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": c.get("model_id", "eleven_multilingual_v2"),
                "voice_settings": {
                    "stability": c.get("stability", 0.45),
                    "similarity_boost": c.get("similarity_boost", 0.8),
                    "style": c.get("style", 0.3),
                },
            },
            timeout=120,
        )
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:400]}")
        data = r.json()
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        al = data.get("alignment") or data.get("normalized_alignment") or {}
        chars = al.get("characters", [])
        starts = al.get("character_start_times_seconds", [])
        ends = al.get("character_end_times_seconds", [])
        words: list[Word] = []
        cur, cs, ce = "", None, None
        for ch, s, e in zip(chars, starts, ends):
            if ch.isspace():
                if cur:
                    words.append(Word(cur, cs, ce))
                cur, cs = "", None
                continue
            if cs is None:
                cs = s
            cur += ch
            ce = e
        if cur:
            words.append(Word(cur, cs, ce))
        return align_to_script(text, words)
