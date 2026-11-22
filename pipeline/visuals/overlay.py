"""Text layer composited over every backend: episode badge, hook title card, on-screen text, CTA pills."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

from ..config import hex_rgb
from .base import SceneCtx
from .common import (clamp, ease_out_back, ease_out_cubic, font, number_tokens, paste_center, pill,
                     render_rich, scaled)


def title_card(text: str, fspec: dict, max_w: int, accent, size: int = 150) -> Image.Image:
    txt = render_rich(text, fspec, size, max_w - 80, max_lines=2, fill=(10, 10, 16), accent=(10, 10, 16),
                      stroke=0, shadow=False)
    pad = 34
    W, H = txt.width + pad * 2, txt.height + pad
    card = Image.new("RGBA", (W + 40, H + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([20, 20, 20 + W, 20 + H], radius=26, fill=accent + (255,))
    card.alpha_composite(txt, (20 + pad, 20 + pad // 2))
    card = card.rotate(-3, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sh.putalpha(card.split()[3].filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.7)))
    sh.alpha_composite(card)
    return sh


class SceneOverlay:
    def __init__(self, ctx: SceneCtx):
        self.ctx = ctx
        cfg = ctx.cfg
        self.pal = cfg["visuals"]["palette"]
        self.accent = hex_rgb(self.pal["accent"])
        self.accent2 = hex_rgb(self.pal["accent2"])
        self.fd, self.fu = cfg["fonts"]["display"], cfg["fonts"]["ui"]
        self.role = ctx.scene.get("role")
        self.text = ctx.scene.get("on_screen_text") or ""
        self.motion = ctx.style.get("motion", "pop")
        self.y_text = ctx.h * cfg["visuals"].get("on_screen_text_y", 0.34)
        self._cache: dict[str, Image.Image] = {}

        ep = ctx.ep
        self.badge = None
        if cfg["overlay"].get("badge", True):
            series = (ep.get("series_title") or cfg["channel"]["series_title"]).upper()
            self.badge = pill(f"{series}  ·  EP {ep['episode_number']}", self.fu, 34, (0, 0, 0, 140), self.accent2 + (255,))
        self.card = None
        if self.role == "hook" and ep.get("title_card"):
            self.card = title_card(ep["title_card"], self.fd, int(ctx.w * 0.9), self.accent)
        self.cta = self.follow = None
        if self.role == "cta":
            nxt = int(ep["episode_number"]) + 1
            self.cta = pill(cfg["overlay"]["cta_text"], self.fu, 44, self.accent + (255,), (10, 10, 16, 255))
            self.follow = pill(cfg["overlay"]["follow_text"].format(next=nxt), self.fu, 36, (255, 255, 255, 235), (10, 10, 16, 255))
        self.num = number_tokens(self.text) if self.motion == "count" else None
        # darken a soft band behind the headline when the background is a real photo/video
        backend = (ctx.scene.get("visual") or {}).get("backend") or cfg["visuals"]["default_backend"]
        self.band = None
        if backend != "kinetic" and (self.text or self.card is not None):
            import numpy as np

            y0, y1 = int(ctx.h * 0.12), int(ctx.h * 0.60)
            yc = (ctx.h * 0.33 if self.card is not None else self.y_text) - y0
            yy = np.arange(y1 - y0, dtype=np.float32)
            a = 175 * np.exp(-((yy - yc) / (ctx.h * 0.13)) ** 2)
            self.band = Image.fromarray(np.repeat(a[:, None], ctx.w, axis=1).astype(np.uint8), "L")
            self.band_y = y0

    def _text_img(self, text: str, size: int = 132) -> Image.Image:
        key = f"{size}|{text}"
        if key not in self._cache:
            self._cache[key] = render_rich(text, self.fd, size, int(self.ctx.w * 0.86), max_lines=3,
                                           accent=self.accent, stroke=8)
        return self._cache[key]

    def _animated_text(self, t: float) -> str:
        txt = self.text
        dur = self.ctx.duration
        if self.motion == "words":
            ws = txt.split()
            k = max(1, math.ceil(len(ws) * clamp(t / max(0.3, dur * 0.55))))
            # keep highlight markup balanced
            part = " ".join(ws[:k])
            return part + ("*" if part.count("*") % 2 else "")
        if self.num is not None:
            raw = self.num.group(0)
            val = float(raw.replace(",", ""))
            dec = len(raw.split(".")[1]) if "." in raw else 0
            v = val * ease_out_cubic(t / 0.9)
            s = f"{v:,.{dec}f}" if "," in raw else f"{v:.{dec}f}"
            return txt[: self.num.start()] + s + txt[self.num.end():]
        return txt

    def draw(self, frame: Image.Image, i: int) -> None:
        ctx = self.ctx
        t = i / ctx.fps
        dur = ctx.duration
        W = ctx.w

        if self.band is not None:
            frame.paste((0, 0, 0), (0, self.band_y), self.band)
        if self.badge is not None:
            paste_center(frame, self.badge, W / 2, 250, alpha=0.95)

        y_main = self.y_text
        if self.card is not None:
            k = ease_out_cubic(t / 0.22)
            s = 1.6 - 0.6 * k
            jit = 10 * math.sin(t * 80) * clamp(1 - (t - 0.22) / 0.25) if t > 0.22 else 0
            paste_center(frame, scaled(self.card, s), W / 2 + jit, ctx.h * 0.33, alpha=clamp(t / 0.08))
            y_main = ctx.h * 0.47
            if self.text:
                img = self._text_img(self.text, 92)
                paste_center(frame, scaled(img, 0.6 + 0.4 * ease_out_back((t - 0.35) / 0.3)), W / 2, y_main,
                             alpha=clamp((t - 0.35) / 0.1))
        elif self.text:
            if self.role == "cta":
                y_main = ctx.h * 0.31
            img = self._text_img(self._animated_text(t))
            p = t / max(dur, 0.01)
            m = self.motion
            x, y, a, s = W / 2, y_main, clamp(t / 0.12), 1.0
            if m in ("pop", "count", "words", "shake"):
                s = 0.55 + 0.45 * ease_out_back(t / 0.35) + 0.03 * p
            elif m == "zoom_in":
                s = 0.92 + 0.14 * ease_out_cubic(p)
            elif m == "zoom_out":
                s = 1.18 - 0.18 * ease_out_cubic(t / (dur * 0.6))
            elif m in ("slide_up", "pan_up", "pan_left", "pan_right"):
                y += 140 * (1 - ease_out_cubic(t / 0.4))
                a = clamp(t / 0.3)
            if m == "shake" and 0.3 < t < 0.75:
                x += 16 * math.sin(t * 95) * (1 - (t - 0.3) / 0.45)
                y += 6 * math.cos(t * 70)
            paste_center(frame, scaled(img, s), x, y, alpha=a)

        if self.cta is not None:
            pulse = 1 + 0.045 * math.sin(t * 6.5)
            paste_center(frame, scaled(self.cta, pulse * ease_out_back((t - 0.25) / 0.35)), W / 2, ctx.h * 0.435,
                         alpha=clamp((t - 0.25) / 0.1))
            paste_center(frame, self.follow, W / 2, ctx.h * 0.515, alpha=clamp((t - 0.6) / 0.2))

        if self.role == "hook" and t < 0.12:  # pattern-interrupt flash on frame 1
            flash = Image.new("RGB", frame.size, (255, 255, 255))
            frame.paste(Image.blend(frame, flash, 0.85 * (1 - t / 0.12)))
