"""Writes the companion upload text file for YouTube Shorts + Instagram Reels."""
from __future__ import annotations

from pathlib import Path


def _tags(ep: dict, cfg: dict) -> list[str]:
    seen, out = set(), []
    for t in list(ep["upload"].get("hashtags", [])) + cfg["channel"].get("default_hashtags", []):
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def upload_fields(ep: dict, cfg: dict) -> dict:
    """The exact text to paste into each platform (used by the web app)."""
    up = ep["upload"]
    tags = _tags(ep, cfg)
    yt_title = up["youtube_title"]
    if "#shorts" not in yt_title.lower():
        yt_title = (yt_title + " #Shorts")[:100]
    ch = cfg["channel"]
    yt_handle = ch.get("youtube_handle") or ch.get("handle", "")
    ig_handle = ch.get("instagram_handle") or ch.get("handle", "")
    series = ep.get("series_title") or ch["series_title"]
    n = ep["episode_number"]
    return {
        "youtube_title": yt_title,
        "youtube_description": (
            f"{up['description']}\n\n{series} - Episode {n}. Follow {yt_handle} for Part {n + 1}. "
            f"Instagram: {ig_handle}\n\n{' '.join(tags[:5])}"
        ),
        "instagram_caption": (
            f"{up['instagram_caption']}\n\n{series} - Ep {n} | Part {n + 1} drops next. "
            f"Follow {ig_handle} | YouTube: {yt_handle}\n\n{' '.join(tags[:15])}"
        ),
        "pinned_comment": up["pinned_comment"],
        "hashtags": " ".join(tags),
    }


def write_caption_file(ep: dict, cfg: dict, path: Path, video_name: str, duration: float) -> None:
    up = ep["upload"]
    tags = _tags(ep, cfg)
    yt_title = up["youtube_title"]
    if "#shorts" not in yt_title.lower():
        yt_title = (yt_title + " #Shorts")[:100]
    yt_tags = " ".join(tags[:5])        # YouTube shows first 3 above the title; keep it tight
    ig_tags = " ".join(tags[:15])
    ch = cfg["channel"]
    yt_handle = ch.get("youtube_handle") or ch.get("handle", "")
    ig_handle = ch.get("instagram_handle") or ch.get("handle", "")
    series = ep.get("series_title") or cfg["channel"]["series_title"]
    n = ep["episode_number"]

    text = f"""=============== YOUTUBE SHORTS ===============
TITLE:
{yt_title}

DESCRIPTION:
{up['description']}

{series} - Episode {n}. Follow {yt_handle} for Part {n + 1}. Instagram: {ig_handle}

{yt_tags}

=============== INSTAGRAM REELS ===============
CAPTION:
{up['instagram_caption']}

{series} - Ep {n} | Part {n + 1} drops next. Follow {ig_handle} | YouTube: {yt_handle}

{ig_tags}

=============== PINNED COMMENT (both) ===============
{up['pinned_comment']}

=============== HASHTAGS (all) ===============
{' '.join(tags)}

--------------------------------------------
file: {video_name}
duration: {duration:.1f}s | 1080x1920 | 30fps
cliffhanger: {ep['cliffhanger_question']}
"""
    path.write_text(text, encoding="utf-8")
