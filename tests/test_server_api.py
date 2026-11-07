import json
import urllib.parse
import urllib.request

from conftest import FAKE_SCORE


def get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read().decode("utf-8"))


def test_列出專案(server):
    assert get_json(server + "/api/projects") == ["假歌"]


def test_讀取鼓譜(server):
    name = urllib.parse.quote("假歌")
    data = get_json(f"{server}/api/score?p={name}")
    assert data["score"]["bpm"] == FAKE_SCORE["bpm"]
    assert len(data["score"]["bars"]) == 1


def test_AI信心_每格取窗內最大擊打機率(projects_root):
    import numpy as np
    from conftest import launch_server
    P = projects_root / "假歌"
    drums = np.zeros((300, 5), dtype=np.float32)   # 欄位順序 BD SD TM HH CY，100 幀/秒
    drums[50, 0] = 0.8                              # BD 在 0.5 秒（第 2 拍正拍）
    np.save(P / "act_drums.npy", drums)
    np.save(P / "act_mix.npy", np.zeros((300, 5), dtype=np.float32))
    with launch_server(projects_root) as base:
        data = get_json(f"{base}/api/score?p={urllib.parse.quote('假歌')}")
    bd = data["act"][0]["BD"]
    assert len(bd["s16"]) == 16 and len(bd["t3"]) == 12
    assert [i for i, v in enumerate(bd["s16"]) if v] == [4] and bd["s16"][4] == 0.8
    assert [i for i, v in enumerate(bd["t3"]) if v] == [3] and bd["t3"][3] == 0.8
    assert not any(data["act"][0]["SD"]["s16"])


def test_沒有活化檔時AI信心為空(server):
    data = get_json(f"{server}/api/score?p={urllib.parse.quote('假歌')}")
    assert data["act"] is None
