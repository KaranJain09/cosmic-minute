from __future__ import annotations

from .base import SceneCtx, VisualBackend


def get_visual(name: str) -> VisualBackend:
    if name == "kinetic":
        from .kinetic import KineticBackend

        return KineticBackend()
    if name == "kenburns":
        from .kenburns import KenBurnsBackend

        return KenBurnsBackend()
    if name == "nasa":
        from .nasa import NasaBackend

        return NasaBackend()
    if name == "stock":
        from .stock import StockBackend

        return StockBackend()
    raise ValueError(f"unknown visual backend '{name}'")


__all__ = ["get_visual", "SceneCtx", "VisualBackend"]
