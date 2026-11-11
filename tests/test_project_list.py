"""專案清單的辨識資訊（bpm、小節數、長度、編輯版本數、最近更新）：只透過 HTTP API 驗證。"""
import json
import os
from datetime import datetime

from conftest import FAKE_SCORE
from test_versions import call, create

NAME = "假歌"


def item(base, name=NAME):
    return {p["name"]: p for p in call("GET", f"{base}/api/project_list")[1]}[name]


def test_清單帶辨識資訊(server):
    p = item(server)
    assert p["status"] == "ready" and p["error"] is None   # 既有欄位不變
    assert p["bpm"] == 120.0 and p["bars"] == 1 and p["duration"] == 4.0
    assert p["versions"] == 0
    datetime.fromisoformat(p["updated"])


def test_編輯版本數不含舊AI譜(server, projects_root):
    create(server, "簡化版")
    create(server, "進階版")
    old = {**FAKE_SCORE, "meta": {"name": "舊 AI 譜", "kind": "old_ai", "source": None}}
    (projects_root / NAME / "versions" / "oldai01.json").write_text(json.dumps(old), encoding="utf-8")
    assert item(server)["versions"] == 2


def test_更新時間跟著版本檔變動(server, projects_root):
    score = projects_root / NAME / "score.json"
    os.utime(score, (1_700_000_000, 1_700_000_000))
    before = item(server)["updated"]
    create(server, "簡化版")
    assert item(server)["updated"] > before


def test_score壞掉清單照常_欄位省略(server, projects_root):
    (projects_root / NAME / "score.json").write_text("{壞掉", encoding="utf-8")
    p = item(server)
    assert p["status"] == "ready"
    assert "bpm" not in p and "bars" not in p


def test_沒有score的專案沒有鼓譜資訊(server, projects_root):
    (projects_root / "半成品").mkdir()
    p = item(server, "半成品")
    assert p["status"] == "failed"
    assert "bpm" not in p and "versions" not in p
