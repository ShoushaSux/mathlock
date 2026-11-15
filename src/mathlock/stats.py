"""Per-lock-session stats (wrong attempts etc.), appended as JSON lines."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


def default_stats_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "MathLock" / "stats.jsonl"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "mathlock" / "stats.jsonl"


@dataclass
class Session:
    started: str  # ISO 8601
    ended: str
    solved: int
    wrong: int
    escaped: bool = False  # True if the debug escape hotkey was used


def record(session: Session, path: Path | None = None) -> None:
    path = path or default_stats_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(session)) + "\n")
    except OSError as exc:  # stats must never break the lock screen
        print(f"[mathlock] could not write stats to {path}: {exc}", file=sys.stderr)


def total_wrong(path: Path | None = None) -> int:
    path = path or default_stats_path()
    total = 0
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    total += int(json.loads(line).get("wrong", 0))
                except (ValueError, AttributeError):
                    continue  # skip corrupt lines
    except OSError:
        return 0
    return total
