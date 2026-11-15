# MathLock

A Windows overlay that periodically covers the screen with its **own separate window**
and won't go away until you solve some math problems.

## Quick start (Windows, Python 3.11+)

Double-click **`setup.bat`** (or run it from a terminal). It checks Python/tkinter, creates
`.venv`, and installs everything. On Linux/macOS run `./setup.sh` instead. Then:

```powershell
.venv\Scripts\activate
python -m mathlock --now      # show the lock screen immediately
python -m mathlock            # normal mode: lock every `interval_minutes`
pytest                        # run tests
```

Settings are in `config.toml`. Put personal overrides in `config.local.toml` (git-ignored).
**Keep `debug = true` while developing.** It gives you a small window and an escape hotkey
(`Ctrl+Shift+F12`), so a bug can't lock you out of your own machine.

## Layout

```
src/mathlock/
  __main__.py   CLI entry point
  app.py        hidden Tk root + timer that triggers lock screens
  overlay.py    the lock-screen window (UI, unclosable behaviour, refocus loop)
  problems.py   math problem generation (pure logic, unit-tested)
  config.py     config.toml loading/validation
  winutil.py    ctypes user32 helpers (topmost, foreground, DPI); no-ops off Windows
tests/          pytest suite
```

## Anti-cheat compliance: the rules

The point is that anti-cheat software (EAC, BattlEye, Vanguard, etc.) has nothing to flag.
MathLock is just an ordinary desktop app that sometimes shows a topmost window.

**We DO:** create our own windows (a translucent full-screen backdrop, `background_opacity`,
plus an opaque question panel), make them topmost, take focus back when it's lost,
and ignore close requests (X button, Alt+F4, WM_CLOSE).

**We NEVER:** use `SetWindowsHookEx` (global keyboard/mouse hooks), `SendInput`/`keybd_event`
(synthetic input), `OpenProcess`/memory reads, DLL injection, or draw into or send messages
to the game's window. All Win32 calls are in `winutil.py`. Review any change to that file
against this list.

### Known limitations (by design)
- **Alt+Tab / Win key aren't blocked.** Blocking them needs a global hook. Instead, the
  overlay takes focus back every 150 ms, so switching away doesn't get you anywhere.
- **Ctrl+Alt+Del / Task Manager always work.** Windows reserves them, which is also a safety net.
- **Exclusive-fullscreen games:** a topmost window can't draw over exclusive fullscreen, so
  Windows minimises the game when we take focus. Borderless-windowed games work smoothly.
  Mention this in the demo.

## Packaging

```powershell
pyinstaller --noconsole --onefile --name MathLock --paths src run_mathlock.py
```

## Ideas / TODO
- System tray icon with "time until next lock" (e.g. `pystray`)
- Only lock while a listed game process is in the foreground (use window title or process
  name via `GetForegroundWindow`, which is read-only and safe)
- Difficulty scaling and streaks; parent/teacher password; stats log
