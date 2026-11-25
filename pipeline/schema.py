"""Episode JSON validation. Errors block the build; warnings are printed (Claude Code should fix them)."""
from __future__ import annotations

import re

ROLES = {"hook", "build", "reveal", "twist", "cta"}
BACKENDS = {"kinetic", "kenburns", "stock", "nasa"}
CAMERAS = {"zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up"}
FITS = {"auto", "cover", "contain"}
MOTIONS = {"pop", "zoom_in", "zoom_out", "shake", "slide_up", "words", "count", "pan_left", "pan_right", "pan_up"}
DECOR = {"auto", "none", "planet", "ring_planet", "sun", "black_hole", "moon"}
REQUIRED = [
    "episode_number", "title", "slug", "topic", "hook", "title_card",
    "cliffhanger_question", "summary", "scenes", "upload",
]
ANGLES = {"news", "event", "evergreen"}
DELIVERIES = {"normal", "excited", "curious", "shock", "serious", "question"}
# openers that only make sense to someone who saw a previous reel, or that waste the first second
WEAK_OPENERS = ("yes", "no", "maybe", "so ", "so,", "today", "hey", "hi ", "welcome", "in this video",
                "did you know", "have you ever", "let's", "here's", "answer", "part ", "next stop",
                "toh", "dosto", "namaste", "hello", "kya aap jaante", "aaj hum")
UPLOAD_REQUIRED = ["youtube_title", "instagram_caption", "description", "pinned_comment", "hashtags"]

MIN_WORDS, MAX_WORDS = 70, 105   # 25-40 s at a fast, clear pace
MIN_SCENES, MAX_SCENES = 9, 15


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z0-9]", w)])


def strip_markup(text: str) -> str:
    return text.replace("*", "")


def validate(ep: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []

    for k in REQUIRED:
        if k not in ep or ep[k] in (None, "", []):
            errors.append(f"missing field: {k}")
    if errors:
        return errors, warns

    if not isinstance(ep["episode_number"], int) or ep["episode_number"] < 1:
        errors.append("episode_number must be an integer >= 1")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ep["slug"]):
        errors.append("slug must be kebab-case: lowercase letters, digits, hyphens")
    if len(ep["title"]) > 60:
        warns.append(f"title is {len(ep['title'])} chars (aim <= 60)")
    if word_count(ep["title_card"]) > 5:
        warns.append("title_card should be 2-5 words")

    scenes = ep["scenes"]
    if not (MIN_SCENES <= len(scenes) <= MAX_SCENES):
        errors.append(f"{len(scenes)} scenes; need {MIN_SCENES}-{MAX_SCENES}")

    total = 0
    for i, s in enumerate(scenes, 1):
        tag = f"scene {i}"
        if s.get("id") != i:
            errors.append(f"{tag}: id must be {i} (sequential)")
        role = s.get("role")
        if role not in ROLES:
            errors.append(f"{tag}: role '{role}' not in {sorted(ROLES)}")
        nar = (s.get("narration") or "").strip()
        if not nar:
            errors.append(f"{tag}: empty narration")
            continue
        n = word_count(nar)
        total += n
        if n < 2 or n > 16:
            errors.append(f"{tag}: {n} words (hard limit 2-16, target 4-11)")
        elif n < 4 or n > 11:
            warns.append(f"{tag}: {n} words (target 4-11 so the picture changes every 1.5-3.5 s)")
        if any(len(sent.split()) > 12 for sent in re.split(r"[.!?]", nar)):
            warns.append(f"{tag}: a sentence is over 12 words; split it so it is easy to follow")
        if s.get("delivery") and s["delivery"] not in DELIVERIES:
            errors.append(f"{tag}: delivery '{s['delivery']}' not in {sorted(DELIVERIES)}")
        sp = (s.get("speech") or "").strip()
        if sp and abs(len(sp.split()) - len(nar.split())) > max(2, len(nar.split()) // 4):
            warns.append(f"{tag}: speech and narration word counts differ a lot; captions may drift")
        ost = s.get("on_screen_text")
        if ost and word_count(strip_markup(ost)) > 6:
            warns.append(f"{tag}: on_screen_text over 6 words")
        if ost and strip_markup(ost).strip().lower() == nar.lower():
            warns.append(f"{tag}: on_screen_text just repeats narration")
        vis = s.get("visual") or {}
        be = vis.get("backend", "kinetic")
        if be not in BACKENDS:
            errors.append(f"{tag}: visual.backend '{be}' not in {sorted(BACKENDS)}")
        style = vis.get("style") or {}
        if style.get("motion") and style["motion"] not in MOTIONS:
            errors.append(f"{tag}: motion '{style['motion']}' not in {sorted(MOTIONS)}")
        if style.get("decor") and style["decor"] not in DECOR:
            errors.append(f"{tag}: decor '{style['decor']}' not in {sorted(DECOR)}")
        if vis.get("camera") and vis["camera"] not in CAMERAS:
            errors.append(f"{tag}: visual.camera '{vis['camera']}' not in {sorted(CAMERAS)}")
        if vis.get("fit") and vis["fit"] not in FITS:
            errors.append(f"{tag}: visual.fit '{vis['fit']}' not in {sorted(FITS)}")
        if be == "nasa" and not (vis.get("query") or vis.get("nasa_id")):
            warns.append(f"{tag}: nasa backend without visual.query or visual.nasa_id")
        if be == "kenburns" and not vis.get("image"):
            warns.append(f"{tag}: kenburns without visual.image (will fall back to kinetic)")

    if scenes:
        if scenes[0].get("role") != "hook":
            errors.append("scene 1 must have role 'hook'")
        if scenes[-1].get("role") != "cta":
            errors.append("last scene must have role 'cta'")
        if "?" not in scenes[-1].get("narration", ""):
            warns.append("last scene narration has no question mark; end on a direct question")
        hook = scenes[0].get("narration", "").strip()
        if word_count(hook) > 8:
            warns.append("hook narration is long; it must land in <= 2.5 s (8 words max)")
        if hook.lower().startswith(WEAK_OPENERS):
            warns.append("hook opens weakly or depends on another reel; lead with the most shocking claim")
        if ep["hook"].strip() != scenes[0].get("narration", "").strip():
            warns.append("'hook' differs from scene 1 narration")

    if not (MIN_WORDS <= total <= MAX_WORDS):
        errors.append(f"total spoken words {total}; need {MIN_WORDS}-{MAX_WORDS}")

    up = ep["upload"]
    for k in UPLOAD_REQUIRED:
        if not up.get(k):
            errors.append(f"upload.{k} missing")
    if isinstance(up.get("hashtags"), list):
        bad = [h for h in up["hashtags"] if not str(h).startswith("#") or " " in str(h)]
        if bad:
            errors.append(f"upload.hashtags must look like '#tag': {bad}")
    if len(up.get("youtube_title", "")) > 100:
        errors.append("upload.youtube_title over 100 chars")

    angle = ep.get("angle")
    if angle not in ANGLES:
        warns.append(f"angle should be one of {sorted(ANGLES)}")
    if angle in ("news", "event") and not ep.get("sources"):
        warns.append("news/event reels need 'sources' (URLs used to verify the facts and dates)")
    for k in ("cliffhanger_question", "title", "hook", "title_card"):
        if re.search(r"\b(part|episode|ep\.?|stop)\s*#?\d", str(ep.get(k, "")), re.I):
            warns.append(f"{k} mentions a part/episode number; reels must stand alone")
    return errors, warns


def timing_warnings(durations: list[float], total: float) -> list[str]:
    w = []
    if durations and durations[0] > 2.7:
        w.append(f"hook runs {durations[0]:.2f}s (target <= 2.5 s)")
    for i, d in enumerate(durations[1:], 2):
        if d < 1.2 or d > 4.0:
            w.append(f"scene {i} runs {d:.2f}s (target 1.5-3.5 s)")
    if not (25 <= total <= 40):
        w.append(f"total runtime {total:.1f}s (target 25-40 s)")
    return w
