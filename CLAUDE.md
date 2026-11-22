# CLAUDE.md — Automated Short-Form Video Pipeline

Builds 2 vertical short videos per day (YouTube Shorts + Instagram Reels), each one an episode in a continuing series.
Claude Code writes each episode. A deterministic Python pipeline renders it.

> **No `ANTHROPIC_API_KEY` anywhere.** Claude Code (running on the user's Claude Pro plan) does all creative work: topic choice, script, metadata.
> Python never calls an LLM.

---

## 1. Directory layout

```
Uploading_Videos/                 # project root (Windows: C:\Users\Karan\Uploading_Videos)
├── CLAUDE.md                     # this file: architecture + rules
├── series_history.json           # series memory (source of truth for continuity)
├── config.yaml                   # channel niche, voice, visual style, music, toggles
├── pyproject.toml                # deps (uv sync)
├── build_video.py                # CLI entry: uv run build_video.py --script scripts/episode_X.json
├── preview_visuals.py            # contact sheet of NASA image candidates per scene (Claude checks it)
├── voice_samples.py              # renders the same line in every candidate voice
├── .claude/commands/next-episode.md  # /next-episode [n]: Step A + B for n episodes (default 2); copy from claude-commands/
├── pipeline/
│   ├── config.py, ffmpeg.py      # config/env loading; ALL ffmpeg calls (PATH ffmpeg or imageio-ffmpeg)
│   ├── schema.py                 # validation of episode JSON (errors block, warnings print)
│   ├── history.py                # series_history.json upsert (atomic)
│   ├── tts/                      # voice backends (common interface)
│   │   ├── base.py               # TTSBackend.synthesize(text, out_path) -> (path, duration, word_timings)
│   │   ├── kokoro_tts.py         # Kokoro-82M: free, local, most human-sounding (word timestamps)
│   │   ├── edge.py               # edge-tts (free, online, word-boundary timings)
│   │   ├── elevenlabs.py         # OPTIONAL: needs ELEVENLABS_API_KEY in .env
│   │   └── dummy.py              # offline test beeps (--tts dummy); never for uploads
│   ├── visuals/                  # visual backends (common interface)
│   │   ├── base.py               # VisualBackend.frames(ctx) -> exactly n_frames RGB images
│   │   ├── common.py             # fonts, *highlight* text, space backgrounds, decor sprites, easing
│   │   ├── overlay.py            # badge, hook title card, on-screen text motion, CTA pills (all backends)
│   │   ├── nasa.py               # DEFAULT: real NASA Image Library photos (no key), cached in build/cache/nasa
│   │   ├── kinetic.py            # drifting nebula/starfield + planet/moon/sun/black-hole decor (fallback)
│   │   ├── kenburns.py           # cinematic still: cover/contain, grade, vignette, zoom/pan camera
│   │   └── stock.py              # OPTIONAL: Pexels/Pixabay clip fetch (needs free API key)
│   ├── captions.py               # 1-3 word chunks drawn on frames (stroke + box + active-word highlight)
│   ├── audio_mix.py              # VO timeline, music ducked -20 dB under speech, whooshes, loudnorm
│   ├── render.py                 # orchestrator: TTS -> timeline -> mix -> frames piped to one ffmpeg encode
│   └── metadata.py               # writes ep_XXX_caption.txt
├── scripts/                      # episode_1.json, episode_2.json, ... (written by Claude Code)
├── assets/
│   ├── music/                    # royalty-free background tracks (user-supplied)
│   ├── fonts/                    # bold display font(s) for title cards + captions
│   └── images/                   # optional per-scene images
├── build/                        # temp per-episode work dirs (safe to wipe)
└── upload videos/                # FINAL OUTPUT ONLY (mp4 + caption txt)
```

---

## 2. Two-step workflow (every episode)

### Step A — Claude Code (Director & Scriptwriter)
When the user says "make the next episode" (or "make today's 2 episodes"):

1. Read `series_history.json` and `config.yaml`.
2. Pick the next topic so it **logically links to the previous episode**:
   answer the last `cliffhanger_question`, continue the overarching story/mystery, or advance the numbered series.
   Never repeat a topic already in history.
3. Write `scripts/episode_{N}.json` following the schema in §3 and the rules in §4.
4. Self-check before saving: word count 110–145, 8–12 scenes, hook ≤ 3 s, last scene is a question/cliffhanger.
   Run `uv run build_video.py --script ... --validate-only`.
4b. **Check the pictures**: `uv run preview_visuals.py --script scripts/episode_{N}.json`, then open
   `build/preview/ep_{N:03d}_visuals.jpg` with the Read tool. Column [0] is what will render. If a picture is wrong
   (people at a podium, a logo, a chart, off-topic, low quality), pin a better candidate with `"nasa_id"` or change the
   `query` and re-run. Every scene should show the thing the narration talks about.
5. Append the episode entry to `series_history.json` (set `status: "scripted"`).
6. Run `python build_video.py --script scripts/episode_{N}.json`.
7. On success, the pipeline sets `status: "rendered"` and `output_file`. On failure, fix the cause, don't hand-edit outputs.

### Step B — Python pipeline (deterministic, no LLM)
`build_video.py --script scripts/episode_X.json`:

1. Validate the JSON against the schema (fail loudly on violations).
2. TTS per scene → `build/ep_X/audio/scene_NN.mp3` + measured duration + word timings.
3. Scene duration = audio duration + `pad_after` (default 0.15 s). **Visuals are timed to audio, never the reverse.**
4. Render each scene's visual clip at exactly that duration (1080×1920, 30 fps).
5. Hard cuts between scenes (with a soft whoosh); frames go straight into one ffmpeg encode.
6. Captions from word timings are drawn onto each frame (no subtitle filter, so no Windows font-path issues).
7. Mix: voiceover + music ducked to −20 dB under speech (sidechain), loudness-normalize to ≈ −14 LUFS.
8. Encode final MP4 → `upload videos/ep_{number:03d}_{slug}.mp4`.
9. Write `upload videos/ep_{number:03d}_caption.txt`.
10. Update `series_history.json` (`status`, `output_file`, `duration_sec`).

---

## 3. Episode JSON schema (`scripts/episode_X.json`)

```json
{
  "episode_number": 1,
  "series_title": "string",
  "title": "string (on-screen + upload title, <= 60 chars)",
  "slug": "kebab-case-slug",
  "topic": "string",
  "links_to_previous": "how this answers/continues the previous episode (or 'series premiere')",
  "hook": "0-3s pattern-interrupt line (also scene 1 narration)",
  "title_card": "BOLD 2-5 WORD TITLE shown during the hook",
  "cliffhanger_question": "polarizing question / teaser for next episode",
  "summary": "1-2 sentence summary for series memory",
  "voice": {},   // optional; config.yaml tts.engine decides. Only applied if "engine" equals that engine
  "music": { "file": "assets/music/track.mp3", "volume_db": -20 },
  "scenes": [
    {
      "id": 1,
      "role": "hook | build | reveal | twist | cta",
      "narration": "spoken text for this scene (6-18 words)",
      "on_screen_text": "short emphasis text (<= 6 words), *stars* = accent color, or null",
      "visual": {
        "backend": "nasa | kinetic | kenburns | stock",
        "query": "NASA/Pexels search text: concrete subject, e.g. 'full moon', 'Saturn rings Cassini'",
        "nasa_id": "optional: pin an exact NASA image (from preview_visuals.py)",
        "fit": "auto | cover | contain   (contain = whole object visible, e.g. full planet disk)",
        "camera": "zoom_in | zoom_out | pan_left | pan_right | pan_up   (photo camera move; default rotates)",
        "prompt": "description of what to show",
        "image": "assets/images/x.jpg (kenburns)", "clip": "local .mp4 (stock)",
        "style": { "motion": "pop|zoom_in|zoom_out|shake|slide_up|words|count|pan_left|pan_right|pan_up",
                   "decor": "auto|none|planet|ring_planet|moon|sun|black_hole" }
      },
      "pad_after": 0.15
    }
  ],
  "upload": {
    "youtube_title": "string (<= 100 chars, includes #Shorts)",
    "instagram_caption": "string",
    "description": "string",
    "pinned_comment": "question that invites replies",
    "hashtags": ["#tag1", "#tag2"]
  }
}
```

---

## 4. Engagement & retention rules (enforced by `schema.py`)

| Rule | Value |
|---|---|
| Length | 45–60 s, 110–145 spoken words total |
| Hook (scene 1) | ≤ 3 s; pattern-interrupt line + bold title card on screen |
| Scenes | 8–12; each 3–5 s (≈ 6–18 words) so visuals change constantly |
| Last scene | `role: "cta"`; direct polarizing question or cliffhanger tied to next episode |
| On-screen text | ≤ 6 words, never a copy of the caption line |
| Language | Short sentences, second person, concrete numbers, no filler intros ("Hey guys", "In this video") |
| Continuity | Every episode after #1 must reference/resolve the previous `cliffhanger_question` |

---

## 5. Video & audio specs

- Container MP4, video **H.264** (`libx264`, `-pix_fmt yuv420p`, `-profile:v high`, CRF 20, `-preset veryfast`), **AAC** 192 kbps 48 kHz, `+faststart`.
- **1080×1920, 30 fps**, constant frame rate.
- Safe zones: keep text out of the top 220 px and bottom 380 px (platform UI). Captions sit at ~62% height, centered.
- Captions: bold sans (e.g. Montserrat ExtraBold / Anton), 64–80 px, white with 6 px black stroke + translucent dark box; 1–3 words per chunk, active word highlighted in accent color.
- Music: −20 dB under speech via sidechain ducking, fade in 0.3 s / out 0.8 s.

---

## 6. Series memory (`series_history.json`)

```json
{
  "series_title": "string",
  "niche": "string",
  "episodes": [
    {
      "episode_number": 1,
      "title": "", "topic": "", "hook": "", "cliffhanger_question": "", "summary": "",
      "script_file": "scripts/episode_1.json",
      "output_file": "upload videos/ep_001_slug.mp4",
      "status": "scripted | rendered | failed",
      "created_at": "ISO-8601"
    }
  ]
}
```
Only Claude Code appends episodes; only the pipeline flips `status` to `rendered`/`failed` and sets `output_file`.

---

## 7. Rules for Claude Code in this repo

1. Never require or read `ANTHROPIC_API_KEY`. Optional third-party keys (ElevenLabs, Pexels, Pixabay) live in `.env` and every feature using them must fall back to a free default.
2. Keep `build_video.py` deterministic: same JSON + same assets → same video.
3. Backends are pluggable: new TTS/visual engines implement the base interface and register in `config.yaml`; never hard-code one engine in `render.py`.
4. All FFmpeg calls go through `pipeline/render.py` helpers; check return codes and surface stderr.
5. Paths use `pathlib`; the output folder name contains a space (`upload videos`) — always quote it.
6. Must run on Windows (PowerShell) with Python 3.10+ via `uv`; no bash-only commands in the pipeline.
7. Only finished MP4s and caption `.txt` files go into `upload videos/`; temp files go in `build/`.
8. Don't overwrite an existing `ep_XXX` output — bump the episode number or ask.
9. Use only royalty-free music/assets the user has placed in `assets/`; never download copyrighted music.
10. Daily target: 2 episodes. Run Step A + Step B for episode N, then N+1.

11. Test without network: `uv run build_video.py --script scripts/episode_X.json --tts dummy --force` (then re-render with the real voice).

### Commands
```powershell
uv sync                                                        # first time: install deps
uv run build_video.py --script scripts/episode_1.json            # render
uv run build_video.py --script scripts/episode_1.json --validate-only
uv run build_video.py --script scripts/episode_1.json --force    # re-render over existing output
```
Motion notes: `count` animates the first number in on_screen_text from 0; `words` reveals it word by word.
The hook scene shows `title_card` as a tilted yellow card plus a white flash on frame 1; the cta scene adds the
"COMMENT YOUR ANSWER" + "FOLLOW FOR PART N+1" pills automatically.

---

## 8. Channel settings (filled in from user answers)

- **Niche: Space & science.** One overarching series (e.g. "Universe Files #N"): each episode answers the previous cliffhanger and opens a new, bigger question. Facts must be accurate; flag uncertain or speculative claims as such in narration ("scientists think…").
- **Voice: edge-tts `en-US-AvaMultilingualNeural` (female, chosen by the user), rate +5%.** Set only in `config.yaml` (`tts.engine` + voice).
  Alternatives: Kokoro (local), edge Indian English (`en-IN-PrabhatNeural` / `en-IN-NeerjaNeural`) or edge Multilingual US voices. ElevenLabs optional.
- **Visual style: real NASA imagery (backend `nasa`) with kinetic text on top.** Every scene gets a concrete `query`.
  Kinetic look (used as fallback / for abstract scenes): Deep-space palette: near-black/indigo gradient backgrounds with a subtle starfield and parallax drift, accent colors `#FFD400` (highlight) and `#4FC3F7` (cyan), bold condensed display font, pop/zoom/shake text animations, simple vector shapes (planets, orbits, arrows, counters) for numbers and scale comparisons. `kenburns`/`stock` remain optional per scene.
