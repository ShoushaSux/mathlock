"""Thin ctypes wrappers around user32 for managing OUR OWN window.

Anti-cheat policy for this module (keep it this way):
  * No SetWindowsHookEx / global keyboard or mouse hooks.
  * No SendInput / keybd_event / synthetic input of any kind.
  * No OpenProcess, ReadProcessMemory, DLL injection, or touching the game's window.
We only reposition / raise / focus the window this process created. Every function
is a safe no-op on non-Windows so the UI can be developed on Linux/macOS too.
"""

from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND

    HWND_TOPMOST = wintypes.HWND(-1)
    SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


def enable_dpi_awareness() -> None:
    """Call before creating any Tk window so geometry matches real pixels."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def hwnd_for(tk_window) -> int | None:
    """Top-level HWND for a Tk window (Tk's winfo_id is an inner child)."""
    if not IS_WINDOWS:
        return None
    tk_window.update_idletasks()
    return user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()


def virtual_screen_rect(tk_window) -> tuple[int, int, int, int]:
    """(x, y, width, height) covering every monitor."""
    if IS_WINDOWS:
        return (
            user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
    return 0, 0, tk_window.winfo_screenwidth(), tk_window.winfo_screenheight()


def force_foreground(hwnd: int | None) -> None:
    """Make our window topmost and focused.

    Windows blocks focus-stealing; the documented workaround is to briefly attach our
    input queue to the current foreground thread. This does not inject input or touch
    the other process's memory.
    """
    if not IS_WINDOWS or not hwnd:
        return
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    our_thread = kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != our_thread:
        attached = bool(user32.AttachThreadInput(our_thread, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(our_thread, fg_thread, False)
