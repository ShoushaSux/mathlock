"""Configuration loading (config.toml, overridden by config.local.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class Config:
    interval_minutes: float = 30
    problems_required: int = 3
    difficulty: int = 2
    background_opacity: float = 0.15
    debug: bool = False


def load_config(base_dir: Path | None = None) -> Config:
    base_dir = base_dir or Path.cwd()
    cfg = Config()
    known = {f.name for f in fields(Config)}
    for name in ("config.toml", "config.local.toml"):
        path = base_dir / name
        if path.is_file():
            with path.open("rb") as fh:
                data = tomllib.load(fh)
            cfg = replace(cfg, **{k: v for k, v in data.items() if k in known})
    if not 1 <= cfg.difficulty <= 3:
        raise ValueError(f"difficulty must be 1-3, got {cfg.difficulty}")
    if cfg.problems_required < 1:
        raise ValueError("problems_required must be >= 1")
    if not 0 < cfg.background_opacity <= 1:
        raise ValueError("background_opacity must be in (0, 1]")
    return cfg
