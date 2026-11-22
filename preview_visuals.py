#!/usr/bin/env python
"""Show the NASA image candidates for every scene of an episode as one contact sheet.

  uv run preview_visuals.py --script scripts/episode_2.json

Writes build/preview/ep_XXX_visuals.jpg. Row = scene, columns = candidates (first = what the renderer uses).
To lock a different picture, put its id into that scene's  "visual": {"nasa_id": "..."}  in the episode JSON.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import load_config, resolve
from pipeline.visuals.common import font
from pipeline.visuals.nasa import UA, search

TW, TH = 300, 220


def thumb(url: str) -> Image.Image:
    try:
        r = requests.get(url.replace(" ", "%20"), headers=UA, timeout=30)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((TW, TH))
        return im
    except Exception:
        return Image.new("RGB", (TW, TH), (60, 0, 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("-n", type=int, default=4, help="candidates per scene")
    a = ap.parse_args()
    cfg = load_config()
    ep = json.loads(Path(a.script).read_text(encoding="utf-8"))
    default = cfg["visuals"]["default_backend"]
    rows = []
    for s in ep["scenes"]:
        vis = s.get("visual") or {}
        if (vis.get("backend") or default) != "nasa":
            continue
        q = vis.get("query") or vis.get("prompt") or ""
        cands = search(q, a.n) if q else []
        if vis.get("nasa_id"):
            cands = [{"nasa_id": vis["nasa_id"], "title": "(pinned)", "preview":
                      f"https://images-assets.nasa.gov/image/{vis['nasa_id']}/{vis['nasa_id']}~thumb.jpg"}] + cands
        print(f"scene {s['id']:>2}  q='{q}'")
        for i, c in enumerate(cands[: a.n]):
            print(f"    [{i}] {c['nasa_id']:<32} {c['title'][:70]}")
        rows.append((s, q, cands[: a.n]))
    if not rows:
        print("no nasa scenes")
        return 0
    lab = 46
    sheet = Image.new("RGB", (TW * a.n, (TH + lab) * len(rows)), (15, 15, 20))
    d = ImageDraw.Draw(sheet)
    f = font(cfg["fonts"]["ui"], 16)
    for r, (s, q, cands) in enumerate(rows):
        y = r * (TH + lab)
        for i, c in enumerate(cands):
            im = thumb(c["preview"])
            sheet.paste(im, (i * TW + (TW - im.width) // 2, y + lab + (TH - im.height) // 2))
            d.text((i * TW + 6, y + 24), f"[{i}] {c['nasa_id'][:30]}", font=f, fill=(255, 212, 0) if i == 0 else (200, 200, 200))
        d.text((6, y + 4), f"SCENE {s['id']}: {q[:60]}", font=f, fill=(79, 195, 247))
    out = resolve("build") / "preview" / f"ep_{int(ep['episode_number']):03d}_visuals.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    print(f"✓ contact sheet: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
