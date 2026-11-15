"""Hidden Tk root that schedules lock screens on a timer."""

from __future__ import annotations

import tkinter as tk

from . import winutil
from .config import Config
from .overlay import Overlay


class MathLockApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        winutil.enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()  # root is invisible; overlays are Toplevels
        self.overlay: Overlay | None = None

    def run(self, lock_now: bool = False) -> None:
        if lock_now:
            self.root.after(0, self.lock)
        else:
            self._schedule_next()
        self.root.mainloop()

    def _schedule_next(self) -> None:
        ms = int(self.cfg.interval_minutes * 60_000)
        print(f"[mathlock] next lock in {self.cfg.interval_minutes} min")
        self.root.after(ms, self.lock)

    def lock(self) -> None:
        if self.overlay is None:
            self.overlay = Overlay(self.root, self.cfg, on_unlock=self._unlocked)

    def _unlocked(self) -> None:
        self.overlay = None
        self._schedule_next()
