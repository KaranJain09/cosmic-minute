"""series_history.json helpers (atomic writes)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["episode_number", "title", "topic", "hook", "cliffhanger_question", "summary"]


def load(path: Path) -> dict:
    if not path.exists():
        return {"series_title": "", "niche": "", "episodes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def upsert(path: Path, ep: dict, script_file: str, **updates) -> None:
    data = load(path)
    eps = data.setdefault("episodes", [])
    entry = next((e for e in eps if e.get("episode_number") == ep["episode_number"]), None)
    if entry is None:
        entry = {k: ep.get(k, "") for k in FIELDS}
        entry.update(script_file=script_file, output_file=None, status="scripted",
                     created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        eps.append(entry)
        eps.sort(key=lambda e: e["episode_number"])
    entry.update({k: ep.get(k, entry.get(k)) for k in FIELDS})
    entry.update(updates)
    save(path, data)
