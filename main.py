"""
CoreX launcher.

Preferred: run the desktop app from frontend/
  cd frontend && npm install && npm start

This script starts the backend in server mode (for Electron or debugging).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_MAIN = ROOT / "backend" / "main.py"
FRONTEND_DIR = ROOT / "frontend"


def _run_backend() -> int:
    cmd = [sys.executable, str(BACKEND_MAIN), "--mode", "server", *sys.argv[1:]]
    return subprocess.call(cmd)


def _run_desktop() -> int:
    if not FRONTEND_DIR.is_dir():
        print("frontend/ not found. Run: python main.py (backend only) or install frontend.")
        return 1

    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    return subprocess.call([npm, "run", "start"], cwd=str(FRONTEND_DIR), shell=sys.platform == "win32")


if __name__ == "__main__":
    if "--desktop" in sys.argv:
        sys.argv.remove("--desktop")
        raise SystemExit(_run_desktop())
    raise SystemExit(_run_backend())
