"""Default backend: programmatic deep-space motion background with drifting starfield and a decor body."""
from __future__ import annotations

import math
from typing import Iterator

from PIL import Image

from .base import SceneCtx, VisualBackend
from .common import DECOR_ANCHORS, DECOR_CYCLE, decor_sprite, ease_out_cubic, scaled, space_background


class KineticBackend(VisualBackend):
    name = "kinetic"

    def frames(self, ctx: SceneCtx) -> Iterator[Image.Image]:
        pal = ctx.cfg["visuals"]["palette"]
        extra = 360
        bg = space_background(ctx.w, ctx.h, pal, ctx.seed, extra)
        direction = 1 if ctx.index % 2 == 0 else -1

        decor = ctx.style.get("decor", "auto")
        if decor == "auto":
            decor = "none" if ctx.scene.get("role") == "hook" else DECOR_CYCLE[(ctx.seed) % len(DECOR_CYCLE)]
        sprite = None
        if decor != "none":
            r = int(ctx.w * (0.30 if decor in ("sun", "black_hole") else 0.26))
            nebs = pal.get("nebula", ["#3B1E8C", "#0E4D7A"])
            c1 = pal["accent2"] if ctx.index % 2 else nebs[ctx.seed % len(nebs)]
            c2 = nebs[(ctx.seed + 1) % len(nebs)]
            sprite = decor_sprite(decor, r, ctx.seed, c1, c2)
            ax, ay = DECOR_ANCHORS[ctx.seed % len(DECOR_ANCHORS)]

        n = ctx.n_frames
        for i in range(n):
            p = i / max(1, n - 1)
            off = int(extra * (p if direction > 0 else 1 - p) * 0.6)
            frame = bg.crop((0, off, ctx.w, off + ctx.h))
            if sprite is not None:
                t = i / ctx.fps
                enter = ease_out_cubic(t / 0.6)
                s = 0.94 + 0.08 * p
                sp = scaled(sprite, s)
                cx = ctx.w * ax + direction * 40 * p + (1 - enter) * (180 if ax > 0.5 else -180)
                cy = ctx.h * ay + 12 * math.sin(t * 1.3)
                frame.paste(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)), sp)
            yield frame
