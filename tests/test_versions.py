"""編輯版本的最小流程：只透過 HTTP API 驗證外部行為。"""
import json
import urllib.error
import urllib.parse
import urllib.request

from conftest import FAKE_SCORE

NAME = urllib.parse.quote("假歌")


def call(method, url, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def create(server, name="簡化版", source="ai"):
    return call("POST", f"{server}/api/versions?p={NAME}", {"name": name, "source": source})


def test_版本清單一開始只有AI譜(server):
    code, vs = call("GET", f"{server}/api/versions?p={NAME}")
    assert code == 200
    assert [(v["id"], v["kind"]) for v in vs] == [("ai", "ai")]


def test_AI譜不能存檔(server, projects_root):
    before = (projects_root / "假歌" / "score.json").read_text(encoding="utf-8")
    code, _ = call("POST", f"{server}/api/score?p={NAME}", FAKE_SCORE)
    assert code == 403
    code, _ = call("POST", f"{server}/api/score?p={NAME}&v=ai", FAKE_SCORE)
    assert code == 403
    assert (projects_root / "假歌" / "score.json").read_text(encoding="utf-8") == before


def test_從AI譜建立編輯版本(server, projects_root):
    code, v = create(server, "照原譜版")
    assert code == 200
    assert v["name"] == "照原譜版" and v["source"] == "ai" and v["kind"] == "edited" and v["created"]
    # 存在專案的 versions/，用 id 命名，檔內記名稱、來源、建立時間
    f = projects_root / "假歌" / "versions" / f"{v['id']}.json"
    assert f.exists()
    meta = json.loads(f.read_text(encoding="utf-8"))["meta"]
    assert (meta["name"], meta["source"], meta["created"]) == ("照原譜版", "ai", v["created"])
    # 內容是 AI 譜的複本
    code, d = call("GET", f"{server}/api/score?p={NAME}&v={v['id']}")
    assert d["score"]["bars"][0]["events"] == FAKE_SCORE["bars"][0]["events"]
    # 列在版本清單
    _, vs = call("GET", f"{server}/api/versions?p={NAME}")
    assert [x["id"] for x in vs] == ["ai", v["id"]]


def test_從編輯版本再複製會記來源(server):
    _, a = create(server, "A")
    _, b = create(server, "B", source=a["id"])
    assert b["source"] == a["id"]


def test_來源不存在不能建立或名稱空白(server):
    assert create(server, "X", source="nope")[0] == 404
    assert create(server, "  ")[0] == 400


def test_編輯版本存檔會重算時間與索引(server):
    _, v = create(server)
    _, d = call("GET", f"{server}/api/score?p={NAME}&v={v['id']}")
    score = d["score"]
    score["bars"][0]["events"] = [
        {"tick": 36, "notes": ["SD", "BD", "SD"]},          # 故意不給 t / idx、順序顛倒
        {"tick": 24, "notes": ["HH"], "t": 99, "idx": 99},
        {"tick": 12, "notes": []},                          # 空音符會被丟掉
    ]
    score["bars"][0]["edited"] = True
    code, r = call("POST", f"{server}/api/score?p={NAME}&v={v['id']}", score)
    assert code == 200 and r["edited"] == 1
    _, d = call("GET", f"{server}/api/score?p={NAME}&v={v['id']}")
    evs = d["score"]["bars"][0]["events"]
    assert [(e["tick"], e["t"], e["idx"], e["notes"]) for e in evs] == [
        (24, 1.0, 0, ["HH"]), (36, 1.5, 1, ["BD", "SD"])]


def test_存檔不影響AI譜也不改動版本中繼資料(server, projects_root):
    before = (projects_root / "假歌" / "score.json").read_text(encoding="utf-8")
    _, v = create(server, "原名")
    _, d = call("GET", f"{server}/api/score?p={NAME}&v={v['id']}")
    d["score"]["meta"] = {"name": "亂改", "source": "x", "created": "x"}
    call("POST", f"{server}/api/score?p={NAME}&v={v['id']}", d["score"])
    _, vs = call("GET", f"{server}/api/versions?p={NAME}")
    assert vs[1]["name"] == "原名" and vs[1]["source"] == "ai"
    assert (projects_root / "假歌" / "score.json").read_text(encoding="utf-8") == before


def test_讀取不存在或不合法的版本id(server):
    assert call("GET", f"{server}/api/score?p={NAME}&v=nope")[0] == 404
    assert call("GET", f"{server}/api/score?p={NAME}&v=..%2Fscore")[0] == 404
    assert call("POST", f"{server}/api/score?p={NAME}&v=nope", FAKE_SCORE)[0] == 404
