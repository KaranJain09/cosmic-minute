"""Optional stock footage from Pexels (free key: PEXELS_API_KEY). Cached; falls back to kinetic on any failure."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Iterator

import requests
from PIL import Image

from ..config import env, resolve
from ..ffmpeg import ffmpeg_exe
from .base import SceneCtx, VisualBackend
from .kinetic import KineticBackend


def _fetch_pexels(query: str, cache: Path) -> Path | None:
    key = env("PEXELS_API_KEY")
    if not key:
        return None
    cache.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(query.encode()).hexdigest()[:12]
    hit = cache / f"{tag}.mp4"
    if hit.exists():
        return hit
    r = requests.get(
        "https://api.pexels.com/v1/videos/search",
        params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 5},
        headers={"Authorization": key},
        timeout=30,
    )
    r.raise_for_status()
    for v in r.json().get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("height", 0) >= 1280 and f.get("file_type") == "video/mp4"]
        files.sort(key=lambda f: abs(f.get("height", 0) - 1920))
        if files:
            with requests.get(files[0]["link"], stream=True, timeout=120) as dl:
                dl.raise_for_status()
                with open(hit, "wb") as f:
                    for chunk in dl.iter_content(1 << 20):
                        f.write(chunk)
            return hit
    return None


class StockBackend(VisualBackend):
    name = "stock"

    def frames(self, ctx: SceneCtx) -> Iterator[Image.Image]:
        vis = ctx.scene.get("visual") or {}
        src = vis.get("clip")
        path = resolve(src) if src else None
        if not path or not path.exists():
            try:
                path = _fetch_pexels(vis.get("query") or vis.get("prompt", "space"), ctx.work.parent / "cache" / "stock")
            except Exception as e:
                print(f"  ! scene {ctx.scene['id']}: stock fetch failed ({e})")
                path = None
        if not path:
            print(f"  ! scene {ctx.scene['id']}: no stock clip, using kinetic")
            yield from KineticBackend().frames(ctx)
            return
        vf = (f"scale={ctx.w}:{ctx.h}:force_original_aspect_ratio=increase,crop={ctx.w}:{ctx.h},"
              f"fps={ctx.fps},eq=brightness=-0.08:saturation=1.1")
        cmd = [ffmpeg_exe(), "-v", "error", "-stream_loop", "-1", "-i", str(path), "-t", f"{ctx.duration + 0.5:.3f}",
               "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        size = ctx.w * ctx.h * 3
        last = None
        try:
            for _ in range(ctx.n_frames):
                buf = proc.stdout.read(size) if proc.stdout else b""
                if len(buf) == size:
                    last = Image.frombytes("RGB", (ctx.w, ctx.h), buf)
                if last is None:
                    last = Image.new("RGB", (ctx.w, ctx.h))
                yield last.copy()
        finally:
            proc.kill()
            proc.wait()
