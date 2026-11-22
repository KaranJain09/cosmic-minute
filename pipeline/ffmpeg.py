"""All FFmpeg access goes through here. Uses ffmpeg on PATH, else the imageio-ffmpeg bundled binary."""
from __future__ import annotations

import shutil
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "FFmpeg not found. Install it (winget install Gyan.FFmpeg) or `uv sync` to get imageio-ffmpeg."
        ) from e


def run(args: list, what: str = "ffmpeg") -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode(errors="replace")[-3000:]
        raise RuntimeError(f"{what} failed (exit {r.returncode}):\n{' '.join(cmd)}\n{err}")


def decode_audio(path: Path, sr: int = 48000) -> np.ndarray:
    """Decode any audio file to mono float32 at `sr`."""
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"Could not decode audio {path}:\n{r.stderr.decode(errors='replace')[-1500:]}")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    """Write mono or (n,2) float array as 16-bit PCM WAV."""
    a = np.clip(samples, -1.0, 1.0)
    channels = 1 if a.ndim == 1 else a.shape[1]
    pcm = (a * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def open_encoder(out: Path, audio: Path, vcfg: dict, log_path: Path) -> subprocess.Popen:
    """Start an ffmpeg process that reads raw RGB frames on stdin and muxes `audio`."""
    w, h, fps = vcfg["width"], vcfg["height"], vcfg["fps"]
    cmd = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", vcfg.get("preset", "veryfast"), "-crf", str(vcfg.get("crf", 20)),
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(fps * 2),
        "-c:a", "aac", "-b:a", vcfg.get("audio_bitrate", "192k"), "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest",
        str(out),
    ]
    log = open(log_path, "wb")
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
