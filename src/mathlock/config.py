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
    gif_dir: str = "assets/gifs"
    gif_grace: int = 1
    gif_growth: float = 1.6
    max_gifs: int = 25
    gif_min_size: int = 120
    gif_max_size: int = 360
    gif_max_rotation: float = 180
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
    if cfg.gif_grace < 0 or cfg.max_gifs < 0 or cfg.gif_growth < 1:
        raise ValueError("gif_grace/max_gifs must be >= 0 and gif_growth >= 1")
    if not 16 <= cfg.gif_min_size <= cfg.gif_max_size:
        raise ValueError("need 16 <= gif_min_size <= gif_max_size")
    if not 0 <= cfg.gif_max_rotation <= 180:
        raise ValueError("gif_max_rotation must be 0-180 degrees")
    gif_dir = Path(cfg.gif_dir)
    if not gif_dir.is_absolute():
        cfg = replace(cfg, gif_dir=str(base_dir / gif_dir))
    return cfg
