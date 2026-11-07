"""重新扒譜：只透過 HTTP API 驗證。扒譜流程換成假的，新的 AI 譜由測試放在 next_score.json。"""
import copy
import json
import time
import urllib.parse

import pytest

from conftest import FAKE_SCORE, launch_server
from test_versions import call, NAME

FAKE_PIPELINE = '''
import json
import time
from pathlib import Path

HERE = Path(__file__).parent


def _step(name):
    with open(HERE / "calls.log", "a", encoding="utf-8") as f:
        f.write(name + "\\n")
    while (HERE / "hold").exists():
        time.sleep(0.05)
    if (HERE / "fail").exists():
        raise RuntimeError("假的失敗：" + name)


def download(P, source, opts, report):
    _step("download")


def separate(P, opts, report):
    _step("separate")


def transcribe(P, opts, report):
    _step("transcribe")


def score(P, opts, report):
    _step("score")
    (P / "score.json").write_text((HERE / "next_score.json").read_text(encoding="utf-8"), encoding="utf-8")
'''


def two_bar(t0_second):
    s = copy.deepcopy(FAKE_SCORE)
    s["bars"] = [s["bars"][0], {**copy.deepcopy(s["bars"][0]), "t0": t0_second, "t1": t0_second + 2.0}]
    return s


@pytest.fixture
def fake(tmp_path):
    d = tmp_path / "fakepipe"
    d.mkdir()
    (d / "pipeline.py").write_text(FAKE_PIPELINE, encoding="utf-8")
    return d


@pytest.fixture
def srv(projects_root, fake):
    (projects_root / "假歌" / "score.json").write_text(json.dumps(two_bar(2.0)), encoding="utf-8")
    (fake / "next_score.json").write_text(json.dumps(two_bar(2.0)), encoding="utf-8")
    with launch_server(projects_root, {"DRUMCOVER_PIPELINE": str(fake / "pipeline.py")}) as base:
        yield base


def set_next(fake, t0_second):
    (fake / "next_score.json").write_text(json.dumps(two_bar(t0_second)), encoding="utf-8")


def versions(base):
    return call("GET", f"{base}/api/versions?p={NAME}")[1]


def reimport(base):
    return call("POST", f"{base}/api/projects/reimport?p={NAME}")


def wait_state(base, state, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        j = call("GET", f"{base}/api/job")[1]
        if j["state"] == state:
            return j
        time.sleep(0.1)
    raise AssertionError(f"等不到 {state}，目前 {call('GET', f'{base}/api/job')[1]}")


def do_reimport(base):
    assert reimport(base)[0] == 200
    wait_state(base, "done")


def old_ai(base):
    return [v for v in versions(base) if v["kind"] == "old_ai"]


def create(base, name, source="ai"):
    return call("POST", f"{base}/api/versions?p={NAME}", {"name": name, "source": source})[1]


def test_重新扒譜把上一份AI譜保存成唯讀舊AI譜(srv, fake, projects_root):
    set_next(fake, 2.5)
    before = (projects_root / "假歌" / "score.json").read_bytes()
    do_reimport(srv)
    olds = old_ai(srv)
    assert len(olds) == 1 and "舊 AI 譜" in olds[0]["name"]
    # 舊 AI 譜內容是重新扒譜前的 AI 譜，AI 譜變成新的
    _, d = call("GET", f"{srv}/api/score?p={NAME}&v={olds[0]['id']}")
    assert d["score"]["bars"][1]["t0"] == 2.0
    _, d = call("GET", f"{srv}/api/score?p={NAME}")
    assert d["score"]["bars"][1]["t0"] == 2.5
    assert before != (projects_root / "假歌" / "score.json").read_bytes()
    assert versions(srv)[0]["id"] == "ai"


def test_舊AI譜不能存檔改名刪除_但可以複製(srv):
    do_reimport(srv)
    oid = old_ai(srv)[0]["id"]
    score = call("GET", f"{srv}/api/score?p={NAME}&v={oid}")[1]["score"]
    assert call("POST", f"{srv}/api/score?p={NAME}&v={oid}", score)[0] == 403
    assert call("POST", f"{srv}/api/version/rename?p={NAME}&v={oid}", {"name": "改名"})[0] == 403
    assert call("POST", f"{srv}/api/version/delete?p={NAME}&v={oid}")[0] == 403
    assert oid in [v["id"] for v in old_ai(srv)]
    v = create(srv, "從舊AI譜複製", source=oid)
    assert v["source"] == oid and v["kind"] == "edited"


def test_編輯版本的檔案完全不變(srv, fake, projects_root):
    a = create(srv, "A")
    b = create(srv, "B", source=a["id"])
    files = {f: (projects_root / "假歌" / "versions" / f"{f}.json") for f in (a["id"], b["id"])}
    before = {k: p.read_bytes() for k, p in files.items()}
    set_next(fake, 3.0)
    do_reimport(srv)
    assert {k: p.read_bytes() for k, p in files.items()} == before


def test_起點差超過0點1秒_衍生的編輯版本有警告(srv, fake):
    a = create(srv, "照AI譜版")                    # 重新扒譜前從當時的 AI 譜複製
    b = create(srv, "再衍生", source=a["id"])
    set_next(fake, 2.2)
    do_reimport(srv)
    oid = old_ai(srv)[0]["id"]
    c = create(srv, "從舊AI譜複製", source=oid)    # 重新扒譜後從舊 AI 譜複製
    by_id = {v["id"]: v for v in versions(srv)}
    for v in (a, b, c):
        assert by_id[v["id"]]["warning"]["bars"] == [1], v["name"]
    assert not by_id["ai"].get("warning") and not by_id[oid].get("warning")


def test_重新扒譜後才從新AI譜複製的版本沒有警告(srv, fake):
    set_next(fake, 2.2)
    time.sleep(1.1)   # 建立時間的解析度是秒
    do_reimport(srv)
    time.sleep(1.1)
    d = create(srv, "從新AI譜複製")
    by_id = {v["id"]: v for v in versions(srv)}
    assert not by_id[d["id"]].get("warning")


def test_起點差不到0點1秒_沒有警告(srv, fake):
    a = create(srv, "照AI譜版")
    set_next(fake, 2.05)
    do_reimport(srv)
    oid = old_ai(srv)[0]["id"]
    c = create(srv, "從舊AI譜複製", source=oid)
    by_id = {v["id"]: v for v in versions(srv)}
    assert not by_id[a["id"]].get("warning")
    assert not by_id[c["id"]].get("warning")


def test_忙碌時重新扒譜被拒絕且不產生舊AI譜(srv, fake):
    (fake / "hold").write_text("1")
    assert reimport(srv)[0] == 200
    wait_state(srv, "running")
    code, body = reimport(srv)
    assert code == 409 and "忙碌" in body["error"]
    (fake / "hold").unlink()
    wait_state(srv, "done")
    assert len(old_ai(srv)) == 1


def test_重新扒譜失敗_AI譜不變且不留下多餘的舊AI譜(srv, fake, projects_root):
    (fake / "fail").write_text("1")
    before = (projects_root / "假歌" / "score.json").read_bytes()
    assert reimport(srv)[0] == 200
    j = wait_state(srv, "error")
    assert "假的失敗" in j["error"]
    assert (projects_root / "假歌" / "score.json").read_bytes() == before
    assert old_ai(srv) == []


def test_沒有AI譜的專案不能重新扒譜(srv, projects_root):
    (projects_root / "空專案").mkdir()
    code, _ = call("POST", f"{srv}/api/projects/reimport?p={urllib.parse.quote('空專案')}")
    assert code in (400, 404)
