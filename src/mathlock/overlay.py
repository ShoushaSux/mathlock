"""The lock-screen window. Lives in its own process/window; never touches the game."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from . import problems, winutil
from .config import Config

REFOCUS_MS = 150  # how often we re-assert topmost + focus

BG, FG, ACCENT, BAD, GOOD = "#11131a", "#e8e8f0", "#7aa2f7", "#f7768e", "#9ece6a"


class Overlay(tk.Toplevel):
    def __init__(self, master: tk.Misc, cfg: Config, on_unlock: Callable[[], None]):
        super().__init__(master)
        self.cfg = cfg
        self.on_unlock = on_unlock
        self.solved = 0
        self.problem = problems.generate(cfg.difficulty)
        self._refocus_job: str | None = None

        self._make_unclosable()
        self._build_ui()
        self._next_problem(first=True)
        self._hwnd = winutil.hwnd_for(self)
        self._keep_on_top()

    # -- window behaviour -------------------------------------------------
    def _make_unclosable(self) -> None:
        self.configure(bg=BG)
        self.title("MathLock")
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # X button / Alt+F4 / WM_CLOSE
        self.bind_all("<Alt-F4>", lambda e: "break")

        if self.cfg.debug:
            # Dev mode: normal-ish window so you can't lock yourself out while iterating.
            self.geometry("700x420+100+100")
            self.attributes("-topmost", True)
            self.bind_all("<Control-Shift-F12>", lambda e: self._unlock())
        else:
            x, y, w, h = winutil.virtual_screen_rect(self)
            self.overrideredirect(True)  # no title bar / close button / taskbar entry
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.attributes("-topmost", True)

    def _keep_on_top(self) -> None:
        """Our window can lose focus (Alt+Tab, Win key); just take it back.
        We don't block those keys -- that would require a global hook."""
        self.lift()
        self.attributes("-topmost", True)
        winutil.force_foreground(self._hwnd)
        self.entry.focus_force()
        self._refocus_job = self.after(REFOCUS_MS, self._keep_on_top)

    # -- UI ---------------------------------------------------------------
    def _build_ui(self) -> None:
        frame = tk.Frame(self, bg=BG)
        frame.place(relx=0.5, rely=0.5, anchor="center")

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

        self.feedback = tk.Label(frame, font=("Segoe UI", 14), fg=FG, bg=BG)
        self.feedback.pack(pady=12)

        if self.cfg.debug:
            tk.Label(frame, text="DEBUG: Ctrl+Shift+F12 to escape", font=("Segoe UI", 10),
                     fg=BAD, bg=BG).pack()

    def _next_problem(self, first: bool = False) -> None:
        if not first:
            self.problem = problems.generate(self.cfg.difficulty)
        self.question.config(text=f"{self.problem.prompt} = ?")
        self.progress.config(text=f"Solved {self.solved} / {self.cfg.problems_required}")
        self.answer.set("")

    def _submit(self, _event=None) -> str:
        if self.problem.check(self.answer.get()):
            self.solved += 1
            if self.solved >= self.cfg.problems_required:
                self._unlock()
                return "break"
            self.feedback.config(text="Correct!", fg=GOOD)
        else:
            self.feedback.config(text=f"Nope — it was {self.problem.answer}. Try another.", fg=BAD)
        self._next_problem()
        return "break"

    def _unlock(self) -> None:
        if self._refocus_job:
            self.after_cancel(self._refocus_job)
        self.unbind_all("<Alt-F4>")
        self.unbind_all("<Control-Shift-F12>")
        self.destroy()
        self.on_unlock()
