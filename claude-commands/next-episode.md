---
description: Write and render the next linked episode(s). Usage: /next-episode [count, default 2]
---

Make $ARGUMENTS new episode(s) of the series (if no number was given, make 2: today's daily quota). For EACH episode, in order:

1. Read `CLAUDE.md`, `config.yaml` and `series_history.json`. Find the highest `episode_number` (N). The new episode is N+1.
   If the last episode has `status: "failed"` or `"scripted"`, fix and render that one first instead of writing a new one.
2. Read the last episode's script (`scripts/episode_N.json`). The new episode MUST open by answering its `cliffhanger_question`
   (state the answer within the first 2 scenes) and continue the series `arc` in `series_history.json`. Don't repeat a topic.
3. Write `scripts/episode_{N+1}.json` following the schema in CLAUDE.md §3 and the rules in §4:
   - 110–145 spoken words, 8–12 scenes, hook ≤ 9 words, last scene role `cta` ending in a polarizing question that sets up episode N+2.
   - Space & science facts must be accurate. Use round, well-established figures; say "about"/"scientists think" for estimates.
   - Write numbers in narration the way they should be spoken; put punchy numbers in `on_screen_text` with `*highlight*` markup.
   - Vary `motion` and `decor` across scenes; use `count` motion when on_screen_text has a number.
   - Every scene: `"backend": "nasa"` with a concrete `query` naming the real object/mission (e.g. "Venus Magellan radar
     globe", "Mars Hubble", "Sun SDO ultraviolet"). Use `"fit": "contain"` for whole planets/moons/stars.
4. Validate: `uv run build_video.py --script scripts/episode_{N+1}.json --validate-only`. Fix every error and warning you reasonably can.
4b. Pictures: `uv run preview_visuals.py --script scripts/episode_{N+1}.json`, open `build/preview/ep_XXX_visuals.jpg`
   with the Read tool and make sure column [0] of each row matches the narration. Pin better ones with `"nasa_id"`
   or rewrite the query, re-run until every scene looks right (no podium photos, logos, charts or off-topic shots).
5. Append the episode to `series_history.json` (`status: "scripted"`, `output_file: null`).
6. Render: `uv run build_video.py --script scripts/episode_{N+1}.json`.
   If runtime warnings say the video is under 45 s or over 60 s, adjust the narration and re-render with `--force`.
7. Report: the output file in `upload videos/`, the runtime, and the cliffhanger for the next episode.
