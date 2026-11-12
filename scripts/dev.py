"""Cross-platform local launcher. Run with the project's virtualenv Python."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
children = []


def stop(*_):
    for child in reversed(children):
        if child.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
            else:
                os.killpg(child.pid, signal.SIGTERM)
    raise SystemExit(0)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from services.api.db import init_db

    init_db()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("Install Node.js 22+ and run npm ci in apps/web first.")
    options = dict(start_new_session=True) if os.name != "nt" else {}
    children.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "services.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            **options,
        )
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/readyz", timeout=1):
                break
        except OSError:
            if children[0].poll() is not None:
                stop()
            time.sleep(0.25)
    else:
        print("API did not become ready within 45 seconds", file=sys.stderr)
        stop()
    children.append(subprocess.Popen([sys.executable, "-m", "workers.processor.main"], **options))
    children.append(subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "apps/web", **options))
    print("DocuLens: http://127.0.0.1:5173 | API docs: http://127.0.0.1:8000/docs", flush=True)
    try:
        while all(child.poll() is None for child in children):
            time.sleep(1)
    finally:
        stop()
