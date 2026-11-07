"""逐小節鼓譜編輯器（本機伺服器）。

啟動：.venv/Scripts/python.exe tools/editor/server.py [--port 8765] [--projects-root DIR] [--open]
只綁 127.0.0.1。然後開 http://127.0.0.1:8765（--open 會自動開瀏覽器）
"""
import argparse
import base64
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8")

import drumcover as dc                      # noqa: E402
import pipeline as real_pipeline            # noqa: E402
import sheet_export                         # noqa: E402
from filenames import ILLEGAL_CHARS, filename_key, is_reserved   # noqa: E402
from jobs import Busy, JobRunner            # noqa: E402
from notation import Layout, LineRenderer   # noqa: E402
from render_job import render_steps         # noqa: E402

# 編輯器的樂器列 -> ADTOF 類別（用來顯示模型信心）
ACT_CLASS = {"CR": "CY", "RD": "CY", "HH": "HH", "HO": "HH", "SD": "SD", "XS": "SD",
             "TH": "TM", "TM": "TM", "TF": "TM", "BD": "BD", "HF": None}
MEDIA = {"video.mp4": "video/mp4", "mix.wav": "audio/wav", "drums.wav": "audio/wav"}

PROJECTS_ROOT = ROOT / "projects"   # 可由 --projects-root 覆寫

renderer = LineRenderer(Layout(width=1920, height=280))
act_cache = {}
runner = JobRunner()   # 整個伺服器唯一的長時間工作執行器


class HttpError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


LOCAL_HOSTS = {"127.0.0.1", "localhost"}
AUDIO_SOURCES = ("drums", "mix", "max", "hybrid")


def check_name(name):
    """專案名稱：接受中文、空白等常見 YouTube 標題字元，擋掉 Windows 不允許的字元、路徑跳脫與保留字。回傳去頭尾空白的名稱。"""
    name = name.strip() if isinstance(name, str) else ""
    if not name:
        raise HttpError(400, "專案名稱不能空白")
    if len(name) > 80:
        raise HttpError(400, "專案名稱太長（最多 80 字）")
    if ILLEGAL_CHARS.search(name):
        raise HttpError(400, '專案名稱不能包含 < > : " / \\ | ? * 這些字元')
    if name.endswith(".") or is_reserved(name):
        raise HttpError(400, "專案名稱不合法（不能以 . 結尾，也不能用 Windows 保留字）")
    return name


def project_dir(name):
    """專案資料夾（不要求已經有 score.json，扒譜中或失敗的專案也找得到）。"""
    try:
        ok = check_name(name) == name
    except HttpError:
        ok = False
    p = PROJECTS_ROOT / name
    if not ok or not p.is_dir():
        raise FileNotFoundError(name)
    return p


def project(name):
    p = project_dir(name)
    if not (p / "score.json").exists():
        raise FileNotFoundError(name)
    return p


def pipeline():
    """扒譜流程：預設是真的 drumcover；環境變數 DRUMCOVER_PIPELINE 可指到另一個 .py（測試用假流程）。"""
    path = os.environ.get("DRUMCOVER_PIPELINE")
    if not path:
        return real_pipeline
    spec = importlib.util.spec_from_file_location("drumcover_fake_pipeline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def clean_source(source):
    source = (source or "").strip().strip('"').strip()
    if Path(source).is_file() and source.lower().endswith(".mp4"):
        return source
    if re.match(r"https?://", source, re.I):
        return source
    raise HttpError(400, "請輸入 YouTube 網址或本機 mp4 的完整路徑")


def import_steps(P, source, opts):
    """新增專案的扒譜步驟：下載 → 分離鼓聲 → 扒譜 → 排版。"""
    pl = pipeline()
    return [
        ("下載", lambda report: pl.download(P, source, opts, report)),
        ("分離鼓聲", lambda report: pl.separate(P, opts, report)),
        ("扒譜", lambda report: pl.transcribe(P, opts, report)),
        ("排版", lambda report: pl.score(P, opts, report)),
    ]


def submit_import(P, source, opts, start_at=0):
    """送出扒譜工作；忙碌時回傳 409。"""
    try:
        runner.submit("import", P.name, import_steps(P, source, opts), start_at=start_at)
    except Busy as e:
        return 409, {"error": str(e), "busy": True, "job": e.status}
    return 200, {"ok": True, "name": P.name}


def new_project(body):
    name = check_name(body.get("name"))
    source = clean_source(body.get("source"))
    audio = body.get("audio") or None
    if audio is not None and audio not in AUDIO_SOURCES:
        raise HttpError(400, f"扒譜音源必須是 {'/'.join(AUDIO_SOURCES)}")
    try:
        opts = {"start": max(0.0, float(body.get("start") or 0)), "dur": max(0.0, float(body.get("dur") or 0)),
                "audio": audio}
    except (TypeError, ValueError):
        raise HttpError(400, "開始秒數與長度必須是數字")
    P = PROJECTS_ROOT / name
    if P.exists():
        raise HttpError(409, f"專案「{name}」已存在，請換一個名稱")
    P.mkdir(parents=True)
    (P / "import.json").write_text(json.dumps({"source": source, "opts": opts}, ensure_ascii=False), encoding="utf-8")
    code, resp = submit_import(P, source, opts)
    if code != 200:
        shutil.rmtree(P, ignore_errors=True)
    return code, resp


def retry_project(name):
    """新增專案的扒譜失敗後重試：從失敗那一步開始，前面各步的中間檔沿用。"""
    P = project_dir(name)
    st = runner.status()
    failed_reimport = (st.get("state") == "error" and st.get("kind") == "reimport"
                       and st.get("project") == name and last_reimport.project == name)
    if failed_reimport:
        try:
            runner.submit("reimport", name, last_reimport.steps, start_at=st["failed_step"])
        except Busy as e:
            return 409, {"error": str(e), "busy": True, "job": e.status}
        return 200, {"ok": True, "name": name}
    f = P / "import.json"
    if not f.exists() or (P / "score.json").exists():
        raise HttpError(400, "這個專案不是扒譜失敗的專案，不能重試")
    d = json.loads(f.read_text(encoding="utf-8"))
    failed_here = st.get("state") == "error" and st.get("project") == name and st.get("kind") == "import"
    return submit_import(P, d["source"], d["opts"], st["failed_step"] if failed_here else 0)


def bars_misaligned(old_bars, new_bars):
    """逐小節比對 t0，差超過 DIFF_SEC 的小節編號（0 起算）；一邊沒有對應小節的也算。"""
    out = []
    for i in range(max(len(old_bars), len(new_bars))):
        if i >= len(old_bars) or i >= len(new_bars) or abs(old_bars[i]["t0"] - new_bars[i]["t0"]) > DIFF_SEC:
            out.append(i)
    return out


def reimport_steps(P, opts):
    """重新扒譜：保存舊 AI 譜 → 扒譜 → 排版 → 比對新舊 AI 譜。失敗時 AI 譜沒變就不留下多餘的舊 AI 譜。"""
    pl = pipeline()
    st = {}

    def snapshot(report=None):
        f = st.get("file")
        if f and f.exists():
            return   # 重試時前面已經保存過
        now = datetime.now()
        vid = uuid.uuid4().hex[:8]
        data = json.loads((P / "score.json").read_text(encoding="utf-8"))
        data["meta"] = {"name": f"舊 AI 譜（{now:%Y-%m-%d %H:%M:%S}）", "kind": OLD_AI, "source": None,
                        "created": now.isoformat(timespec="seconds")}
        (P / "versions").mkdir(exist_ok=True)
        f = P / "versions" / f"{vid}.json"
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        st.update(id=vid, file=f, before=(P / "score.json").read_bytes())

    def guard(fn):
        def run(report):
            try:
                snapshot()   # 重試從中間步驟開始時，失敗當下已清掉快照，這裡補回
                fn(report)
            except BaseException:
                if (P / "score.json").read_bytes() == st["before"]:
                    st["file"].unlink(missing_ok=True)
                raise
        return run

    def compare(report):
        f = st["file"]
        old = json.loads(f.read_text(encoding="utf-8"))
        new = json.loads((P / "score.json").read_text(encoding="utf-8"))
        old["meta"]["diff_bars"] = bars_misaligned(old["bars"], new["bars"])
        old["meta"]["replaced_at"] = datetime.now().isoformat(timespec="seconds")
        f.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")

    return [("保存舊 AI 譜", snapshot),
            ("扒譜", guard(lambda report: pl.transcribe(P, opts, report, force=True))),   # 已有的 act_*.npy / beats.json 也要重做
            ("排版", guard(lambda report: pl.score(P, opts, report))),
            ("比對", compare)]


class _LastReimport:
    """最近一次重新扒譜的專案名稱與步驟組。

    步驟組閉包裡存著舊 AI 譜快照的狀態，失敗重試時必須沿用同一組，所以要記住。
    生命週期：每次送出重新扒譜就整組覆蓋；只存在這個伺服器行程的記憶體，重啟即消失
    （重啟後的失敗重試資訊不持久化，是已知的暫不處理項目）。只有 reimport_project 寫入、retry_project 讀取。
    """
    project = None
    steps = None

    def set(self, project, steps):
        self.project, self.steps = project, steps


last_reimport = _LastReimport()


def reimport_project(name):
    P = project(name)   # 沒有 AI 譜的專案（還沒扒完）不能重新扒譜
    f = P / "import.json"
    opts = json.loads(f.read_text(encoding="utf-8")).get("opts", {}) if f.exists() else {}
    try:
        steps = reimport_steps(P, opts)
        runner.submit("reimport", P.name, steps)
    except Busy as e:
        return 409, {"error": str(e), "busy": True, "job": e.status}
    last_reimport.set(P.name, steps)
    return 200, {"ok": True, "name": P.name}


def project_list():
    st = runner.status()
    out = []
    for d in sorted(p for p in PROJECTS_ROOT.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        on_me = st.get("project") == d.name
        mine = on_me and st.get("kind") == "import"
        item = {"name": d.name, "status": "ready", "error": None}
        if on_me and st.get("kind") == "reimport" and st["state"] == "error":
            item.update(reimport_error=st["error"], reimport_failed_step=st["steps"][st["failed_step"]])
        if on_me and st["state"] == "running" and st.get("kind") in ("import", "reimport"):
            item.update(status="running", step=st["step"], progress=st["progress"])
        elif mine and st["state"] == "error":
            item.update(status="failed", error=st["error"], failed_step=st["steps"][st["failed_step"]])
        elif not (d / "score.json").exists():
            item.update(status="failed", error="上次扒譜沒有完成（可以重試）")
        out.append(item)
    return out


AI = "ai"   # AI 譜（score.json）的版本 id，唯讀


def version_file(P, vid):
    if vid == AI:
        return P / "score.json"
    f = P / "versions" / f"{vid}.json"
    if not re.fullmatch(r"[0-9a-f]{8}", vid or "") or not f.exists():
        raise FileNotFoundError(f"版本 {vid}")
    return f


def read_version(P, vid):
    return json.loads(version_file(P, vid).read_text(encoding="utf-8"))


OLD_AI = "old_ai"   # 舊 AI 譜（versions/ 裡 meta.kind == "old_ai"），唯讀
DIFF_SEC = 0.1      # 新舊 AI 譜小節起點差超過這個秒數就算對不齊


def list_versions(P):
    out = [{"id": AI, "name": AI_NAME, "kind": "ai", "source": None, "created": None}]
    metas, olds = [], []
    for f in (P / "versions").glob("*.json"):
        m = json.loads(f.read_text(encoding="utf-8")).get("meta", {})
        kind = OLD_AI if m.get("kind") == OLD_AI else "edited"
        metas.append({"id": f.stem, "name": m.get("name", f.stem), "kind": kind,
                      "source": m.get("source"), "created": m.get("created")})
        if kind == OLD_AI:
            olds.append((m.get("replaced_at") or "", f.stem, m.get("diff_bars") or []))
    out += sorted(metas, key=lambda v: (v["created"] or "", v["id"]))
    ids = {v["id"]: v for v in out}
    for v in out:
        v["source_deleted"] = bool(v["source"]) and v["source"] not in ids
    olds.sort()
    diffs = {oid: bars for _, oid, bars in olds}
    for v in out:
        if v["kind"] == "edited":
            oid = derived_old_ai(v, ids, olds)
            if oid and diffs[oid]:
                v["warning"] = {"old_ai": oid, "bars": diffs[oid],
                                "message": f"新的 AI 譜有 {len(diffs[oid])} 個小節的起點跟這個版本根據的舊 AI 譜差超過 {DIFF_SEC} 秒，可能跟影片對不齊"}
    return out


def derived_old_ai(v, by_id, olds):
    """這個編輯版本是從哪一份舊 AI 譜衍生的（沿來源鏈往上找）。
    來源是「AI 譜」的版本，指的是它建立當時的 AI 譜，也就是在它之後第一個被取代下來的舊 AI 譜。"""
    seen = set()
    while v and v["id"] not in seen:
        seen.add(v["id"])
        src = v["source"]
        if src == AI:
            return next((oid for rep, oid, _ in olds if rep and (v["created"] or "") <= rep), None)
        if src in by_id and by_id[src]["kind"] == OLD_AI:
            return src
        v = by_id.get(src)
    return None


def require_editable(P, vid):
    if vid == AI:
        raise HttpError(403, "AI 譜不能存檔、改名或刪除")
    if read_version(P, vid).get("meta", {}).get("kind") == OLD_AI:
        raise HttpError(403, "舊 AI 譜是唯讀的，不能存檔、改名或刪除；可以從它複製新版本")


AI_NAME = "AI 譜"


def version_name(score, vid):
    """版本的顯示名稱（也是輸出檔名的來源）。"""
    return AI_NAME if vid == AI else score.get("meta", {}).get("name", vid)


def check_version_name(P, name, exclude=None):
    """版本名稱：不能空白，也不能跟同專案其他版本（含保留的「AI 譜」）重複，
    包含轉成檔名後會撞檔的名稱（輸出檔以名稱命名，撞名會互相覆蓋）。回傳去頭尾空白的名稱。"""
    name = (name or "").strip()
    if not name:
        raise HttpError(400, "版本名稱不能空白")
    taken = {filename_key(AI_NAME)}
    for f in (P / "versions").glob("*.json"):
        if f.stem != exclude:
            taken.add(filename_key(version_name(json.loads(f.read_text(encoding="utf-8")), f.stem)))
    if filename_key(name) in taken:
        raise HttpError(409, f"版本名稱「{name}」跟其他版本重複（或輸出檔名會相同），請換一個名稱")
    return name


def rename_version(P, vid, name):
    require_editable(P, vid)
    name = check_version_name(P, name, exclude=vid)
    f = version_file(P, vid)
    d = json.loads(f.read_text(encoding="utf-8"))
    d.setdefault("meta", {})["name"] = name
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": vid, "name": name}


def delete_version(P, vid):
    require_editable(P, vid)
    version_file(P, vid).unlink()


def restore_bar(P, vid, i):
    """某小節「還原成來源版本」：來源存在取來源的，否則取 AI 譜的。只回傳內容，不改檔。"""
    if vid == AI:
        raise HttpError(403, "AI 譜沒有來源版本")
    src = read_version(P, vid).get("meta", {}).get("source") or AI
    try:
        bars = read_version(P, src)["bars"]
    except FileNotFoundError:
        bars = read_version(P, AI)["bars"]
    if not 0 <= i < len(bars):
        raise FileNotFoundError(f"小節 {i}")
    return bars[i]


def create_version(P, name, source):
    name = check_version_name(P, name)
    score = read_version(P, source)
    score.pop("meta", None)
    vid = uuid.uuid4().hex[:8]
    meta = {"name": name, "source": source, "created": datetime.now().isoformat(timespec="seconds")}
    (P / "versions").mkdir(exist_ok=True)
    (P / "versions" / f"{vid}.json").write_text(
        json.dumps({**score, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": vid, "name": name, "kind": "edited", "source": source, "created": meta["created"]}


ACT_FPS = 100   # ADTOF 機率曲線的幀率（幀/秒）


def window_max(col, t, half):
    """機率曲線在 t±half 秒窗內的最大值。"""
    return float(col[max(0, int((t - half) * ACT_FPS)):int((t + half) * ACT_FPS) + 1].max(initial=0))


def bar_activations(P, score):
    """每小節每個 ADTOF 類別在每個 16 分格（16 格）與三連音格（12 格）的最大擊打機率。"""
    key = (str(P), score.get("offset_ms"), len(score["bars"]))
    if key in act_cache:
        return act_cache[key]
    try:
        act = dc.load_activations(P, "hybrid")
    except FileNotFoundError:
        return None
    off = (score.get("offset_ms") or 0) / 1000
    out = []
    for b in score["bars"]:
        beats = b.get("beats") or list(np.linspace(b["t0"], b["t1"], 5))
        spans = list(zip(beats[:-1], beats[1:]))   # 每拍 (起, 止)
        row = {}
        for c, cls in enumerate(dc.ACT_CLASSES):
            row[cls] = {
                "s16": [round(window_max(act[:, c], t0 + (t1 - t0) * k / 4 + off, (t1 - t0) / 8), 3)
                        for t0, t1 in spans for k in range(4)],
                "t3": [round(window_max(act[:, c], t0 + (t1 - t0) * k / 3 + off, (t1 - t0) / 6), 3)
                       for t0, t1 in spans for k in range(3)],
            }
        out.append(row)
    act_cache[key] = out
    return out


def normalize(score):
    """依 tick 重算每個事件的時間與編號（編輯器只改 tick / notes）。"""
    idx = 0
    for b in score["bars"]:
        evs = sorted((e for e in b["events"] if e["notes"]), key=lambda e: e["tick"])
        for e in evs:
            e["t"] = dc.tick_time(b, e["tick"]) if "beats" in b else b["t0"] + (b["t1"] - b["t0"]) * e["tick"] / b["ticks"]
            e["idx"] = idx
            e["notes"] = sorted(set(e["notes"]))
            idx += 1
        b["events"] = evs
    return score


def preview_line(body):
    """即時預覽：依傳入（可含未存檔修改）的鼓譜，回傳第 line 行的譜面圖、游標位置 [t, x]，
    以及每一行的時間範圍（前端據此由影片時間找出該顯示哪一行）。與練習影片用同一套排版。"""
    score = normalize(body["score"])
    simile = body.get("simile", True)
    lines = dc.lines_of(score, simile=simile)
    li = int(body.get("line", 0))
    if not 0 <= li < len(lines):
        raise FileNotFoundError(f"第 {li} 行")
    ms = lines[li]
    img, xs = renderer.render_line(ms, show_header=li == 0, is_last_line=li == len(lines) - 1,
                                   tempo=int(round(score["bpm"])))
    t0, t1 = ms[0]["t0"], ms[-1]["t1"]
    evs = sorted((e["t"], xs[e["idx"]]) for m in ms for e in m["events"] if e["idx"] in xs)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    L = renderer.L
    bx = L.margin_l + 8 + L.clef_w + (L.header_w if li == 0 else 0)
    bar_w = (L.width - L.margin_r - bx) / L.bars_per_line
    cw = int(L.sp * 1.6)   # 與 notation.render_cursor 的游標範圍一致
    return {"png": base64.b64encode(buf.getvalue()).decode(), "t0": t0, "t1": t1,
            "evs": [[t, x] for t, x in evs], "width": L.width, "height": L.height,
            "cursor": {"dx": cw / 2 - L.sp * 0.15, "w": cw, "y0": int(L.y(-7.5)), "y1": int(L.y(13))},
            "measures": [{"x0": bx + k * bar_w, "x1": bx + (k + 1) * bar_w, "bar": m["no"] - 1, "t0": m["t0"]}
                         for k, m in enumerate(ms)],
            "lines": [[ms[0]["t0"], ms[-1]["t1"]] for ms in lines]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _local_only(self, post):
        """擋 DNS rebinding / CSRF：Host 必須是本機（含埠），POST 帶 Origin 時也必須是本機。"""
        host = urlparse("//" + (self.headers.get("Host") or "")).hostname
        if host not in LOCAL_HOSTS:
            self._send(403, {"error": "只接受本機（127.0.0.1 / localhost）的請求"})
            return False
        origin = self.headers.get("Origin")
        if post and origin is not None and (urlparse(origin).hostname not in LOCAL_HOSTS):
            self._send(403, {"error": "不接受來自其他網站的請求"})
            return False
        return True

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def _media(self, path):
        """支援 Range 的靜態檔（影片/音訊拖曳播放需要）。"""
        size = path.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = min(int(m.group(2)), size - 1)
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", MEDIA[path.name])
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            try:
                while remaining > 0:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass

    def do_GET(self):
        if not self._local_only(False):
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/home.html"):
                return self._send(200, (HERE / "home.html").read_bytes(), "text/html; charset=utf-8")
            if u.path in ("/editor", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/project_list":
                return self._send(200, project_list())
            if u.path == "/api/project_title":
                src = clean_source(q.get("source"))
                try:
                    title = Path(src).stem if Path(src).is_file() else pipeline().title(src)
                except RuntimeError as e:
                    raise HttpError(502, str(e))
                return self._send(200, {"title": title})
            if u.path == "/api/projects":
                names = sorted(p.parent.name for p in PROJECTS_ROOT.glob("*/score.json"))
                return self._send(200, names)
            if u.path == "/api/score":
                P = project(q["p"])
                vid = q.get("v", AI)
                score = read_version(P, vid)
                return self._send(200, {"score": score, "version": vid, "act": bar_activations(P, score),
                                        "media": [m for m in MEDIA if (P / m).exists()]})
            if u.path == "/api/versions":
                return self._send(200, list_versions(project(q["p"])))
            if u.path == "/api/restore_bar":
                return self._send(200, restore_bar(project(q["p"]), q["v"], int(q["i"])))
            if u.path == "/api/job":
                return self._send(200, runner.status())
            m = re.fullmatch(r"/media/([^/]+)/([\w.]+)", u.path)
            if m and m.group(2) in MEDIA:
                P = project(unquote(m.group(1)))
                return self._media(P / m.group(2))
            self._send(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send(404, {"error": f"找不到 {e}"})
        except HttpError as e:
            self._send(e.code, {"error": e.msg})

    def do_POST(self):
        if not self._local_only(True):
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/projects/new":
                return self._send(*new_project(self._body()))
            if u.path == "/api/projects/reimport":
                return self._send(*reimport_project(q.get("p")))
            if u.path == "/api/projects/retry":
                return self._send(*retry_project(q.get("p")))
            if u.path == "/api/score":
                P = project(q["p"])
                vid = q.get("v", AI)
                if vid == AI:
                    raise HttpError(403, "AI 譜是唯讀的，請先複製成編輯版本")
                require_editable(P, vid)
                f = version_file(P, vid)
                meta = json.loads(f.read_text(encoding="utf-8")).get("meta", {})
                score = normalize(self._body())
                score["meta"] = meta   # 中繼資料以伺服器端為準
                f.write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8")
                return self._send(200, {"ok": True, "edited": sum(1 for b in score["bars"] if b.get("edited"))})
            if u.path == "/api/versions":
                body = self._body()
                return self._send(200, create_version(project(q["p"]), body.get("name"), body.get("source", AI)))
            if u.path == "/api/export_sheet":
                P = project(q["p"])
                body = self._body()
                if body.get("format") not in ("pdf", "png"):
                    raise HttpError(400, "format 必須是 pdf 或 png")
                vid = body.get("version", AI)
                score = read_version(P, vid)
                name = version_name(score, vid)
                return self._send(200, sheet_export.export_sheet(
                    P, score, dc.display_measures, name, body["format"], body.get("simile", True)))
            if u.path == "/api/open_exports":
                P = project(q["p"])
                (P / "exports").mkdir(exist_ok=True)
                sheet_export.open_folder(str(P / "exports"))
                return self._send(200, {"ok": True})
            if u.path == "/api/version/rename":
                return self._send(200, rename_version(project(q["p"]), q["v"], self._body().get("name")))
            if u.path == "/api/version/delete":
                delete_version(project(q["p"]), q["v"])
                return self._send(200, {"ok": True})
            if u.path == "/api/preview_line":
                return self._send(200, preview_line(self._body()))
            if u.path == "/api/render":
                P = project(q["p"])
                vid = q.get("v", AI)
                body = self._body()
                score = read_version(P, vid)   # 送出當下的鼓譜；render 讀快照，之後再改版本不影響
                name = version_name(score, vid)
                steps, out, discard = render_steps(PROJECTS_ROOT, P, name, score,
                                                   float(body.get("crop_y", 0.5)), body.get("simile", True))
                try:
                    runner.submit("render", P.name, steps, output=out.relative_to(P).as_posix())
                except Busy as e:
                    discard()
                    return self._send(409, {"error": str(e), "busy": True, "job": e.status})
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send(404, {"error": f"找不到 {e}"})
        except HttpError as e:
            self._send(e.code, {"error": e.msg})


def main():
    global PROJECTS_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--projects-root", type=Path, default=PROJECTS_ROOT, help="專案根目錄（預設 projects/）")
    ap.add_argument("--open", action="store_true", help="啟動後自動開瀏覽器")
    a = ap.parse_args()
    PROJECTS_ROOT = a.projects_root.resolve()
    url = f"http://127.0.0.1:{a.port}"
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"鼓譜編輯器：{url}（關閉此視窗即結束）", flush=True)
    if a.open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
