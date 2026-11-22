"""Burned-in captions: 1-3 word chunks, centered, white text with dark stroke on a translucent box,
active word highlighted. Drawn straight onto frames (no libass / font-path issues on Windows)."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from .config import hex_rgb
from .tts.base import Word
from .visuals.common import font, scaled

PUNCT_BREAK = (".", ",", "?", "!", ":", ";", "—")


@dataclass
class Chunk:
    words: list[Word]
    start: float
    end: float


def build_chunks(scene_words: list[list[Word]], scene_starts: list[float], scene_ends: list[float],
                 max_words: int, max_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for words, s0, s_end in zip(scene_words, scene_starts, scene_ends):
        cur: list[Word] = []
        glob = [Word(w.text, s0 + w.start, s0 + w.end) for w in words]
        for w in glob:
            if cur and (len(cur) >= max_words or len(" ".join(x.text for x in cur + [w])) > max_chars):
                chunks.append(Chunk(cur, cur[0].start, w.start))
                cur = []
            cur.append(w)
            if w.text.endswith(PUNCT_BREAK):
                chunks.append(Chunk(cur, cur[0].start, w.end))
                cur = []
        if cur:
            chunks.append(Chunk(cur, cur[0].start, cur[-1].end))
        # hold each scene's last chunk until the cut (no blank gap)
        same_scene = [c for c in chunks if c.start >= s0 - 1e-6]
        if same_scene:
            same_scene[-1].end = max(same_scene[-1].end, s_end - 0.02)
    # close gaps between chunks inside a scene so text doesn't flicker
    for a, b in zip(chunks, chunks[1:]):
        if 0 < b.start - a.end < 0.35:
            a.end = b.start
    return chunks


class CaptionRenderer:
    def __init__(self, chunks: list[Chunk], cfg: dict, w: int, h: int):
        self.chunks = chunks
        c = cfg["captions"]
        self.c = c
        self.font = font(cfg["fonts"]["caption"], c.get("size", 76))
        self.color = hex_rgb(c.get("color", "#FFFFFF"))
        self.hl = hex_rgb(c.get("highlight", "#FFD400"))
        self.stroke = c.get("stroke", 6)
        self.box_a = int(255 * c.get("box_opacity", 0.55))
        self.w, self.h = w, h
        self.cy = h * c.get("y", 0.62)
        self.max_w = int(w * 0.84)
        self._cache: dict[tuple[int, int], Image.Image] = {}
        self._idx = 0

    def _render(self, ci: int, active: int) -> Image.Image:
        key = (ci, active)
        if key in self._cache:
            return self._cache[key]
        words = [w.text.upper() if self.c.get("uppercase", True) else w.text for w in self.chunks[ci].words]
        f = self.font
        sp = f.getlength(" ")
        # wrap into at most 2 lines
        lines: list[list[int]] = [[]]
        lw = 0.0
        for i, w in enumerate(words):
            wl = f.getlength(w)
            if lines[-1] and lw + sp + wl > self.max_w:
                lines.append([])
                lw = 0.0
            lw += (sp if lines[-1] else 0) + wl
            lines[-1].append(i)
        asc, desc = f.getmetrics()
        lh = asc + desc
        widths = [sum(f.getlength(words[i]) for i in ln) + sp * (len(ln) - 1) for ln in lines]
        px, py = 34, 16
        W = int(max(widths)) + px * 2 + self.stroke * 2
        H = lh * len(lines) + py * 2 + self.stroke * 2
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=26, fill=(0, 0, 0, self.box_a))
        for li, ln in enumerate(lines):
            x = (W - widths[li]) / 2
            y = py + self.stroke + li * lh
            for i in ln:
                col = self.hl if i == active else self.color
                d.text((x, y), words[i], font=f, fill=col, stroke_width=self.stroke, stroke_fill=(0, 0, 0))
                x += f.getlength(words[i]) + sp
        self._cache[key] = img
        return img

    def draw(self, frame: Image.Image, t: float) -> None:
        # frames arrive in order; walk forward
        while self._idx < len(self.chunks) - 1 and t >= self.chunks[self._idx + 1].start:
            self._idx += 1
        ch = self.chunks[self._idx] if self.chunks else None
        if ch is None or not (ch.start <= t < ch.end):
            return
        active = 0
        for k, w in enumerate(ch.words):
            if t >= w.start:
                active = k
        img = self._render(self._idx, active)
        age = t - ch.start
        s = 0.86 + 0.14 * min(1.0, age / 0.09)
        im = scaled(img, s)
        frame.paste(im, (int(self.w / 2 - im.width / 2), int(self.cy - im.height / 2)), im)
