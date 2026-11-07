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


# ---- 版本管理：改名、刪除、來源已刪除、還原小節 ----

def rename(server, vid, name):
    return call("POST", f"{server}/api/version/rename?p={NAME}&v={vid}", {"name": name})


def delete(server, vid):
    return call("POST", f"{server}/api/version/delete?p={NAME}&v={vid}")


def restore(server, vid, i=0):
    return call("GET", f"{server}/api/restore_bar?p={NAME}&v={vid}&i={i}")


def set_events(server, vid, events):
    _, d = call("GET", f"{server}/api/score?p={NAME}&v={vid}")
    d["score"]["bars"][0]["events"] = events
    assert call("POST", f"{server}/api/score?p={NAME}&v={vid}", d["score"])[0] == 200


def version_list(server):
    return call("GET", f"{server}/api/versions?p={NAME}")[1]


def test_編輯版本可以改名且保留來源(server):
    _, v = create(server, "舊名")
    code, r = rename(server, v["id"], "  新名 ")
    assert code == 200 and r["name"] == "新名"
    got = [x for x in version_list(server) if x["id"] == v["id"]][0]
    assert got["name"] == "新名" and got["source"] == "ai"


def test_改名不能空白(server):
    _, v = create(server)
    assert rename(server, v["id"], " ")[0] == 400


def test_AI譜不能改名或刪除(server, projects_root):
    assert rename(server, "ai", "亂改")[0] == 403
    assert delete(server, "ai")[0] == 403
    assert (projects_root / "假歌" / "score.json").exists()
    assert version_list(server)[0]["name"] == "AI 譜"


def test_改名或刪除不存在的版本(server):
    assert rename(server, "nope", "x")[0] == 404
    assert delete(server, "nope")[0] == 404


def test_刪除編輯版本(server, projects_root):
    _, v = create(server)
    code, _ = delete(server, v["id"])
    assert code == 200
    assert [x["id"] for x in version_list(server)] == ["ai"]
    assert not (projects_root / "假歌" / "versions" / f"{v['id']}.json").exists()
    assert call("GET", f"{server}/api/score?p={NAME}&v={v['id']}")[0] == 404


def test_來源被刪後版本照常可用並標示來源已刪除(server):
    _, a = create(server, "A")
    _, b = create(server, "B", source=a["id"])
    assert [x for x in version_list(server) if x["id"] == b["id"]][0]["source_deleted"] is False
    delete(server, a["id"])
    got = [x for x in version_list(server) if x["id"] == b["id"]][0]
    assert got["source_deleted"] is True and got["source"] == a["id"]
    code, d = call("GET", f"{server}/api/score?p={NAME}&v={b['id']}")
    assert code == 200 and d["score"]["bars"]
    # 仍可存檔
    assert call("POST", f"{server}/api/score?p={NAME}&v={b['id']}", d["score"])[0] == 200
    # 從 AI 譜複製的版本沒有「來源已刪除」
    _, c = create(server, "C")
    assert [x for x in version_list(server) if x["id"] == c["id"]][0]["source_deleted"] is False


def test_還原小節取來源版本的那一小節(server):
    _, a = create(server, "A")
    set_events(server, a["id"], [{"tick": 12, "notes": ["SD"]}])
    _, b = create(server, "B", source=a["id"])
    set_events(server, b["id"], [{"tick": 0, "notes": ["HH"]}])
    code, bar = restore(server, b["id"])
    assert code == 200
    assert [(e["tick"], e["notes"]) for e in bar["events"]] == [(12, ["SD"])]
    # 還原只回傳小節內容，不會自己改動版本
    _, d = call("GET", f"{server}/api/score?p={NAME}&v={b['id']}")
    assert [e["notes"] for e in d["score"]["bars"][0]["events"]] == [["HH"]]


def test_來源已刪除時還原成AI譜的那一小節(server):
    _, a = create(server, "A")
    set_events(server, a["id"], [{"tick": 12, "notes": ["SD"]}])
    _, b = create(server, "B", source=a["id"])
    set_events(server, b["id"], [{"tick": 0, "notes": ["HH"]}])
    delete(server, a["id"])
    code, bar = restore(server, b["id"])
    assert code == 200
    assert [(e["tick"], e["notes"]) for e in bar["events"]] == [(0, ["BD"])]


def test_從AI譜複製的版本還原成AI譜(server):
    _, v = create(server)
    set_events(server, v["id"], [])
    code, bar = restore(server, v["id"])
    assert code == 200 and [e["notes"] for e in bar["events"]] == [["BD"]]


def test_還原小節的錯誤情況(server):
    _, v = create(server)
    assert restore(server, "ai")[0] == 403
    assert restore(server, "nope")[0] == 404
    assert restore(server, v["id"], i=5)[0] == 404
