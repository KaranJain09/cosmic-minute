from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image


@dataclass
class SceneCtx:
    ep: dict
    scene: dict
    index: int          # 0-based scene index
    n_frames: int
    fps: int
    w: int
    h: int
    cfg: dict
    work: Path

    @property
    def seed(self) -> int:
        return int(self.ep["episode_number"]) * 1000 + int(self.scene["id"])

    @property
    def style(self) -> dict:
        return (self.scene.get("visual") or {}).get("style") or {}

    @property
    def duration(self) -> float:
        return self.n_frames / self.fps


class VisualBackend:
    """A backend yields exactly ctx.n_frames RGB background frames of size (w, h).
    Text overlays and captions are composited on top by the renderer, so every backend gets them."""

    name = "base"

    def frames(self, ctx: SceneCtx) -> Iterator[Image.Image]:
        raise NotImplementedError
