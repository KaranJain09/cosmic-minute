"""Default voice: Microsoft Edge neural TTS via edge-tts (free, no key, word-level timings)."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from .base import TTSBackend, Word, align_to_script


class EdgeTTS(TTSBackend):
    name = "edge"
    ext = "mp3"

    def synthesize(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        last = None
        for attempt in range(4):
            try:
                words = asyncio.run(self._run(text, out_path, voice))
                if out_path.exists() and out_path.stat().st_size > 0:
                    return align_to_script(text, words)
                raise RuntimeError("edge-tts returned no audio")
            except Exception as e:  # network hiccups are common; retry with backoff
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"edge-tts failed after retries: {last}")

    async def _run(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        import edge_tts

        kw = dict(
            voice=voice.get("voice_id") or self.cfg["edge"]["voice"],
            rate=voice.get("rate") or self.cfg["edge"].get("rate", "+0%"),
            pitch=voice.get("pitch") or self.cfg["edge"].get("pitch", "+0Hz"),
            volume=voice.get("volume") or self.cfg["edge"].get("volume", "+0%"),
        )
        try:  # edge-tts >= 7 defaults to sentence boundaries; ask for words
            comm = edge_tts.Communicate(text, boundary="WordBoundary", **kw)
        except TypeError:
            comm = edge_tts.Communicate(text, **kw)
        words: list[Word] = []
        with open(out_path, "wb") as f:
            async for ch in comm.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    words.append(Word(ch["text"], s, s + ch["duration"] / 1e7))
        return words
