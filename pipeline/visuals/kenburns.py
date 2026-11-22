"""Cinematic still image (NASA / your own / AI / stock photo) with slow zoom or pan. Falls back to kinetic.

fit = "cover"   -> image fills the 9:16 frame (crops the sides of landscape photos)
fit = "contain" -> whole image shown, centered, over a blurred + darkened copy of itself (best for full planets,
                   wide nebula shots, diagrams)
fit = "auto"    -> contain for very wide images (aspect > 1.4), else cover
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from ..config import resolve
from .base import SceneCtx, VisualBackend
from .common import ease_in_out
from .kinetic import KineticBackend

Image.MAX_IMAGE_PIXELS = None
MARGIN = 1.18  # canvas is 18% larger than the frame so the camera can move


def _grade(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.12)
    return ImageEnhance.Brightness(img).enhance(0.9)


def _vignette(w: int, h: int) -> Image.Image:
    yy = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    v = np.clip(xx**2 * 0.8 + yy**2 * 0.45, 0, 1) ** 1.3
    return Image.fromarray((v * 200).astype(np.uint8), "L")


def build_canvas(src: Image.Image, w: int, h: int, fit: str) -> Image.Image:
    src = src.convert("RGB")
    cw, ch = int(w * MARGIN), int(h * MARGIN)
    aspect = src.width / src.height
    if fit == "auto":
        fit = "contain" if aspect > 1.4 else "cover"
    if fit == "contain":
        k = max(cw / src.width, ch / src.height)
        bg = src.resize((max(1, int(src.width * k / 8)), max(1, int(src.height * k / 8))), Image.BILINEAR)
        bg = bg.filter(ImageFilter.GaussianBlur(6)).resize((int(src.width * k) + 1, int(src.height * k) + 1), Image.BICUBIC)
        bg = ImageEnhance.Brightness(bg).enhance(0.45)
        left, top = (bg.width - cw) // 2, (bg.height - ch) // 2
        canvas = bg.crop((left, top, left + cw, top + ch))
        # foreground: fit to ~96% of frame width (wide images) or 70% of frame height (tall images)
        kf = min(w * 0.96 / src.width, h * 0.70 / src.height)
        fg = _grade(src.resize((max(1, int(src.width * kf)), max(1, int(src.height * kf))), Image.LANCZOS))
        sh = Image.new("L", (fg.width + 80, fg.height + 80), 0)
        sh.paste(255, (40, 40, 40 + fg.width, 40 + fg.height))
        sh = sh.filter(ImageFilter.GaussianBlur(25))
        cx, cy = (cw - fg.width) // 2, int(ch * 0.50 - fg.height / 2)
        canvas.paste((0, 0, 0), (cx - 40, cy - 40), sh)
        canvas.paste(fg, (cx, cy))
    else:
        k = max(cw / src.width, ch / src.height)
        img = src.resize((int(src.width * k) + 1, int(src.height * k) + 1), Image.LANCZOS)
        left, top = (img.width - cw) // 2, (img.height - ch) // 2
        canvas = _grade(img.crop((left, top, left + cw, top + ch)))
    canvas.paste((0, 0, 0), (0, 0), _vignette(cw, ch))
    return canvas


IMAGE_MOTIONS = {"zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up"}


def image_motion(ctx: SceneCtx) -> str | None:
    vis = ctx.scene.get("visual") or {}
    m = vis.get("camera")
    return m if m in IMAGE_MOTIONS else None


def still_frames(ctx: SceneCtx, path: Path, fit: str = "auto", motion: str | None = None) -> Iterator[Image.Image]:
    canvas = build_canvas(Image.open(path), ctx.w, ctx.h, fit)
    CW, CH = canvas.size
    motion = motion or ("zoom_in", "pan_right", "zoom_out", "pan_left")[ctx.index % 4]
    n = ctx.n_frames
    for i in range(n):
        p = ease_in_out(i / max(1, n - 1))
        # zf=1.0 shows the whole canvas; zf=MARGIN shows exactly one frame of pixels
        if motion == "zoom_out":
            zf = 1.16 - 0.15 * p
        elif motion in ("pan_left", "pan_right", "pan_up"):
            zf = 1.10
        else:
            zf = 1.01 + 0.15 * p
        cw, ch = min(ctx.w * MARGIN / zf, CW), min(ctx.h * MARGIN / zf, CH)
        cx, cy = CW / 2, CH / 2
        if motion == "pan_left":
            cx = CW - cw / 2 - (CW - cw) * p
        elif motion == "pan_right":
            cx = cw / 2 + (CW - cw) * p
        elif motion == "pan_up":
            cy = CH - ch / 2 - (CH - ch) * p
        yield canvas.resize((ctx.w, ctx.h), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))


class KenBurnsBackend(VisualBackend):
    name = "kenburns"

    def frames(self, ctx: SceneCtx) -> Iterator[Image.Image]:
        vis = ctx.scene.get("visual") or {}
        path = vis.get("image")
        if not path or not resolve(path).exists():
            print(f"  ! scene {ctx.scene['id']}: image '{path}' not found, using kinetic")
            yield from KineticBackend().frames(ctx)
            return
        yield from still_frames(ctx, resolve(path), vis.get("fit", "auto"), image_motion(ctx))
