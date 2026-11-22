"""Orchestrates one episode: validate -> TTS -> timeline -> audio mix -> frames -> encode -> metadata -> history."""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import history, schema
from .audio_mix import mix
from .captions import CaptionRenderer, build_chunks
from .config import resolve
from .ffmpeg import decode_audio, open_encoder
from .metadata import write_caption_file
from .tts import get_tts
from .visuals import SceneCtx, get_visual
from .visuals.overlay import SceneOverlay


class BuildError(RuntimeError):
    pass


def load_episode(script: Path) -> dict:
    with open(script, encoding="utf-8") as f:
        return json.load(f)


def build(script: Path, cfg: dict, *, force: bool = False, tts_override: str | None = None,
          validate_only: bool = False) -> Path | None:
    t0 = time.time()
    ep = load_episode(script)
    errors, warns = schema.validate(ep)
    for w in warns:
        print(f"  warn: {w}")
    if errors:
        raise BuildError("script invalid:\n  - " + "\n  - ".join(errors))
    print(f"✓ script valid: ep {ep['episode_number']} '{ep['title']}'")
    if validate_only:
        return None

    n = int(ep["episode_number"])
    out_dir = resolve(cfg["paths"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"ep_{n:03d}_{ep['slug']}.mp4"
    out_txt = out_dir / f"ep_{n:03d}_caption.txt"
    hist = resolve(cfg["paths"]["history"])
    try:
        script_rel = script.resolve().relative_to(resolve(".")).as_posix()
    except ValueError:
        script_rel = str(script)
    if out_mp4.exists() and not force:
        raise BuildError(f"{out_mp4.name} already exists (use --force to overwrite)")

    work = resolve(cfg["paths"]["build_dir"]) / f"ep_{n:03d}"
    (work / "audio").mkdir(parents=True, exist_ok=True)
    vcfg = cfg["video"]
    W, H, FPS = vcfg["width"], vcfg["height"], vcfg["fps"]
    acfg = cfg["audio"]
    sr = acfg.get("sample_rate", 48000)

    try:
        # ---------------- 1. TTS per scene
        # config.yaml decides the engine; an episode's voice block only applies if it names the same engine
        engine = tts_override or cfg["tts"]["engine"]
        voice = dict(ep.get("voice") or {})
        if voice.get("engine") != engine:
            voice = {}
        tts = get_tts(engine, cfg["tts"])
        print(f"→ voice: {engine} {voice.get('voice_id') or (cfg['tts'].get(engine) or {}).get('voice', '')}")
        cache = resolve(cfg["paths"]["build_dir"]) / "cache" / "tts"
        clips, words_per_scene, n_frames = [], [], []
        for s in ep["scenes"]:
            path, words = tts.cached(s["narration"], cache, voice)
            a = decode_audio(path, sr)
            # trim leading/trailing silence the engine adds (keep 40 ms)
            nz = np.nonzero(np.abs(a) > 0.003)[0]
            lead = 0
            if len(nz):
                lead = max(0, nz[0] - int(0.04 * sr))
                a = a[lead : nz[-1] + int(0.08 * sr)]
            shift = lead / sr
            words = [type(w)(w.text, max(0.0, w.start - shift), max(0.0, w.end - shift)) for w in words]
            pad = float(s.get("pad_after", acfg.get("pad_after_default", 0.15)))
            nf = math.ceil((len(a) / sr + pad) * FPS)
            clips.append(a)
            words_per_scene.append(words)
            n_frames.append(nf)
            print(f"  scene {s['id']:>2}: {nf / FPS:5.2f}s  {s['narration'][:60]}")

        durations = [f / FPS for f in n_frames]
        total = sum(durations)
        for w in schema.timing_warnings(durations, total):
            print(f"  warn: {w}")
        print(f"→ runtime {total:.1f}s, {sum(n_frames)} frames")

        # ---------------- 2. voiceover timeline + mix
        starts_f = np.cumsum([0] + n_frames[:-1]).tolist()
        total_samples = int(round(sum(n_frames) / FPS * sr))
        vo = np.zeros(total_samples, dtype=np.float32)
        for a, sf in zip(clips, starts_f):
            i = int(round(sf / FPS * sr))
            j = min(total_samples, i + len(a))
            vo[i:j] += a[: j - i]
        cuts = [int(round(sf / FPS * sr)) for sf in starts_f[1:]]
        mix_wav = work / "mix.wav"
        info = mix(vo, sr, cuts, acfg, ep, mix_wav)
        print(f"→ audio mixed (music: {info.get('music', 'none')})")

        # ---------------- 3. captions
        starts_s = [sf / FPS for sf in starts_f]
        ends_s = [st + d for st, d in zip(starts_s, durations)]
        c = cfg["captions"]
        chunks = build_chunks(words_per_scene, starts_s, ends_s, c.get("max_words", 3), c.get("max_chars", 20))
        caps = CaptionRenderer(chunks, cfg, W, H)

        # ---------------- 4. frames -> encoder
        tmp_mp4 = work / "render.mp4"
        log = work / "ffmpeg_encode.log"
        enc = open_encoder(tmp_mp4, mix_wav, vcfg, log)
        assert enc.stdin is not None
        frame_no = 0
        try:
            for idx, s in enumerate(ep["scenes"]):
                backend_name = (s.get("visual") or {}).get("backend") or cfg["visuals"]["default_backend"]
                ctx = SceneCtx(ep=ep, scene=s, index=idx, n_frames=n_frames[idx], fps=FPS, w=W, h=H, cfg=cfg, work=work)
                overlay = SceneOverlay(ctx)
                ts = time.time()
                count = 0
                for i, frame in enumerate(get_visual(backend_name).frames(ctx)):
                    if i >= ctx.n_frames:
                        break
                    if frame.mode != "RGB" or frame.size != (W, H):
                        frame = frame.convert("RGB").resize((W, H))
                    if idx > 0 and i < 5:  # quick punch-in on every cut
                        k = 1.0 + 0.06 * (1 - i / 5) ** 2
                        cw, chh = W / k, H / k
                        frame = frame.resize((W, H), Image.BILINEAR,
                                             box=((W - cw) / 2, (H - chh) / 2, (W + cw) / 2, (H + chh) / 2))
                    overlay.draw(frame, i)
                    caps.draw(frame, (frame_no + 0.5) / FPS)
                    enc.stdin.write(frame.tobytes())
                    frame_no += 1
                    count += 1
                if count < ctx.n_frames:
                    raise BuildError(f"scene {s['id']}: backend yielded {count}/{ctx.n_frames} frames")
                print(f"  rendered scene {s['id']:>2} [{backend_name}] in {time.time() - ts:4.1f}s")
        except BrokenPipeError:
            pass
        finally:
            enc.stdin.close()
            rc = enc.wait()
        if rc != 0:
            raise BuildError(f"ffmpeg encode failed (exit {rc}):\n{log.read_text(errors='replace')[-2000:]}")

        # ---------------- 5. publish
        os.replace(tmp_mp4, out_mp4)
        write_caption_file(ep, cfg, out_txt, out_mp4.name, total)
        rel = Path(cfg["paths"]["output_dir"]) / out_mp4.name
        history.upsert(hist, ep, script_rel, status="rendered", output_file=rel.as_posix(),
                       duration_sec=round(total, 2), voice_engine=engine)
        print(f"✓ done in {time.time() - t0:.0f}s → {rel}")
        return out_mp4
    except Exception as e:
        history.upsert(hist, ep, script_rel, status="failed", error=str(e)[:300])
        raise


def clean(cfg: dict, n: int) -> None:
    d = resolve(cfg["paths"]["build_dir"]) / f"ep_{n:03d}"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
