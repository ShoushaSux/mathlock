"""Animated GIF "punishment" windows that pile up as wrong answers increase.

* How many: ``target_count`` -- grows roughly exponentially with wrong answers instead of
  one-per-mistake, so a couple of slips are mild and repeated guessing gets chaotic.
* How they look: every window gets a random size, rotation and mirroring.
* Each GIF is its own small borderless topmost window that WE own -- nothing touches the game.

Pillow does the decoding (it composites optimized GIF frames correctly; Tk alone doesn't)
and the resizing/rotation. That work runs on a background thread so the lock screen (and
its refocus loop) never freezes; only the final hand-off to Tk happens on the UI thread.
Pure image work is kept separate from Tk so it's unit-testable.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps, ImageSequence, ImageTk

from .winutil import IS_WINDOWS

DEFAULT_DELAY_MS = 100
MIN_DELAY_MS = 20      # 0/10ms delays are treated as "default" by browsers too
MAX_FRAMES = 40        # long GIFs are thinned to this many frames to bound memory
MAX_VARIANTS = 12      # distinct size/rotation renders kept; beyond this, reuse them
SPAWN_STAGGER_MS = 90  # several new GIFs pop in one by one, not all in one frame
POLL_MS = 30           # how often the UI thread checks for finished background renders

# Windows can make one exact colour fully transparent (and click-through to our own
# backdrop). Rotated corners and transparent GIF pixels are painted this colour.
KEY_COLOR = (255, 0, 254)
KEY_HEX = "#ff00fe"


def target_count(wrong: int, grace: int, growth: float, max_windows: int) -> int:
    """How many GIFs should be on screen after `wrong` wrong answers.

    The first `grace` mistakes are free; after that the total grows by ~`growth`x per
    mistake (1.6 -> 1, 2, 3, 4, 7, 10, 17, 27, ...), capped at `max_windows`.
    """
    over = wrong - grace
    if over <= 0 or max_windows <= 0:
        return 0
    return min(max_windows, math.floor(growth ** (over - 1) + 0.5) if growth > 1 else over)


def find_gifs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".gif")


def load_frames(path: Path, max_size: int,
                max_frames: int = MAX_FRAMES) -> tuple[list[Image.Image], list[int]]:
    """Decode a GIF into RGBA frames (longest side <= max_size) plus per-frame delays (ms)."""
    frames: list[Image.Image] = []
    delays: list[int] = []
    with Image.open(path) as im:
        if getattr(im, "format", None) != "GIF":
            raise ValueError("not a GIF file")
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert("RGBA")
            rgba.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            frames.append(rgba)
            d = int(frame.info.get("duration") or 0)
            delays.append(d if d >= MIN_DELAY_MS else DEFAULT_DELAY_MS)
    if not frames:
        raise ValueError("no frames")

    if len(frames) > max_frames:  # keep every k-th frame, folding skipped time into it
        step = math.ceil(len(frames) / max_frames)
        frames = frames[::step]
        delays = [sum(delays[i:i + step]) for i in range(0, len(delays), step)]
    return frames, delays


@dataclass(frozen=True)
class Look:
    size: int        # longest side in px, before rotation
    angle: float     # degrees, counter-clockwise
    mirror: bool


def random_look(rng: random.Random, min_size: int, max_size: int, max_rotation: float) -> Look:
    return Look(
        size=rng.randint(min_size, max_size),
        angle=rng.uniform(-max_rotation, max_rotation),
        mirror=rng.random() < 0.5,
    )


def render(frames: list[Image.Image], look: Look,
           background: tuple[int, int, int]) -> list[Image.Image]:
    """Apply a Look to every frame, flattening transparency onto `background`."""
    out = []
    for f in frames:
        scale = look.size / max(f.size)
        img = f.resize((max(1, round(f.width * scale)), max(1, round(f.height * scale))),
                       Image.Resampling.LANCZOS)
        if look.mirror:
            img = ImageOps.mirror(img)
        if look.angle:
            img = img.rotate(look.angle, resample=Image.Resampling.BILINEAR, expand=True)
        # Hard alpha cut: semi-transparent edge pixels blended with the key colour would
        # leave a pink fringe, so pixels are either fully shown or fully keyed out.
        mask = img.getchannel("A").point([0] * 128 + [255] * 128)
        flat = Image.new("RGB", img.size, background)
        flat.paste(img, mask=mask)
        out.append(flat)
    return out


class Animation:
    """Tk-ready frames for one rendered variant; shared by every window that uses it."""

    def __init__(self, master: tk.Misc, images: list[Image.Image], delays: list[int]):
        self.frames = [ImageTk.PhotoImage(img, master=master) for img in images]
        self.delays = delays
        self.width, self.height = images[0].size


class GifWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, anim: Animation, x: int, y: int, bg_hex: str,
                 on_click: Callable[[], None]):
        super().__init__(master, bg=bg_hex)
        self.anim = anim
        self.index = random.randrange(len(anim.frames))  # don't dance in lockstep
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        if IS_WINDOWS:
            self.attributes("-transparentcolor", bg_hex)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.label = tk.Label(self, image=anim.frames[self.index], bd=0, bg=bg_hex)
        self.label.pack()
        self.label.bind("<Button>", lambda e: on_click())
        self.geometry(f"+{x}+{y}")
        self._job = self.after(anim.delays[self.index], self._advance)

    def _advance(self) -> None:
        self.index = (self.index + 1) % len(self.anim.frames)
        self.label.configure(image=self.anim.frames[self.index])
        self._job = self.after(self.anim.delays[self.index], self._advance)

    def destroy(self) -> None:
        self.after_cancel(self._job)
        super().destroy()


class GifSwarm:
    """Keeps the number of GIF windows on screen in line with `target_count`.

    Threading rule: the worker thread only touches Pillow images and `_sources`;
    everything Tk (Animation, GifWindow, after()) stays on the UI thread.
    """

    def __init__(self, master: tk.Misc, folder: Path, screen_rect: tuple[int, int, int, int],
                 *, max_windows: int, grace: int, growth: float, min_size: int,
                 max_size: int, max_rotation: float, on_click: Callable[[], None],
                 log: Callable[[str], None] = lambda msg: None):
        self.master = master
        self.paths = find_gifs(folder)
        self.screen_rect = screen_rect
        self.max_windows, self.grace, self.growth = max_windows, grace, growth
        self.min_size, self.max_size, self.max_rotation = min_size, max_size, max_rotation
        self.on_click = on_click
        self.log = log
        self.rng = random.Random()
        self.background = KEY_COLOR if IS_WINDOWS else (0, 0, 0)
        self.bg_hex = KEY_HEX if IS_WINDOWS else "#000000"
        self.windows: list[GifWindow] = []
        self._queued = 0      # spawns requested but not on screen yet
        self._rendering = 0   # variants being rendered in the background
        self._jobs: set[str] = set()
        self._closed = False
        self._sources: dict[Path, tuple[list[Image.Image], list[int]]] = {}  # worker-only
        self._variants: list[Animation] = []
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mathlock-gifs")
        if not self.paths:
            log(f"no .gif files in {folder} -- wrong answers won't spawn GIFs")

    # -- public -------------------------------------------------------------
    def update_for(self, wrong: int) -> None:
        """Call after each wrong answer; spawns however many GIFs the curve now asks for."""
        if not self.paths:
            return
        target = target_count(wrong, self.grace, self.growth, self.max_windows)
        missing = target - len(self.windows) - self._queued
        for i in range(max(0, missing)):
            self._queued += 1
            self._after(i * SPAWN_STAGGER_MS, self._spawn_one)

    def lift_all(self) -> None:
        for w in self.windows:
            w.lift()

    def destroy_all(self) -> None:
        self._closed = True
        for job in self._jobs:
            self.master.after_cancel(job)
        self._jobs.clear()
        self._pool.shutdown(wait=False, cancel_futures=True)
        for w in self.windows:
            w.destroy()
        self.windows.clear()
        self._variants.clear()

    # -- internals ----------------------------------------------------------
    def _after(self, ms: int, fn: Callable[[], None]) -> None:
        job = ""
        def run() -> None:
            self._jobs.discard(job)
            if not self._closed:
                fn()
        job = self.master.after(ms, run)
        self._jobs.add(job)

    def _render_job(self, path: Path, look: Look) -> tuple[list[Image.Image], list[int]]:
        """Runs on the worker thread."""
        if path not in self._sources:
            self._sources[path] = load_frames(path, self.max_size)
        frames, delays = self._sources[path]
        return render(frames, look, self.background), delays

    def _spawn_one(self) -> None:
        if len(self._variants) + self._rendering >= MAX_VARIANTS:
            if self._variants:
                self._show(self.rng.choice(self._variants))
            else:  # every variant is still rendering; try again shortly
                self._after(POLL_MS, self._spawn_one)
            return
        if not self.paths:
            self._queued -= 1
            return
        path = self.rng.choice(self.paths)
        look = random_look(self.rng, self.min_size, self.max_size, self.max_rotation)
        self._rendering += 1
        future = self._pool.submit(self._render_job, path, look)
        self._after(POLL_MS, lambda: self._collect(future, path))

    def _collect(self, future: Future, path: Path) -> None:
        if not future.done():
            self._after(POLL_MS, lambda: self._collect(future, path))
            return
        self._rendering -= 1
        try:
            images, delays = future.result()
        except Exception as exc:  # unreadable file: drop it and try another
            self.log(f"skipping {path.name}: {exc}")
            if path in self.paths:
                self.paths.remove(path)
            self._spawn_one()
            return
        anim = Animation(self.master, images, delays)
        self._variants.append(anim)
        self._show(anim)

    def _show(self, anim: Animation) -> None:
        self._queued -= 1
        sx, sy, sw, sh = self.screen_rect
        x = sx + self.rng.randint(0, max(0, sw - anim.width))
        y = sy + self.rng.randint(0, max(0, sh - anim.height))
        self.windows.append(GifWindow(self.master, anim, x, y, self.bg_hex, self.on_click))
