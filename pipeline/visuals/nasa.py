"""Real space imagery from the NASA Image and Video Library (images.nasa.gov). Free, no API key.
NASA media is generally not copyrighted; don't use NASA logos/insignia or imply NASA endorsement.

Scene fields:  visual.query  -> search text (e.g. "full moon", "Saturn rings Cassini")
               visual.nasa_id -> pin an exact image (set after checking preview_visuals.py)
               visual.fit     -> auto | cover | contain
Fallback chain: NASA -> Pexels video (if PEXELS_API_KEY) -> kinetic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from PIL import Image

import requests

from ..config import resolve
from .base import SceneCtx, VisualBackend
from .kenburns import image_motion, still_frames
from .kinetic import KineticBackend

API = "https://images-api.nasa.gov"
UA = {"User-Agent": "shorts-pipeline/0.2"}
BAD = re.compile(
    r"\b(press|conference|briefing|portrait|ceremony|award|meeting|logo|insignia|patch|poster|employee|"
    r"interview|panel|speaks|speech|visit|tour|students?|outreach|event|signing|chart|graph|plot|infographic)\b",
    re.I,
)
GOOD_CENTERS = {"JPL", "GSFC", "MSFC", "ARC", "JSC"}


def cache_dir(ctx_work: Path | None = None) -> Path:
    d = resolve("build") / "cache" / "nasa"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _score(item: dict, words: list[str]) -> float:
    d = (item.get("data") or [{}])[0]
    title = d.get("title", "")
    text = " ".join([title, " ".join(d.get("keywords", []) or []), d.get("description", "")[:400]]).lower()
    s = sum(2.0 for w in words if w in title.lower()) + sum(1.0 for w in words if w in text)
    if BAD.search(title) or BAD.search(" ".join(d.get("keywords", []) or [])):
        s -= 6
    if d.get("center") in GOOD_CENTERS:
        s += 1
    return s


def search(query: str, n: int = 8) -> list[dict]:
    """Return up to n ranked candidates: {nasa_id, title, preview}."""
    qcache = cache_dir() / "queries.json"
    store = json.loads(qcache.read_text(encoding="utf-8")) if qcache.exists() else {}
    key = query.strip().lower()
    if key in store:
        return store[key][:n]
    r = requests.get(f"{API}/search", params={"q": query, "media_type": "image", "page_size": 50},
                     headers=UA, timeout=30)
    r.raise_for_status()
    items = r.json().get("collection", {}).get("items", [])
    words = [w for w in re.findall(r"[a-z0-9]+", key) if len(w) > 2]
    ranked = sorted(enumerate(items), key=lambda t: (-_score(t[1], words), t[0]))
    out = []
    for _, it in ranked:
        d = (it.get("data") or [{}])[0]
        prev = next((l["href"] for l in it.get("links", []) if l.get("rel") == "preview"), None)
        if d.get("nasa_id") and prev:
            out.append({"nasa_id": d["nasa_id"], "title": d.get("title", ""), "preview": prev})
    store[key] = out[:12]
    qcache.write_text(json.dumps(store, indent=1), encoding="utf-8")
    return out[:n]


def download(nasa_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", nasa_id)
    for ext in (".jpg", ".png"):
        p = cache_dir() / f"{safe}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    r = requests.get(f"{API}/asset/{requests.utils.quote(nasa_id)}", headers=UA, timeout=30)
    r.raise_for_status()
    hrefs = [i["href"] for i in r.json().get("collection", {}).get("items", [])]
    pick = None
    for pref in ("~large.jpg", "~orig.jpg", "~large.png", "~orig.png", "~medium.jpg"):
        pick = next((h for h in hrefs if h.lower().endswith(pref)), None)
        if pick:
            break
    if not pick:
        raise RuntimeError(f"no jpg/png asset for {nasa_id}")
    pick = pick.replace("http://", "https://").replace(" ", "%20")
    out = cache_dir() / f"{safe}{Path(pick).suffix.lower()}"
    with requests.get(pick, headers=UA, timeout=120, stream=True) as dl:
        dl.raise_for_status()
        with open(out, "wb") as f:
            for chunk in dl.iter_content(1 << 20):
                f.write(chunk)
    return out


def resolve_scene_image(scene: dict) -> tuple[Path, str]:
    vis = scene.get("visual") or {}
    if vis.get("nasa_id"):
        return download(vis["nasa_id"]), vis["nasa_id"]
    q = vis.get("query") or vis.get("prompt") or "galaxy"
    last = None
    for c in search(q):
        try:
            return download(c["nasa_id"]), c["nasa_id"]
        except Exception as e:  # try the next candidate
            last = e
    raise RuntimeError(f"no NASA image for '{q}' ({last})")


class NasaBackend(VisualBackend):
    name = "nasa"

    def frames(self, ctx: SceneCtx) -> Iterator[Image.Image]:
        vis = ctx.scene.get("visual") or {}
        try:
            path, nid = resolve_scene_image(ctx.scene)
            print(f"  scene {ctx.scene['id']}: NASA {nid}")
        except Exception as e:
            print(f"  ! scene {ctx.scene['id']}: NASA lookup failed ({e})")
            from .stock import StockBackend

            yield from StockBackend().frames(ctx)
            return
        yield from still_frames(ctx, path, vis.get("fit", "auto"), image_motion(ctx))
