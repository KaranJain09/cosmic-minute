"""Script markup for the spoken line.

  [excited] [whispers] [laughs] ...  ElevenLabs v3 emotion tags (inside `speech`). Removed for other voices.
  {{word}}                           a gaali: the voice says it, a beep covers that exact word,
                                     and the caption shows a symbol string instead.
"""
from __future__ import annotations

import re

import numpy as np

TAG_RE = re.compile(r"\[[A-Za-z][A-Za-z \-']{1,30}\]")
BLEEP_RE = re.compile(r"\{\{([^{}]+)\}\}")
BLEEP_CAPTION = "#@$%!"


def spoken_text(text: str, keep_tags: bool) -> tuple[str, set[int]]:
    """Return (text to send to the voice, indices of words to bleep among the non-tag words)."""
    if not keep_tags:
        text = TAG_RE.sub(" ", text)
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    out, bleeps, idx = [], set(), 0
    for t in tokens:
        if TAG_RE.fullmatch(t.strip(".,!?")):
            out.append(t)
            continue
        if BLEEP_RE.search(t):
            bleeps.add(idx)
            t = BLEEP_RE.sub(lambda m: m.group(1), t)
        out.append(t)
        idx += 1
    return " ".join(out), bleeps


def caption_text(text: str) -> str:
    """Narration as shown on screen: no emotion tags, gaali replaced by symbols."""
    text = TAG_RE.sub(" ", text)
    text = BLEEP_RE.sub(BLEEP_CAPTION, text)
    return re.sub(r"\s+", " ", text).strip()


def drop_tag_words(words: list) -> list:
    """Remove timing entries the engine produced for emotion tags."""
    return [w for w in words if not TAG_RE.fullmatch(w.text.strip(".,!?"))]


def apply_bleeps(a: np.ndarray, sr: int, words: list, bleeps: set[int], freq: float = 1000.0) -> np.ndarray:
    """Replace the bleeped words' audio with a classic TV beep at a matching loudness."""
    if not bleeps:
        return a
    a = a.copy()
    level = float(np.sqrt(np.mean(a**2)) * 1.6) if len(a) else 0.2
    level = min(max(level, 0.12), 0.35)
    for i in sorted(bleeps):
        if i >= len(words):
            continue
        s = max(0, int((words[i].start - 0.03) * sr))
        e = min(len(a), int((words[i].end + 0.05) * sr))
        if e <= s:
            continue
        n = e - s
        t = np.arange(n) / sr
        tone = level * np.sin(2 * np.pi * freq * t)
        f = min(n // 2, int(0.006 * sr))
        if f > 0:
            ramp = np.linspace(0, 1, f)
            tone[:f] *= ramp
            tone[-f:] *= ramp[::-1]
        a[s:e] = tone.astype(a.dtype)
    return a
