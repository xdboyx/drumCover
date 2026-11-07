"""測試用：在暫存資料夾準備假專案，以子行程啟動編輯器伺服器，只透過 HTTP 驗證。"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "tools" / "editor" / "server.py"

FAKE_SCORE = {
    "bpm": 120.0, "meter": 4, "duration": 4.0, "offset_ms": 0,
    "bars": [{"t0": 0.0, "t1": 2.0, "ticks": 48,
              "events": [{"tick": 0, "notes": ["BD"], "t": 0.0, "idx": 0}]}],
}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def projects_root(tmp_path):
    root = tmp_path / "projects"
    (root / "假歌").mkdir(parents=True)
    (root / "假歌" / "score.json").write_text(json.dumps(FAKE_SCORE), encoding="utf-8")
    return root


@contextmanager
def launch_server(projects_root, env=None):
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), "--port", str(port), "--projects-root", str(projects_root)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, **(env or {})})
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen(base + "/api/projects", timeout=1).read()
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError("伺服器啟動失敗")
                time.sleep(0.2)
        else:
            raise RuntimeError("伺服器啟動逾時")
        yield base
    finally:
        proc.kill()
        proc.wait()


@pytest.fixture
def server(projects_root):
    with launch_server(projects_root) as base:
        yield base
