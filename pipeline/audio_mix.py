"""Voiceover timeline + background music ducked under speech + scene-cut whooshes. Deterministic numpy DSP."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .config import resolve
from .ffmpeg import decode_audio, run, write_wav


def db(x: float) -> float:
    return 10 ** (x / 20)


def rms_db(a: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-9)


def ambient_drone(n: int, sr: int, seed: int) -> np.ndarray:
    """Generated space pad (royalty-free by construction): detuned sine chord with slow swells."""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64) / sr
    roots = [[55.0, 82.41, 110.0, 164.81, 220.0], [49.0, 73.42, 98.0, 146.83, 196.0],
             [58.27, 87.31, 116.54, 174.61, 233.08]]
    chord = roots[seed % len(roots)]
    out = np.zeros(n)
    for i, f in enumerate(chord):
        for det in (-0.6, 0.6):
            ph = rng.uniform(0, 2 * np.pi)
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.03, 0.09) * t + ph)
            out += np.sin(2 * np.pi * (f + det) * t + ph) * lfo / (1 + i * 0.6)
    shimmer = np.sin(2 * np.pi * chord[-1] * 2 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)) * 0.15
    out += shimmer
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.5).astype(np.float32)


def whoosh(sr: int, seed: int, dur: float = 0.35) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(sr * dur)
    noise = rng.standard_normal(n)
    # crude sweeping band-pass via moving averages of decreasing width
    out = np.zeros(n)
    for k in (64, 32, 16, 8):
        out += np.convolve(noise, np.ones(k) / k, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    out *= env
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


def pick_music(acfg: dict, ep: dict) -> Path | None:
    m = (ep.get("music") or {}).get("file")
    if m and resolve(m).exists():
        return resolve(m)
    d = resolve(acfg.get("music_dir", "assets/music"))
    tracks = sorted([p for p in d.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac")]) if d.exists() else []
    if tracks:
        return tracks[(int(ep["episode_number"]) - 1) % len(tracks)]
    return None


def mix(vo: np.ndarray, sr: int, cut_samples: list[int], acfg: dict, ep: dict, out_wav: Path) -> dict:
    n = len(vo)
    info: dict = {}
    vo_level = rms_db(vo[np.abs(vo) > 0.01]) if np.any(np.abs(vo) > 0.01) else -20.0

    # --- music bed
    path = pick_music(acfg, ep)
    music = None
    if path is not None:
        m = decode_audio(path, sr)
        if len(m):
            reps = int(np.ceil(n / len(m)))
            music = np.tile(m, reps)[:n]
            info["music"] = str(path.name)
    elif acfg.get("fallback_music", "ambient") == "ambient":
        music = ambient_drone(n, sr, int(ep["episode_number"]))
        info["music"] = "generated ambient"
    if music is not None:
        music = music / db(rms_db(music))  # normalise to 0 dB RMS reference
        # speech activity in 10 ms blocks
        blk = sr // 100
        nb = int(np.ceil(n / blk))
        pad = np.zeros(nb * blk, dtype=np.float32)
        pad[:n] = vo
        e = np.sqrt(np.mean(pad.reshape(nb, blk) ** 2, axis=1))
        speech = 20 * np.log10(e + 1e-9) > vo_level - 22
        # hold speech flag 150 ms after it stops, pre-roll 50 ms
        held = speech.copy()
        for k in range(1, 16):
            held[k:] |= speech[:-k]
        for k in range(1, 6):
            held[:-k] |= speech[k:]
        target = np.where(held, acfg.get("music_under_speech_db", -20), acfg.get("music_gaps_db", -14)).astype(np.float64)
        g = np.empty(nb)
        cur = target[0]
        for i in range(nb):  # attack 60 ms, release 300 ms
            a = 0.15 if target[i] < cur else 0.033
            cur += (target[i] - cur) * a
            g[i] = cur
        gain = np.repeat(db(vo_level) * (10 ** (g / 20)), blk)[:n]
        fade_in, fade_out = int(0.3 * sr), int(0.8 * sr)
        env = np.ones(n)
        env[:fade_in] = np.linspace(0, 1, fade_in)
        env[-fade_out:] = np.linspace(1, 0, fade_out)
        bed = music * gain * env
    else:
        bed = np.zeros(n)

    # --- whooshes at scene cuts
    sfx = np.zeros(n)
    if acfg.get("whoosh", True):
        w = whoosh(sr, int(ep["episode_number"]))
        lvl = db(vo_level) * db(acfg.get("whoosh_db", -24) + 12)
        for s in cut_samples:
            a = max(0, s - len(w) // 2)
            b = min(n, a + len(w))
            sfx[a:b] += w[: b - a] * lvl

    out = vo.astype(np.float64) + bed + sfx
    peak = np.max(np.abs(out)) + 1e-9
    if peak > 0.98:
        out *= 0.98 / peak
    raw = out_wav.with_name("mix_raw.wav")
    write_wav(raw, out.astype(np.float32), sr)
    lufs = acfg.get("loudness_lufs", -14)
    run(["-i", raw, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11", "-ar", sr, "-ac", 2, out_wav], "loudnorm")
    return info
