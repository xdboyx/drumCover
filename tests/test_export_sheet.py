"""鼓譜圖檔輸出（PDF / PNG）：只透過 HTTP API 驗證外部行為。"""
import json
import re
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


def big_score(n_bars, same=False):
    bars = []
    for i in range(n_bars):
        notes = [{"tick": 0, "notes": ["BD"]}, {"tick": 24, "notes": ["SD"]}]
        if not same:
            notes.append({"tick": 12 + (i % 3) * 3, "notes": ["HH"]})
        bars.append({"t0": i * 2.0, "t1": i * 2.0 + 2.0, "ticks": 48, "events": notes})
    return {**FAKE_SCORE, "duration": n_bars * 2.0, "bars": bars}


def make_version(server, name, n_bars=40, same=False):
    _, v = call("POST", f"{server}/api/versions?p={NAME}", {"name": name, "source": "ai"})
    code, _ = call("POST", f"{server}/api/score?p={NAME}&v={v['id']}", big_score(n_bars, same))
    assert code == 200
    return v


def export(server, v, fmt, **extra):
    return call("POST", f"{server}/api/export_sheet?p={NAME}",
                {"version": v, "format": fmt, **extra})


def exports_dir(projects_root):
    return projects_root / "假歌" / "exports"


def pdf_pages(path):
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))


def test_輸出PDF_多頁一檔且檔名用版本名稱(server, projects_root):
    v = make_version(server, "練習用簡化版", n_bars=40)   # 40 小節 = 10 行
    code, r = export(server, v["id"], "pdf")
    assert code == 200
    f = exports_dir(projects_root) / "練習用簡化版.pdf"
    assert f.exists() and f.read_bytes()[:5] == b"%PDF-"
    assert r["files"] == ["練習用簡化版.pdf"]
    # 10 行排在 A4 直式：不會一頁塞完、也不會每行一頁
    assert 2 <= pdf_pages(f) <= 3
    assert r["pages"] == pdf_pages(f)


def test_輸出PNG_每頁一張且尺寸為A4直式(server, projects_root):
    from PIL import Image
    v = make_version(server, "原譜", n_bars=40)
    code, r = export(server, v["id"], "png")
    assert code == 200
    assert len(r["files"]) == r["pages"] >= 2
    for name in r["files"]:
        f = exports_dir(projects_root) / name
        assert f.suffix == ".png" and name.startswith("原譜")
        w, h = Image.open(f).size
        assert abs(h / w - 297 / 210) < 0.01


def test_短譜只有一頁(server, projects_root):
    v = make_version(server, "短", n_bars=4)
    _, r = export(server, v["id"], "pdf")
    assert r["pages"] == 1


def test_檔名非法字元被替換(server, projects_root):
    v = make_version(server, 'a/b:c?d*e"f<g>h|i\\j')
    code, r = export(server, v["id"], "pdf")
    assert code == 200
    assert r["files"] == ["a_b_c_d_e_f_g_h_i_j.pdf"]
    assert (exports_dir(projects_root) / "a_b_c_d_e_f_g_h_i_j.pdf").exists()


def test_同一版本再輸出會覆蓋(server, projects_root):
    v = make_version(server, "覆蓋測試", n_bars=40)
    _, r1 = export(server, v["id"], "png")
    assert r1["pages"] >= 2
    # 改短後再輸出：同名檔覆蓋，不留下舊的多餘頁
    call("POST", f"{server}/api/score?p={NAME}&v={v['id']}", big_score(4))
    _, r2 = export(server, v["id"], "png")
    assert r2["pages"] == 1
    pngs = sorted(p.name for p in exports_dir(projects_root).glob("覆蓋測試*.png"))
    assert pngs == r2["files"]
    # PDF 也一樣只有一個檔
    export(server, v["id"], "pdf")
    export(server, v["id"], "pdf")
    assert [p.name for p in exports_dir(projects_root).glob("覆蓋測試*.pdf")] == ["覆蓋測試.pdf"]


def test_可輸出AI譜(server, projects_root):
    code, r = export(server, "ai", "pdf")
    assert code == 200
    assert r["files"] == ["AI 譜.pdf"]


def test_百分比記號可選(server, projects_root):
    v = make_version(server, "重複譜", n_bars=40, same=True)
    _, r = export(server, v["id"], "png", simile=True)
    with_simile = (exports_dir(projects_root) / r["files"][0]).read_bytes()
    _, r = export(server, v["id"], "png", simile=False)
    without = (exports_dir(projects_root) / r["files"][0]).read_bytes()
    assert with_simile != without


def test_不合法的請求被拒絕(server):
    v = make_version(server, "x", n_bars=4)
    assert export(server, v["id"], "gif")[0] == 400
    assert export(server, "deadbeef", "pdf")[0] == 404
