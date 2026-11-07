"""即時預覽：伺服器依傳入（可能未存檔）的鼓譜，回傳某一行的譜面圖與游標位置。"""
import base64

from test_versions import call


def score5():
    bars = []
    for i in range(5):
        bars.append({"t0": i * 2.0, "t1": (i + 1) * 2.0, "ticks": 48,
                     "events": [{"tick": 0, "notes": ["BD"]}, {"tick": 24, "notes": ["SD"]}]})
    return {"bpm": 120.0, "meter": 4, "duration": 10.0, "offset_ms": 0, "bars": bars}


def preview(server, score, line, simile=True):
    return call("POST", f"{server}/api/preview_line?p=x", {"score": score, "line": line, "simile": simile})


def test_回傳每行的時間範圍與該行譜面圖(server):
    code, d = preview(server, score5(), 0)
    assert code == 200
    assert d["lines"] == [[0.0, 8.0], [8.0, 10.0]]
    assert base64.b64decode(d["png"])[:4] == b"\x89PNG"
    assert d["t0"] == 0.0 and d["t1"] == 8.0
    ts = [t for t, _ in d["evs"]]
    xs = [x for _, x in d["evs"]]
    assert ts == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    assert xs == sorted(xs)


def test_點譜面小節的對照資料(server):
    _, d = preview(server, score5(), 0)
    assert [m["bar"] for m in d["measures"]] == [0, 1, 2, 3]
    assert [m["t0"] for m in d["measures"]] == [0.0, 2.0, 4.0, 6.0]
    assert all(m["x0"] < m["x1"] for m in d["measures"])
    assert d["measures"][0]["x1"] == d["measures"][1]["x0"]
    assert d["measures"][0]["x0"] <= d["evs"][0][1] < d["measures"][0]["x1"]


def test_第二行只含剩下的小節(server):
    code, d = preview(server, score5(), 1)
    assert code == 200
    assert [t for t, _ in d["evs"]] == [8.0, 9.0]


def test_未存檔的修改立即反映(server):
    s = score5()
    s["bars"][1]["events"].append({"tick": 12, "notes": ["HH"]})   # 沒有 t / idx，等同前端剛改的
    _, d = preview(server, s, 0)
    assert [t for t, _ in d["evs"]] == [0.0, 1.0, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_百分比記號選項不影響游標時間(server):
    s = score5()
    _, a = preview(server, s, 0, simile=True)
    _, b = preview(server, s, 0, simile=False)
    assert [t for t, _ in a["evs"]] == [t for t, _ in b["evs"]]


def test_行號超出範圍回404(server):
    code, _ = preview(server, score5(), 9)
    assert code == 404
