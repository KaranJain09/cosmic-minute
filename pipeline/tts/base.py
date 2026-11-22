from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float  # seconds, relative to the clip
    end: float


class TTSBackend:
    name = "base"
    ext = "mp3"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def synthesize(self, text: str, out_path: Path, voice: dict) -> list[Word]:
        """Write audio to out_path and return word timings."""
        raise NotImplementedError

    # --- caching: same text + voice -> reuse audio (keeps re-renders fast and deterministic)
    def cached(self, text: str, cache_dir: Path, voice: dict) -> tuple[Path, list[Word]]:
        key = hashlib.sha1(json.dumps([self.name, text, voice], sort_keys=True).encode()).hexdigest()[:16]
        cache_dir.mkdir(parents=True, exist_ok=True)
        audio = cache_dir / f"{key}.{self.ext}"
        meta = cache_dir / f"{key}.json"
        if audio.exists() and meta.exists() and audio.stat().st_size > 0:
            return audio, [Word(**w) for w in json.loads(meta.read_text(encoding="utf-8"))]
        words = self.synthesize(text, audio, voice)
        meta.write_text(json.dumps([asdict(w) for w in words]), encoding="utf-8")
        return audio, words


def align_to_script(text: str, words: list[Word]) -> list[Word]:
    """Swap engine word texts for the script's own tokens (keeps punctuation/casing) when counts match."""
    tokens = [t for t in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z0-9]", t)]
    if len(tokens) == len(words):
        return [Word(t, w.start, w.end) for t, w in zip(tokens, words)]
    return words


def estimate_words(text: str, total: float) -> list[Word]:
    """Fallback timings spread across `total` seconds, weighted by word length."""
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    weights = [max(2, len(t)) + (3 if t[-1] in ".,?!" else 0) for t in tokens]
    s = sum(weights) or 1
    out, t = [], 0.0
    for tok, wt in zip(tokens, weights):
        d = total * wt / s
        out.append(Word(tok, t, t + d * 0.9))
        t += d
    return out
