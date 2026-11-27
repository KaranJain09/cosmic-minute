"""Optional premium voice. Needs ELEVENLABS_API_KEY in .env. Uses the with-timestamps endpoint for word timings."""
from __future__ import annotations

import base64
import time
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
        settings = {k: c[k] for k in ("stability", "similarity_boost", "style") if k in c}
        body = {"text": text, "model_id": c.get("model_id", "eleven_multilingual_v2")}
        if settings:
            body["voice_settings"] = settings
        r = None
        for attempt in range(3):
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=120,
            )
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(3 * (attempt + 1))
        if r.status_code != 200:  # 401 bad key, 402/quota: out of credits -> render falls back to the free voice
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
