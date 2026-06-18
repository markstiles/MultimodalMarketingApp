"""Run backend + frontend in one terminal with clean Ctrl+C shutdown."""
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYTHON = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")

CYAN    = "\033[36m"
MAGENTA = "\033[35m"
RESET   = "\033[0m"


def stream(proc, label, color):
    try:
        for raw in proc.stdout:
            print(f"{color}{label:8s}{RESET} | {raw}", end="", flush=True)
    except ValueError:
        pass


def kill_tree(proc):
    """Kill a process and all its children (handles npm → node chains on Windows)."""
    if sys.platform == "win32":
        subprocess.call(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    backend = subprocess.Popen(
        [
            PYTHON, "-m", "uvicorn", "app.main:app",
            "--app-dir", "backend",
            "--reload", "--reload-dir", "backend/app",
            "--port", "8000",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    frontend = subprocess.Popen(
        "npm run dev",
        cwd=str(ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )

    threading.Thread(target=stream, args=(backend,  "backend",  CYAN),    daemon=True).start()
    threading.Thread(target=stream, args=(frontend, "frontend", MAGENTA), daemon=True).start()

    print(f"\n{CYAN}backend {RESET} | http://localhost:8000")
    print(f"{MAGENTA}frontend{RESET} | http://localhost:3000")
    print("Press Ctrl+C or run 'just stop' to shut down.\n", flush=True)

    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    print("\nShutting down...", flush=True)
    kill_tree(backend)
    kill_tree(frontend)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
