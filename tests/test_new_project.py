"""首頁與新增專案：只透過 HTTP API 驗證。

扒譜流程（DRUMCOVER_PIPELINE 指到的模組）換成假的：每一步把自己的名稱記到 calls.log，
可以用 fail 檔案指定在哪一步失敗，score 步驟寫出一份固定的鼓譜。
"""
import json
import time
import urllib.parse
import urllib.request

import pytest

from conftest import FAKE_SCORE, launch_server
from test_versions import call

FAKE_PIPELINE = '''
import json
from pathlib import Path

HERE = Path(__file__).parent


def _step(name, P, report):
    with open(HERE / "calls.log", "a", encoding="utf-8") as f:
        f.write(name + "\\n")
    report(0.5)
    while (HERE / "hold").exists():
        import time; time.sleep(0.05)
    fail = HERE / "fail"
    if fail.exists() and fail.read_text(encoding="utf-8").strip() == name:
        raise RuntimeError("假的失敗：" + name)


def title(source):
    return "某歌 - 官方MV【中文】"


def download(P, source, opts, report):
    _step("download", P, report)
    (P / "video.mp4").write_bytes(b"x")
    (HERE / "opts.json").write_text(json.dumps({"source": source, "opts": opts}), encoding="utf-8")


def separate(P, opts, report):
    _step("separate", P, report)


def transcribe(P, opts, report):
    _step("transcribe", P, report)


def score(P, opts, report):
    _step("score", P, report)
    (P / "score.json").write_text(json.dumps(SCORE), encoding="utf-8")


SCORE = %s
''' % json.dumps(FAKE_SCORE)

URL = "https://www.youtube.com/watch?v=abc"


@pytest.fixture
def fake(tmp_path):
    d = tmp_path / "fakepipe"
    d.mkdir()
    (d / "pipeline.py").write_text(FAKE_PIPELINE, encoding="utf-8")
    return d


@pytest.fixture
def srv(projects_root, fake):
    with launch_server(projects_root, {"DRUMCOVER_PIPELINE": str(fake / "pipeline.py")}) as base:
        yield base


def calls(fake):
    f = fake / "calls.log"
    return f.read_text(encoding="utf-8").split() if f.exists() else []


def job(base):
    return call("GET", f"{base}/api/job")[1]


def wait_state(base, state, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        j = job(base)
        if j["state"] == state:
            return j
        time.sleep(0.1)
    raise AssertionError(f"等不到 {state}，目前 {job(base)}")


def new(base, name, source=URL, **kw):
    return call("POST", f"{base}/api/projects/new", {"source": source, "name": name, **kw})


def listing(base):
    return {p["name"]: p for p in call("GET", f"{base}/api/project_list")[1]}


def test_名稱預設用影片標題(srv):
    code, body = call("GET", f"{srv}/api/project_title?source={urllib.parse.quote(URL)}")
    assert code == 200 and body["title"] == "某歌 - 官方MV【中文】"


def test_本機mp4名稱預設用檔名(srv, tmp_path):
    mp4 = tmp_path / "我的 錄影.mp4"
    mp4.write_bytes(b"x")
    code, body = call("GET", f"{srv}/api/project_title?source={urllib.parse.quote(str(mp4))}")
    assert code == 200 and body["title"] == "我的 錄影"


def test_新增專案成功_中文與空白名稱(srv, projects_root):
    code, body = new(srv, "某歌 - 官方MV【中文】")
    assert code == 200 and body["name"] == "某歌 - 官方MV【中文】"
    wait_state(srv, "done")
    assert (projects_root / "某歌 - 官方MV【中文】" / "score.json").exists()
    assert listing(srv)["某歌 - 官方MV【中文】"]["status"] == "ready"
    # 新專案可以像一般專案一樣讀取
    n = urllib.parse.quote("某歌 - 官方MV【中文】")
    assert call("GET", f"{srv}/api/score?p={n}")[0] == 200


def test_工作回報四個步驟(srv, fake):
    (fake / "hold").write_text("1")
    new(srv, "新歌")
    j = wait_state(srv, "running")
    assert j["kind"] == "import" and j["project"] == "新歌"
    assert j["steps"] == ["下載", "分離鼓聲", "扒譜", "排版"]
    assert listing(srv)["新歌"]["status"] == "running"
    (fake / "hold").unlink()
    wait_state(srv, "done")
    assert calls(fake) == ["download", "separate", "transcribe", "score"]


def test_重名被拒絕(srv, fake):
    code, body = new(srv, "假歌")
    assert code == 409 and "已存在" in body["error"]
    assert calls(fake) == []


@pytest.mark.parametrize("bad", ["a/b", "a\\b", "..", "a:b", "a*b", "a?b", 'a"b', "a<b", "a|b", "", "  ", "x.", "CON"])
def test_不合法名稱被拒絕(srv, bad):
    code, body = new(srv, bad)
    assert code == 400 and body["error"]


def test_進階選項會傳給扒譜流程(srv, fake):
    new(srv, "有選項", start=12.5, dur=30, audio="mix")
    wait_state(srv, "done")
    got = json.loads((fake / "opts.json").read_text(encoding="utf-8"))
    assert got["source"] == URL
    assert got["opts"] == {"start": 12.5, "dur": 30.0, "audio": "mix"}


def test_音源選項不合法被拒絕(srv):
    assert new(srv, "壞選項", audio="rm -rf")[0] == 400


def test_忙碌時不能再新增專案且不留下資料夾(srv, fake, projects_root):
    (fake / "hold").write_text("1")
    assert new(srv, "第一首")[0] == 200
    code, body = new(srv, "第二首")
    assert code == 409 and "忙碌" in body["error"]
    assert not (projects_root / "第二首").exists()
    (fake / "hold").unlink()
    wait_state(srv, "done")


def test_失敗後從失敗那步重試且前面步驟不重跑(srv, fake):
    (fake / "fail").write_text("transcribe")
    new(srv, "會失敗")
    j = wait_state(srv, "error")
    assert j["failed_step"] == 2 and "假的失敗" in j["error"]
    p = listing(srv)["會失敗"]
    assert p["status"] == "failed" and "假的失敗" in p["error"]
    (fake / "fail").unlink()
    assert call("POST", f"{srv}/api/projects/retry?p={urllib.parse.quote('會失敗')}")[0] == 200
    wait_state(srv, "done")
    assert calls(fake) == ["download", "separate", "transcribe", "transcribe", "score"]
    assert listing(srv)["會失敗"]["status"] == "ready"


def test_失敗的專案名稱不能被重複使用(srv, fake):
    (fake / "fail").write_text("download")
    new(srv, "壞掉")
    wait_state(srv, "error")
    assert new(srv, "壞掉")[0] == 409


def test_不是新增專案失敗的專案不能重試(srv):
    assert call("POST", f"{srv}/api/projects/retry?p={urllib.parse.quote('假歌')}")[0] == 400


def test_首頁是專案清單_編輯畫面在editor(srv):
    home = urllib.request.urlopen(srv + "/").read().decode("utf-8")
    editor = urllib.request.urlopen(srv + "/editor").read().decode("utf-8")
    assert "project_list" in home and "project_list" not in editor
    assert 'id="overview"' in editor
