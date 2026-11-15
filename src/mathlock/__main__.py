"""Entry point: `python -m mathlock [--now] [--config-dir DIR]`."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import MathLockApp
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="mathlock")
    parser.add_argument("--now", action="store_true", help="show the lock screen immediately")
    parser.add_argument("--config-dir", type=Path, default=None,
                        help="directory containing config.toml (default: cwd)")
    args = parser.parse_args()

    cfg = load_config(args.config_dir)
    MathLockApp(cfg).run(lock_now=args.now)


if __name__ == "__main__":
    main()
