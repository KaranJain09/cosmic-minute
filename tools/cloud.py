#!/usr/bin/env python
"""Cloud publishing helpers. Video files live in GitHub Releases; scripts and history stay in git.

  python tools/cloud.py render              # render pending episodes and publish them (GitHub Actions)
  python tools/cloud.py publish             # upload local videos that have no release yet
  python tools/cloud.py site                # build the web app into _site/
  python tools/cloud.py archive             # list what would be archived (changes nothing)
  python tools/cloud.py archive --delete    # download, verify, then remove from GitHub
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import load_config  # noqa: E402
from pipeline.ffmpeg import ffmpeg_exe  # noqa: E402
from pipeline.metadata import upload_fields  # noqa: E402

HISTORY = ROOT / "series_history.json"
ARCHIVE = ROOT / "Video Archive"
PREVIEW = "preview.m4v"
MAX_PREVIEW_BYTES = 800_000_000


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed:\n{r.stderr[-1500:]}")
    return r


def history() -> dict:
    return json.loads(HISTORY.read_text(encoding="utf-8"))


def tag(n: int) -> str:
    return f"ep-{n:03d}"


def releases() -> dict[str, dict]:
    """All episode releases keyed by tag, with their assets."""
    out = gh("api", "--paginate", "--slurp", "repos/{owner}/{repo}/releases").stdout
    pages = json.loads(out)
    return {r["tag_name"]: r for page in pages for r in page if r["tag_name"].startswith("ep-")}


def make_poster(video: Path, out: Path) -> None:
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=540:-2", "-q:v", "4", str(out)], check=True)


def make_preview(video: Path, out: Path) -> None:
    """Small H.264 copy for in-page playback. Named .m4v so the archive only treats full videos as .mp4."""
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:-2",
                    "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast", "-crf", "28",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-ac", "2",
                    "-movflags", "+faststart", "-f", "mp4", str(out)], check=True)


def ensure_previews() -> None:
    for t, r in sorted(releases().items()):
        names = {a["name"] for a in r["assets"]}
        full = next((n for n in names if n.endswith(".mp4")), None)
        if not full or PREVIEW in names:
            continue
        with tempfile.TemporaryDirectory() as d:
            gh("release", "download", t, "--pattern", full, "--dir", d)
            out = Path(d) / PREVIEW
            make_preview(Path(d) / full, out)
            gh("release", "upload", t, str(out))
        print(f"✓ preview added to {t}")


def copy_previews(rel: dict[str, dict], out: Path) -> dict[str, dict]:
    """Copy previews into the site, newest first, staying well under the 1 GB Pages limit."""
    target = out / "previews"
    target.mkdir(exist_ok=True)
    found: dict[str, dict] = {}
    used = 0
    for t, r in sorted(rel.items(), reverse=True):
        assets = {a["name"]: a for a in r["assets"]}
        if PREVIEW not in assets or used + assets[PREVIEW]["size"] > MAX_PREVIEW_BYTES:
            continue
        gh("release", "download", t, "--pattern", PREVIEW, "--output", str(target / f"{t}.mp4"), "--clobber")
        used += assets[PREVIEW]["size"]
        item = {"preview": f"previews/{t}.mp4"}
        if "poster.jpg" in assets:
            gh("release", "download", t, "--pattern", "poster.jpg", "--output", str(target / f"{t}.jpg"), "--clobber")
            item["poster"] = f"previews/{t}.jpg"
        found[t] = item
    return found


def publish_episode(e: dict, existing: dict[str, dict]) -> bool:
    n = e["episode_number"]
    if tag(n) in existing or not e.get("output_file"):
        return False
    video = ROOT / e["output_file"]
    if not video.exists():
        return False
    with tempfile.TemporaryDirectory() as d:
        poster = Path(d) / "poster.jpg"
        make_poster(video, poster)
        gh("release", "create", tag(n), str(video), str(poster), "--title", f"Episode {n}: {e['title']}",
           "--notes", e.get("summary", ""), "--latest=false")
    print(f"✓ published {tag(n)}")
    return True


def cmd_render(_: argparse.Namespace) -> int:
    failed = 0
    for e in history()["episodes"]:
        if e.get("status") == "rendered":
            continue
        script = e.get("script_file") or f"scripts/episode_{e['episode_number']}.json"
        print(f"→ rendering episode {e['episode_number']}")
        r = subprocess.run([sys.executable, "build_video.py", "--script", script, "--force"], cwd=ROOT)
        if r.returncode != 0:
            print(f"✗ episode {e['episode_number']} failed")
            failed += 1
    existing = releases()
    for e in history()["episodes"]:
        if e.get("status") == "rendered":
            publish_episode(e, existing)
    ensure_previews()
    return 1 if failed else 0


def cmd_publish(_: argparse.Namespace) -> int:
    existing = releases()
    count = sum(publish_episode(e, existing) for e in history()["episodes"] if e.get("status") == "rendered")
    print(f"{count} episode(s) uploaded")
    return 0


def site_data(rel: dict[str, dict], previews: dict[str, dict]) -> dict:
    cfg = load_config()
    h = history()
    items = []
    for e in sorted(h["episodes"], key=lambda x: x["episode_number"], reverse=True):
        n = e["episode_number"]
        script = ROOT / (e.get("script_file") or f"scripts/episode_{n}.json")
        if not script.exists():
            continue
        ep = json.loads(script.read_text(encoding="utf-8"))
        assets = {a["name"]: a for a in rel.get(tag(n), {}).get("assets", [])}
        name = Path(e["output_file"]).name if e.get("output_file") else ""
        video = assets.get(name)
        local = previews.get(tag(n), {})
        state = "ready" if video else ("archived" if e.get("status") == "rendered" else e.get("status", "scripted"))
        items.append({
            "number": n, "title": e["title"], "state": state, "created_at": e.get("created_at"),
            "duration": e.get("duration_sec"), "file": name,
            "video_url": video["browser_download_url"] if video else None,
            "preview_url": local.get("preview"),
            "poster_url": local.get("poster"),
            "text": upload_fields(ep, cfg),
        })
    return {"series": h.get("series_title", ""), "episodes": items}


def cmd_site(a: argparse.Namespace) -> int:
    out = ROOT / "_site"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(ROOT / "site", out)
    rel = {} if a.offline else releases()
    previews = copy_previews(rel, out) if rel else {}
    (out / "episodes.json").write_text(json.dumps(site_data(rel, previews), ensure_ascii=False), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    print(f"✓ site built: {out}")
    return 0


def cmd_archive(a: argparse.Namespace) -> int:
    rel = releases()
    if not rel:
        print("Nothing to archive.")
        return 0
    total = sum(x["size"] for r in rel.values() for x in r["assets"])
    print(f"{len(rel)} episode release(s), {total / 1e6:.0f} MB on GitHub")
    if not a.delete:
        for t in sorted(rel):
            print(" ", t)
        print("Nothing changed. Add --delete to download, verify, then remove these from GitHub.")
        return 0
    ARCHIVE.mkdir(exist_ok=True)
    removed = 0
    for t, r in sorted(rel.items()):
        videos = [x for x in r["assets"] if x["name"].endswith(".mp4")]
        if not videos:
            print(f"! {t}: no video asset, left alone")
            continue
        gh("release", "download", t, "--pattern", "*.mp4", "--dir", str(ARCHIVE), "--clobber")
        if not all((ARCHIVE / v["name"]).is_file() and (ARCHIVE / v["name"]).stat().st_size == v["size"]
                   for v in videos):
            print(f"✗ {t}: download did not verify, NOT deleted")
            continue
        gh("release", "delete", t, "--yes", "--cleanup-tag")
        removed += 1
        print(f"✓ {t}: saved to {ARCHIVE.name} and removed from GitHub")
    gh("workflow", "run", "render.yml", check=False)  # refresh the web app
    print(f"{removed} episode(s) archived. History and scripts stay on GitHub.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("publish").set_defaults(fn=cmd_publish)
    s = sub.add_parser("site")
    s.add_argument("--offline", action="store_true", help="skip GitHub lookup (local preview)")
    s.set_defaults(fn=cmd_site)
    c = sub.add_parser("archive")
    c.add_argument("--delete", action="store_true", help="download, verify, then remove from GitHub")
    c.set_defaults(fn=cmd_archive)
    a = ap.parse_args()
    os.chdir(ROOT)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
