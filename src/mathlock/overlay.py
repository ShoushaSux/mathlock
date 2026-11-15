"""The lock-screen window. Lives in its own process/window; never touches the game."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import problems, stats, winutil
from .gifs import GifSwarm
from .config import Config

REFOCUS_MS = 150  # how often we re-assert topmost + focus

BG, FG, ACCENT, BAD, GOOD = "#11131a", "#e8e8f0", "#7aa2f7", "#f7768e", "#9ece6a"


class Overlay(tk.Toplevel):
    def __init__(self, master: tk.Misc, cfg: Config, on_unlock: Callable[[], None]):
        super().__init__(master)
        self.cfg = cfg
        self.on_unlock = on_unlock
        self.solved = 0
        self.wrong = 0
        self.lifetime_wrong = stats.total_wrong()
        self.started = datetime.now()
        self.problem = problems.generate(cfg.difficulty)
        self._refocus_job: str | None = None

        # Two windows: a translucent full-screen backdrop (game stays visible, but clicks
        # land on us, not the game) and this opaque panel on top holding the question.
        # Tk's -alpha applies to a whole window, so one window can't do both.
        self.backdrop = self._make_backdrop(master)
        self._make_unclosable()
        self.gifs = GifSwarm(
            master, Path(cfg.gif_dir), winutil.virtual_screen_rect(self.backdrop),
            max_windows=cfg.max_gifs, grace=cfg.gif_grace, growth=cfg.gif_growth,
            min_size=cfg.gif_min_size, max_size=cfg.gif_max_size,
            max_rotation=cfg.gif_max_rotation,
            on_click=lambda: self.entry.focus_force(),
            log=(lambda m: print(f"[mathlock] {m}")) if cfg.debug else (lambda m: None),
        )
        self._build_ui()
        self._next_problem(first=True)
        self._hwnd = winutil.hwnd_for(self)
        self._keep_on_top()

    # -- window behaviour -------------------------------------------------
    def _make_backdrop(self, master: tk.Misc) -> tk.Toplevel:
        backdrop = tk.Toplevel(master, bg="black", cursor="arrow")
        backdrop.protocol("WM_DELETE_WINDOW", lambda: None)
        x, y, w, h = winutil.virtual_screen_rect(backdrop)
        backdrop.overrideredirect(True)
        backdrop.geometry(f"{w}x{h}+{x}+{y}")
        backdrop.attributes("-topmost", True)
        # Must stay > 0: a fully transparent window would let clicks reach the game.
        opacity = max(0.01, self.cfg.background_opacity)
        backdrop.attributes("-alpha", opacity)
        backdrop.bind("<Button>", lambda e: self.entry.focus_force())

        # Re-apply once the window really exists on screen (see winutil.set_window_opacity).
        backdrop.update()
        hwnd = winutil.hwnd_for(backdrop)
        winutil.set_window_opacity(hwnd, opacity)
        backdrop.attributes("-alpha", opacity)
        if self.cfg.debug:
            actual = winutil.get_window_opacity(hwnd)
            print(f"[mathlock] backdrop opacity: requested {opacity}, "
                  f"tk reports {backdrop.attributes('-alpha')}, windows reports {actual}")
        return backdrop

    def _make_unclosable(self) -> None:
        self.configure(bg=BG, padx=40, pady=30)
        self.title("MathLock")
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # X button / Alt+F4 / WM_CLOSE
        self.bind_all("<Alt-F4>", lambda e: "break")
        self.attributes("-topmost", True)

        if self.cfg.debug:
            # Dev mode: keeps the title bar and adds an escape hotkey.
            self.bind_all("<Control-Shift-F12>", lambda e: self._unlock(escaped=True))
        else:
            self.overrideredirect(True)  # no title bar / close button / taskbar entry

    def _center_on_primary(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _keep_on_top(self) -> None:
        """Our windows can lose focus (Alt+Tab, Win key); just take it back.
        We don't block those keys -- that would require a global hook."""
        self.backdrop.lift()
        self.backdrop.attributes("-topmost", True)
        self.gifs.lift_all()  # GIFs above backdrop...
        self.lift()  # ...panel above everything
        self.attributes("-topmost", True)
        winutil.force_foreground(self._hwnd)
        self.entry.focus_force()
        self._refocus_job = self.after(REFOCUS_MS, self._keep_on_top)

    # -- UI ---------------------------------------------------------------
    def _build_ui(self) -> None:
        frame = tk.Frame(self, bg=BG)
        frame.pack()

        tk.Label(frame, text="Brain break!", font=("Segoe UI", 28, "bold"),
                 fg=ACCENT, bg=BG).pack(pady=(0, 8))
        self.progress = tk.Label(frame, font=("Segoe UI", 14), fg=FG, bg=BG)
        self.progress.pack()
        self.question = tk.Label(frame, font=("Segoe UI", 48, "bold"), fg=FG, bg=BG)
        self.question.pack(pady=24)

        self.answer = tk.StringVar()
        self.entry = tk.Entry(frame, textvariable=self.answer, font=("Segoe UI", 32),
                              width=8, justify="center", bg="#1f2335", fg=FG,
                              insertbackground=FG, relief="flat")
        self.entry.pack()
        self.entry.bind("<Return>", self._submit)

        self.feedback = tk.Label(frame, font=("Segoe UI", 14), fg=FG, bg=BG, width=40)
        self.feedback.pack(pady=12)

        if self.cfg.debug:
            tk.Label(frame, text="DEBUG: Ctrl+Shift+F12 to escape", font=("Segoe UI", 10),
                     fg=BAD, bg=BG).pack()
        self._center_on_primary()

    def _next_problem(self, first: bool = False) -> None:
        if not first:
            self.problem = problems.generate(self.cfg.difficulty)
        self.question.config(text=f"{self.problem.prompt} = ?")
        self.progress.config(
            text=f"Solved {self.solved} / {self.cfg.problems_required}    "
                 f"Wrong: {self.wrong}    (all-time: {self.lifetime_wrong + self.wrong})")
        self.answer.set("")

    def _submit(self, _event=None) -> str:
        if self.problem.check(self.answer.get()):
            self.solved += 1
            if self.solved >= self.cfg.problems_required:
                self._unlock()
                return "break"
            self.feedback.config(text="Correct!", fg=GOOD)
        else:
            self.wrong += 1
            self.gifs.update_for(self.wrong)
            self.feedback.config(text=f"Nope — it was {self.problem.answer}. Try another.", fg=BAD)
        self._next_problem()
        return "break"

    def _unlock(self, escaped: bool = False) -> None:
        if self._refocus_job:
            self.after_cancel(self._refocus_job)
        stats.record(stats.Session(
            started=self.started.isoformat(timespec="seconds"),
            ended=datetime.now().isoformat(timespec="seconds"),
            solved=self.solved, wrong=self.wrong, escaped=escaped,
        ))
        self.gifs.destroy_all()
        self.unbind_all("<Alt-F4>")
        self.unbind_all("<Control-Shift-F12>")
        self.backdrop.destroy()
        self.destroy()
        self.on_unlock()
