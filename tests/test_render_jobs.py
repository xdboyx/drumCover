"""輸出練習影片與長時間工作佇列：只透過 HTTP API 驗證。

render 子行程換成假腳本（DRUMCOVER_RENDER_SCRIPT）：等 go 檔案出現才把讀到的鼓譜複製到輸出路徑，
這樣能在不跑 ffmpeg 的情況下控制「工作進行中」的時機。實際跑 ffmpeg 的測試標成 slow。
"""
import json
import time

import pytest

from conftest import FAKE_SCORE, launch_server
from test_versions import call, NAME

FAKE_RENDER = '''
import json, sys, time
from pathlib import Path
a = sys.argv[1:]
opt = {a[i]: a[i + 1] for i in range(2, len(a) - 1) if a[i].startswith("--")}
go = Path(__file__).parent / "go"
print("PROGRESS 5/10", flush=True)
while not go.exists():
    time.sleep(0.05)
if (Path(__file__).parent / "fail").exists():
    print("boom: 假的失敗", flush=True)
    sys.exit(3)
Path(opt["--out"]).write_text(Path(opt["--score"]).read_text(encoding="utf-8"), encoding="utf-8")
'''


@pytest.fixture
def fake(tmp_path):
    d = tmp_path / "fake"
    d.mkdir()
    (d / "render.py").write_text(FAKE_RENDER, encoding="utf-8")
    return d


@pytest.fixture
def srv(projects_root, fake):
    with launch_server(projects_root, {"DRUMCOVER_RENDER_SCRIPT": str(fake / "render.py")}) as base:
        yield base


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


def release(fake):
    (fake / "go").write_text("1")


def new_version(base, name="簡化版", events_tick=0):
    code, v = call("POST", f"{base}/api/versions?p={NAME}", {"name": name, "source": "ai"})
    assert code == 200
    set_tick(base, v["id"], events_tick)
    return v["id"]


def set_tick(base, vid, tick):
    score = json.loads(json.dumps(FAKE_SCORE))
    score["bars"][0]["events"] = [{"tick": tick, "notes": ["SD"]}]
    assert call("POST", f"{base}/api/score?p={NAME}&v={vid}", score)[0] == 200


def start(base, vid, **body):
    return call("POST", f"{base}/api/render?p={NAME}&v={vid}", {"crop_y": 0.5, "simile": True, **body})


def test_沒有工作時狀態是idle(srv):
    assert job(srv)["state"] == "idle"


def test_輸出到exports且檔名用版本名稱(srv, fake, projects_root):
    vid = new_version(srv)
    assert start(srv, vid)[0] == 200
    release(fake)
    j = wait_state(srv, "done")
    assert (j["kind"], j["project"]) == ("render", "假歌")
    assert (projects_root / "假歌" / "exports" / "簡化版.mp4").exists()


def test_進行中回報步驟與進度(srv, fake):
    vid = new_version(srv)
    start(srv, vid)
    end = time.time() + 15
    while time.time() < end and job(srv).get("progress") != 0.5:
        time.sleep(0.1)
    j = job(srv)
    assert j["state"] == "running" and j["progress"] == 0.5 and j["step"]
    release(fake)
    wait_state(srv, "done")


def test_忙碌時拒絕新工作但仍可編輯存檔預覽(srv, fake):
    vid = new_version(srv)
    assert start(srv, vid)[0] == 200
    code, body = start(srv, vid)
    assert code == 409 and "忙碌" in body["error"]
    # 工作進行中仍可讀取、存檔、預覽
    assert call("GET", f"{srv}/api/score?p={NAME}&v={vid}")[0] == 200
    set_tick(srv, vid, 12)
    assert call("POST", f"{srv}/api/line", {"bars": FAKE_SCORE["bars"], "first_no": 1})[0] == 200
    release(fake)
    wait_state(srv, "done")


def test_工作結束後可以再送新工作(srv, fake):
    vid = new_version(srv)
    start(srv, vid)
    release(fake)
    wait_state(srv, "done")
    assert start(srv, vid)[0] == 200
    wait_state(srv, "done")


def test_送出後再改版本不影響這次輸出(srv, fake, projects_root):
    vid = new_version(srv, events_tick=0)
    start(srv, vid)
    set_tick(srv, vid, 24)   # 送出後才修改
    release(fake)
    wait_state(srv, "done")
    out = json.loads((projects_root / "假歌" / "exports" / "簡化版.mp4").read_text(encoding="utf-8"))
    assert out["bars"][0]["events"][0]["tick"] == 0


def test_同一版本再輸出會覆蓋(srv, fake, projects_root):
    vid = new_version(srv, events_tick=0)
    release(fake)
    start(srv, vid)
    wait_state(srv, "done")
    set_tick(srv, vid, 24)
    start(srv, vid)
    wait_state(srv, "done")
    exports = list((projects_root / "假歌" / "exports").iterdir())
    assert [f.name for f in exports] == ["簡化版.mp4"]
    out = json.loads(exports[0].read_text(encoding="utf-8"))
    assert out["bars"][0]["events"][0]["tick"] == 24


def test_檔名非法字元會被替換(srv, fake, projects_root):
    vid = new_version(srv, name='a/b:c*d?"e')
    release(fake)
    start(srv, vid)
    wait_state(srv, "done")
    assert [f.name for f in (projects_root / "假歌" / "exports").iterdir()] == ["a_b_c_d__e.mp4"]


def test_輸出AI譜(srv, fake, projects_root):
    release(fake)
    assert start(srv, "ai")[0] == 200
    wait_state(srv, "done")
    assert (projects_root / "假歌" / "exports" / "AI 譜.mp4").exists()


def test_失敗時回報錯誤訊息且之後可再送(srv, fake, projects_root):
    vid = new_version(srv)
    (fake / "fail").write_text("1")
    release(fake)
    start(srv, vid)
    j = wait_state(srv, "error")
    assert "boom" in j["error"]
    assert not (projects_root / "假歌" / "exports" / "簡化版.mp4").exists()
    (fake / "fail").unlink()
    assert start(srv, vid)[0] == 200
    wait_state(srv, "done")


def test_不存在的版本回404(srv):
    assert start(srv, "deadbeef")[0] == 404
    assert job(srv)["state"] == "idle"


@pytest.mark.slow
def test_實際用ffmpeg輸出練習影片(projects_root):
    import subprocess
    import imageio_ffmpeg
    P = projects_root / "假歌"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(P / "video.mp4")],
                   check=True)
    with launch_server(projects_root, {"DRUMCOVER_CODEC": "libx264"}) as base:
        vid = new_version(base)
        assert start(base, vid)[0] == 200
        wait_state(base, "done", timeout=120)
    assert (P / "exports" / "簡化版.mp4").stat().st_size > 1000
