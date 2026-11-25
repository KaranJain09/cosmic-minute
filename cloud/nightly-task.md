# Nightly reel task (runs in Claude's cloud at 4 AM India time)

You write the scripts only. GitHub Actions renders and publishes them.
In this cloud environment, run Python with this prefix instead of `uv run`:

`uv run --no-project --python 3.12 --with-requirements requirements-cloud.txt`

1. Read `CLAUDE.md`, `config.yaml`, `series_history.json` and `claude-commands/next-episode.md` (the full playbook).
2. If any entry has `status: "failed"`, fix its script if the error is caused by the script, set its status to
   `"scripted"`, remove its `error` field, push to `main`, and stop. Write no new reels that night.
3. If any entry has `status: "scripted"`, it is still waiting to render. Stop without changes.
4. Otherwise write 2 new standalone reels by following steps 1 to 5 of `claude-commands/next-episode.md`:
   - Use WebSearch (and WebFetch when needed) to find this week's space news and the space events of the next
     14 days. Today's date is in your system reminder; use it. Make one reel news/event and one evergreen when possible.
   - Verify news and dates in 2 reputable sources and list them in `sources`.
   - Run validation with `build_video.py --validate-only` and the picture check with `preview_visuals.py`.
   - Do NOT run the full render.
   If NASA cannot be reached and the pictures cannot be checked, stop, push nothing, and report that the
   environment must allow `images-api.nasa.gov` and `images-assets.nasa.gov`.
5. Commit only `scripts/episode_*.json` and `series_history.json`, then push directly to the `main` branch.
   If the push is rejected, run `git pull --rebase origin main` and push again.
6. Report the episode numbers, topic type, hook lines, and the sources used.
