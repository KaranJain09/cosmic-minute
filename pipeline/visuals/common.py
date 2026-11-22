"""Shared drawing helpers: fonts, rich text blocks, space backgrounds, decor sprites, easing."""
from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import hex_rgb, resolve

FALLBACK_FONTS = [
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/seguibl.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


# ---------------------------------------------------------------- easing
def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def ease_out_cubic(x: float) -> float:
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x: float, s: float = 1.70158) -> float:
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_in_out(x: float) -> float:
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


# ---------------------------------------------------------------- fonts
@lru_cache(maxsize=512)
def _font(path: str, size: int, variation: str | None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def font(spec: dict, size: int) -> ImageFont.FreeTypeFont:
    candidates = [str(resolve(spec["file"]))] + FALLBACK_FONTS
    for c in candidates:
        if Path(c).exists():
            return _font(c, int(size), spec.get("variation"))
    return ImageFont.load_default(size=int(size))


# ---------------------------------------------------------------- rich text
def parse_rich(text: str) -> list[tuple[str, bool]]:
    """'the *4.6 billion* year clock' -> [(the,F),(4.6,T),(billion,T),(year,F),(clock,F)]"""
    out, hl = [], False
    for tok in text.split():
        word = tok.replace("*", "")
        cur = hl
        if tok.startswith("*"):
            cur = True
        stars = tok.count("*")
        # an odd number of stars toggles state for following tokens
        if stars % 2 == 1:
            hl = not hl
        if word:
            out.append((word, cur or (stars >= 2)))
    return out


def render_rich(
    text: str,
    fspec: dict,
    size: int,
    max_w: int,
    *,
    max_lines: int = 3,
    fill=(255, 255, 255),
    accent=(255, 212, 0),
    stroke: int = 8,
    stroke_fill=(0, 0, 0),
    uppercase: bool = True,
    line_gap: float = 0.02,
    shadow: bool = True,
) -> Image.Image:
    words = [(w.upper() if uppercase else w, h) for w, h in parse_rich(text)]
    if not words:
        return Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    sz = size
    while True:
        f = font(fspec, sz)
        space = f.getlength(" ")
        lines: list[list[tuple[str, bool, float]]] = [[]]
        lw = 0.0
        for w, h in words:
            wl = f.getlength(w)
            if lines[-1] and lw + space + wl > max_w:
                lines.append([])
                lw = 0.0
            lw += (space if lines[-1] else 0) + wl
            lines[-1].append((w, h, wl))
        widest = max(sum(x[2] for x in ln) + space * (len(ln) - 1) for ln in lines)
        if (len(lines) <= max_lines and widest <= max_w) or sz <= 28:
            break
        sz = int(sz * 0.92)
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * (1 + line_gap))
    pad = stroke + 18
    W = int(widest) + pad * 2
    H = lh * len(lines) + pad * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for li, ln in enumerate(lines):
        lwid = sum(x[2] for x in ln) + space * (len(ln) - 1)
        x = (W - lwid) / 2
        y = pad + li * lh
        for w, h, wl in ln:
            d.text((x, y), w, font=f, fill=accent if h else fill, stroke_width=stroke, stroke_fill=stroke_fill)
            x += wl + space
    if shadow:
        a = img.split()[3].filter(ImageFilter.GaussianBlur(10))
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.6)))
        sh.alpha_composite(img)
        return sh
    return img


def pill(text: str, fspec: dict, size: int, bg, fg, pad_x: int = 36, pad_y: int = 18) -> Image.Image:
    f = font(fspec, size)
    l, t, r, b = f.getbbox(text)
    W, H = int(r - l + pad_x * 2), int(b - t + pad_y * 2)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2, fill=bg)
    d.text((pad_x - l, pad_y - t), text, font=f, fill=fg)
    return img


def scaled(img: Image.Image, s: float) -> Image.Image:
    if abs(s - 1) < 1e-3:
        return img
    w, h = max(1, int(img.width * s)), max(1, int(img.height * s))
    return img.resize((w, h), Image.BILINEAR)


def paste_center(canvas: Image.Image, layer: Image.Image, cx: float, cy: float, alpha: float = 1.0) -> None:
    if alpha <= 0.01:
        return
    if alpha < 0.999:
        layer = layer.copy()
        layer.putalpha(layer.split()[3].point(lambda v: int(v * alpha)))
    canvas.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


# ---------------------------------------------------------------- backgrounds
def space_background(w: int, h: int, palette: dict, seed: int, extra_h: int = 360) -> Image.Image:
    """Tall RGB image: vertical gradient + blurred nebula clouds + starfield + vignette. Scroll it for drift."""
    rng = np.random.default_rng(seed)
    H = h + extra_h
    top = np.array(hex_rgb(palette["bg_top"]), dtype=np.float32)
    bot = np.array(hex_rgb(palette["bg_bottom"]), dtype=np.float32)
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.broadcast_to(top * (1 - t) + bot * t, (H, w, 3)).copy()

    # nebula at 1/6 resolution, blurred, then upscaled
    sw, sh = w // 6, H // 6
    neb = Image.new("RGB", (sw, sh), (0, 0, 0))
    nd = ImageDraw.Draw(neb)
    cols = palette.get("nebula", ["#3B1E8C"])
    for _ in range(6):
        c = hex_rgb(cols[int(rng.integers(len(cols)))])
        cx, cy = rng.uniform(0, sw), rng.uniform(0, sh)
        rx, ry = rng.uniform(sw * 0.2, sw * 0.6), rng.uniform(sh * 0.08, sh * 0.25)
        k = rng.uniform(0.35, 0.8)
        nd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=tuple(int(v * k) for v in c))
    neb = neb.filter(ImageFilter.GaussianBlur(sw * 0.12)).resize((w, H), Image.BICUBIC)
    arr += np.asarray(neb, dtype=np.float32) * 0.9

    # stars
    n = int(w * H / 3500)
    xs, ys = rng.integers(0, w, n), rng.integers(0, H, n)
    br = rng.power(4, n) * 255
    arr[ys, xs] = np.maximum(arr[ys, xs], br[:, None])
    big = rng.choice(n, n // 25, replace=False)
    for dx, dy in ((1, 0), (0, 1), (1, 1)):
        yy, xx = np.clip(ys[big] + dy, 0, H - 1), np.clip(xs[big] + dx, 0, w - 1)
        arr[yy, xx] = np.maximum(arr[yy, xx], br[big, None] * 0.8)

    # vignette
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    v = 1 - 0.45 * np.clip(xx**2 * 0.9 + yy**2 * 0.35, 0, 1)
    arr *= v[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- decor sprites
def _glow(img: Image.Image, color, radius: int, strength: float = 0.8) -> Image.Image:
    a = img.split()[3].filter(ImageFilter.GaussianBlur(radius))
    g = Image.new("RGBA", img.size, color + (0,))
    g.putalpha(a.point(lambda v: int(min(255, v * strength))))
    g.alpha_composite(img)
    return g


@lru_cache(maxsize=32)
def decor_sprite(kind: str, r: int, seed: int, c1: str, c2: str) -> Image.Image:
    rng = np.random.default_rng(seed)
    S = int(r * (3.6 if kind in ("sun", "black_hole") else 2.9))
    c = S / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    dx, dy = (xx - c) / r, (yy - c) / r
    d2 = dx**2 + dy**2
    inside = d2 <= 1
    z = np.sqrt(np.clip(1 - d2, 0, 1))
    light = np.clip(-0.55 * dx - 0.45 * dy + 0.7 * z, 0, 1) ** 1.2
    rgba = np.zeros((S, S, 4), dtype=np.float32)
    a1, a2 = np.array(hex_rgb(c1), np.float32), np.array(hex_rgb(c2), np.float32)

    if kind in ("planet", "ring_planet", "moon"):
        freq = rng.uniform(6, 14)
        bands = 0.5 + 0.5 * np.sin(dy * freq + np.sin(dx * 3 + rng.uniform(0, 6)) * 0.8)
        if kind == "moon":
            a1, a2 = np.array([185, 185, 192], np.float32), np.array([95, 95, 108], np.float32)
            bands = np.full_like(dx, 0.75)
            for _ in range(28):  # craters
                cx_, cy_ = rng.uniform(-0.9, 0.9, 2)
                cr = rng.uniform(0.05, 0.22)
                dist = np.sqrt((dx - cx_) ** 2 + (dy - cy_) ** 2) / cr
                bands -= 0.35 * np.clip(1 - dist, 0, 1) ** 0.5 * rng.uniform(0.4, 1)
                bands += 0.12 * np.exp(-((dist - 1.0) ** 2) / 0.02)
            bands = np.clip(bands, 0, 1)
        col = a1 * bands[..., None] + a2 * (1 - bands[..., None])
        col = col * (0.15 + 0.95 * light[..., None])
        rgba[..., :3] = col
        rgba[..., 3] = inside * 255
        img = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")
        img = _glow(img, tuple(int(v) for v in a1), int(r * 0.12), 0.7)
        if kind == "ring_planet":
            ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            rd = ImageDraw.Draw(ring)
            for k, wdt in ((1.75, 10), (1.55, 6), (1.95, 4)):
                rd.ellipse([c - r * k, c - r * k * 0.28, c + r * k, c + r * k * 0.28],
                           outline=tuple(int(v) for v in a1) + (200,), width=wdt)
            # back half of ring behind planet, front half over it
            back = ring.crop((0, 0, S, int(c)))
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.paste(back, (0, 0), back)
            out.alpha_composite(img)
            front = ring.crop((0, int(c), S, S))
            out.alpha_composite(front, (0, int(c)))
            img = out
        return img

    if kind == "sun":
        core = np.clip(1.2 - np.sqrt(d2) * 0.6, 0, 1)
        col = np.array([255, 240, 180], np.float32) * core[..., None] + np.array([255, 140, 20], np.float32) * (1 - core[..., None])
        rgba[..., :3] = col
        rgba[..., 3] = inside * 255
        img = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")
        return _glow(_glow(img, (255, 160, 40), int(r * 0.22), 1.0), (255, 220, 120), int(r * 0.08), 1.0)

    if kind == "black_hole":
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dd = ImageDraw.Draw(img)
        for k, wdt, colr in ((1.6, int(r * 0.22), (255, 120, 20, 230)), (1.35, int(r * 0.1), (255, 210, 120, 255))):
            dd.ellipse([c - r * k, c - r * k * 0.32, c + r * k, c + r * k * 0.32], outline=colr, width=wdt)
        dd.ellipse([c - r * 1.08, c - r * 1.08, c + r * 1.08, c + r * 1.08], outline=(255, 170, 60, 230), width=int(r * 0.08))
        img = img.filter(ImageFilter.GaussianBlur(r * 0.05))
        img = _glow(img, (255, 120, 20), int(r * 0.2), 1.3)
        dd = ImageDraw.Draw(img)
        dd.ellipse([c - r, c - r, c + r, c + r], fill=(0, 0, 0, 255))
        return img

    raise ValueError(kind)


DECOR_CYCLE = ["planet", "ring_planet", "moon", "sun", "black_hole", "planet"]
DECOR_ANCHORS = [(0.82, 0.83), (0.15, 0.80), (0.86, 0.17), (0.12, 0.20), (0.80, 0.78), (0.20, 0.85)]


def number_tokens(text: str) -> re.Match | None:
    return re.search(r"\d[\d,]*(?:\.\d+)?", text)
