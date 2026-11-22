#!/usr/bin/env python
"""Render one episode script to ./upload videos/.

  uv run build_video.py --script scripts/episode_1.json
  uv run build_video.py --script scripts/episode_1.json --validate-only
  uv run build_video.py --script scripts/episode_1.json --force          # overwrite existing output
  uv run build_video.py --script scripts/episode_1.json --tts dummy      # offline test voice
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import load_config, resolve
from pipeline.render import BuildError, build, clean


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic short-video renderer")
    ap.add_argument("--script", required=True, help="path to scripts/episode_X.json")
    ap.add_argument("--config", default=None, help="config.yaml path")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output video")
    ap.add_argument("--validate-only", action="store_true", help="check the script and exit")
    ap.add_argument("--tts", choices=["kokoro", "edge", "elevenlabs", "dummy"], help="override voice engine")
    ap.add_argument("--keep-build", action="store_true", help="keep build/ep_XXX temp files")
    a = ap.parse_args()

    cfg = load_config(Path(a.config) if a.config else None)
    script = Path(a.script)
    if not script.is_absolute() and not script.exists():
        script = resolve(a.script)
    if not script.exists():
        print(f"✗ script not found: {a.script}")
        return 2
    try:
        out = build(script, cfg, force=a.force, tts_override=a.tts, validate_only=a.validate_only)
    except BuildError as e:
        print(f"✗ {e}")
        return 1
    if out and not a.keep_build:
        import json

        clean(cfg, json.loads(script.read_text(encoding="utf-8"))["episode_number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
