@echo off
rem One-command setup for Windows: double-click this file or run `setup.bat` in a terminal.
rem Creates .venv and installs MathLock + dev tools. Safe to re-run.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [setup] Python 3.11 or newer is required. Install it from https://www.python.org/downloads/
    goto :fail
)

%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [setup] tkinter is missing. Re-run the Python installer and tick "tcl/tk and IDLE".
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment in .venv ...
    %PY% -m venv .venv || goto :fail
)

echo [setup] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :fail
".venv\Scripts\python.exe" -m pip install -e ".[dev]" --quiet || goto :fail

echo.
echo [setup] Done! Next steps:
echo     .venv\Scripts\activate
echo     python -m mathlock --now
echo.
if "%~1"=="" pause
exit /b 0

:fail
echo [setup] Setup failed, see the message above.
if "%~1"=="" pause
exit /b 1
