#!/usr/bin/env python
"""One-off ElevenLabs check (run in GitHub Actions, where the key lives). Never prints the key.

Reports: credits left, models that speak Hindi, whether the expressive model returns word timings,
and writes short Hindi/Hinglish voice samples to voice_samples/elevenlabs/.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import requests

KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
API = "https://api.elevenlabs.io"
H = {"xi-api-key": KEY}
OUT = Path("voice_samples/elevenlabs")
LINE_ROMAN = "[excited] Bhai, NASA ne Mars par aise rocks dhoondhe hain! [whispers] Aur sach bataun? Yeh toh pagal kar dega."
LINE_DEVA = "[excited] भाई, NASA ने Mars पर ऐसे rocks ढूंढे हैं! [whispers] और सच बताऊँ? ये तो पागल कर देगा।"


def get(path, **params):
    r = requests.get(API + path, headers=H, params=params, timeout=60)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def tts(voice_id, text, model):
    r = requests.post(f"{API}/v1/text-to-speech/{voice_id}/with-timestamps", headers=H, timeout=120,
                      json={"text": text, "model_id": model})
    if r.status_code != 200:
        return None, f"{r.status_code}: {r.text[:200]}"
    d = r.json()
    al = d.get("alignment") or {}
    return base64.b64decode(d["audio_base64"]), f"ok, timing chars={len(al.get('characters', []))}"


def main() -> int:
    if not KEY:
        print("ELEVENLABS_API_KEY missing")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    st, sub = get("/v1/user/subscription")
    if st == 200:
        print(f"PLAN {sub.get('tier')} credits used {sub.get('character_count')} of {sub.get('character_limit')}, "
              f"voice slots {sub.get('voice_slots_used')}/{sub.get('voice_limit')}")
    else:
        print("subscription check failed", st, str(sub)[:200])

    st, models = get("/v1/models")
    hindi_models = []
    if st == 200:
        for m in models:
            langs = [l.get("language_id") for l in m.get("languages", [])]
            if m.get("can_do_text_to_speech"):
                print(f"MODEL {m['model_id']:<28} hindi={'hi' in langs} cost={m.get('model_rates', {})} {m.get('name')}")
                if "hi" in langs:
                    hindi_models.append(m["model_id"])
    expressive = next((m for m in ("eleven_v4", "eleven_v3") if m in hindi_models), None) or \
        next((m for m in hindi_models if m.startswith("eleven_v")), "eleven_multilingual_v2")
    print("USING MODEL", expressive)

    st, shared = get("/v1/shared-voices", language="hi", page_size=40, sort="usage_character_count_1y")
    voices = []
    if st == 200:
        for v in shared.get("voices", []):
            voices.append(v)
            print(f"VOICE {v['voice_id']} | {v.get('name')} | {v.get('gender')} | {v.get('age')} | "
                  f"{v.get('accent')} | {v.get('use_case')} | {(v.get('descriptive') or '')}")
    else:
        print("shared voices failed", st, str(shared)[:200])

    picks = []
    for g in ("female", "male"):
        picks += [v for v in voices if v.get("gender") == g and v.get("use_case") in
                  ("narrative_story", "social_media", "characters_animation", "conversational", "entertainment_tv")][:3]
    results = {}
    for i, v in enumerate(picks, 1):
        vid = v["voice_id"]
        audio, msg = tts(vid, LINE_ROMAN, expressive)
        if audio is None and v.get("public_owner_id"):
            r = requests.post(f"{API}/v1/voices/add/{v['public_owner_id']}/{vid}", headers=H, timeout=60,
                              json={"new_name": v.get("name", "hindi")[:40]})
            print(f"  added {v.get('name')} to library: {r.status_code}")
            audio, msg = tts(vid, LINE_ROMAN, expressive)
        name = f"{i}_{v.get('gender')}_{(v.get('name') or 'voice').replace(' ', '_')[:24]}"
        print(f"SAMPLE {name} roman: {msg}")
        if audio:
            (OUT / f"{name}_roman.mp3").write_bytes(audio)
            results[name] = vid
        if i == 1 and audio:
            audio2, msg2 = tts(vid, LINE_DEVA, expressive)
            print(f"SAMPLE {name} devanagari: {msg2}")
            if audio2:
                (OUT / f"{name}_devanagari.mp3").write_bytes(audio2)
    (OUT / "voices.json").write_text(json.dumps({"model": expressive, "voices": results}, indent=2), encoding="utf-8")
    st, sub = get("/v1/user/subscription")
    if st == 200:
        print(f"AFTER credits used {sub.get('character_count')} of {sub.get('character_limit')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
