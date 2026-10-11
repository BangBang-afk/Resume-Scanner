"""One-command boot: backend + frontend + demo seed. Usage: python run.py"""

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
API = "http://127.0.0.1:8000"
UI = "http://127.0.0.1:3000"

def _find_venv() -> str:
    if os.environ.get("SHORTLISTIQ_PY"):
        return os.environ["SHORTLISTIQ_PY"]
    here = pathlib.Path(__file__).resolve()
    candidates = [here.parent / ".venv", * [p / ".venv" for p in here.parents]]
    for venv in candidates:
        for exe in (venv / "Scripts" / "python.exe", venv / "bin" / "python"):
            if exe.exists():
                return str(exe)
    return sys.executable


VENV_PY = _find_venv()


def wait(url: str, timeout: int = 90) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=5)
            return True
        except Exception:
            time.sleep(2)
    return False


def seed_if_empty() -> None:
    # _seed.py authenticates itself and skips when the demo job exists.
    print("seeding demo job + 12 resumes (skips if present) ...")
    r = subprocess.run([sys.executable, "_seed.py"], cwd=BACKEND, capture_output=True, text=True)
    out = (r.stdout or "").strip().splitlines()
    print(out[-3:] if out else r.stderr[-500:])


def main() -> int:
    backend = subprocess.Popen([VENV_PY, "_serve.py"], cwd=BACKEND)
    try:
        if not wait(API + "/health"):
            print("backend failed to start")
            return 1
        print("backend up", API)
        seed_if_empty()

        npm = shutil.which("npm") or "npm"
        if not (FRONTEND / ".next").exists():
            print("building frontend (first run only) ...")
            if subprocess.run([npm, "run", "build"], cwd=FRONTEND, shell=os.name == "nt").returncode != 0:
                print("frontend build failed")
                return 1
        frontend = subprocess.Popen([npm, "start"], cwd=FRONTEND, shell=os.name == "nt")
        try:
            if not wait(UI):
                print("frontend failed to start")
                return 1
            print("frontend up", UI)
            webbrowser.open(UI)
            print("both live. Ctrl+C stops everything.")
            frontend.wait()
            return 0
        except KeyboardInterrupt:
            print("\nstopping ...")
            frontend.terminate()
            return 0
    except KeyboardInterrupt:
        print("\nstopping ...")
        return 0
    finally:
        backend.terminate()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    sys.exit(main())
