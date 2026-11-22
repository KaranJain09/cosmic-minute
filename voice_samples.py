#!/usr/bin/env python
"""Make one short sample per candidate voice so you can pick the most human-sounding one.

  uv run voice_samples.py            -> voice_samples/*.mp3 / *.wav

Then set your favourite in config.yaml:  tts.engine + tts.kokoro.voice (or tts.edge.voice).
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import load_config, resolve
from pipeline.tts import get_tts

TEXT = ("You just left Earth at the speed of light. One point three seconds later, you pass the Moon. "
        "And here's the strange part: it's slowly running away from us.")

CANDIDATES = [
    ("kokoro", "am_michael"), ("kokoro", "am_fenrir"), ("kokoro", "am_puck"), ("kokoro", "am_onyx"),
    ("kokoro", "bm_george"), ("kokoro", "bm_fable"), ("kokoro", "af_heart"), ("kokoro", "af_bella"),
    ("edge", "en-US-AndrewMultilingualNeural"), ("edge", "en-US-BrianMultilingualNeural"),
    ("edge", "en-US-AvaMultilingualNeural"), ("edge", "en-IN-PrabhatNeural"), ("edge", "en-IN-NeerjaNeural"),
]


def main() -> int:
    cfg = load_config()
    out = resolve("voice_samples")
    out.mkdir(exist_ok=True)
    for engine, vid in CANDIDATES:
        try:
            tts = get_tts(engine, cfg["tts"])
            voice = {"voice_id": vid}
            if engine == "edge":
                voice["rate"] = "+5%"
            dest = out / f"{engine}__{vid}.{tts.ext}"
            tts.synthesize(TEXT, dest, voice)
            print(f"✓ {dest.name}")
        except Exception as e:
            print(f"✗ {engine} {vid}: {str(e)[:200]}")
    print(f"\nListen to the files in {out} and tell Claude which one sounds best.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
