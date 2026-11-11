"""專案：命名驗證、專案清單、新增、失敗重試、重新扒譜。"""
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from common import HttpError, pipeline, runner, settings
from filenames import ILLEGAL_CHARS, is_reserved
from jobs import Busy
from versions import DIFF_SEC, OLD_AI

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
    p = settings.projects_root / name
    if not ok or not p.is_dir():
        raise FileNotFoundError(name)
    return p


def project(name):
    p = project_dir(name)
    if not (p / "score.json").exists():
        raise FileNotFoundError(name)
    return p


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
    P = settings.projects_root / name
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


_score_cache = {}   # score.json 路徑 -> ((mtime_ns, size), {bpm, bars, duration})
_kind_cache = {}    # versions/*.json 路徑 -> ((mtime_ns, size), 是否為編輯版本)


def _stat_key(f):
    s = f.stat()
    return (s.st_mtime_ns, s.st_size)


def _score_summary(f):
    """score.json 的 bpm／小節數／長度；依檔案 mtime 與大小快取，輪詢時不重讀。讀不到回傳 {}。"""
    try:
        key = _stat_key(f)
        hit = _score_cache.get(f)
        if hit and hit[0] == key:
            return hit[1]
        d = json.loads(f.read_text(encoding="utf-8"))
        info = {"bpm": d.get("bpm"), "bars": len(d.get("bars") or []), "duration": d.get("duration")}
        info = {k: v for k, v in info.items() if v is not None}
        _score_cache[f] = (key, info)
        return info
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def _is_edited(f):
    try:
        key = _stat_key(f)
        hit = _kind_cache.get(f)
        if hit and hit[0] == key:
            return hit[1]
        meta = json.loads(f.read_text(encoding="utf-8")).get("meta") or {}
        edited = meta.get("kind") != OLD_AI
        _kind_cache[f] = (key, edited)
        return edited
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def _extra_info(d):
    """清單用的辨識資訊：bpm、bars、duration、versions（編輯版本數）、updated（score.json 與 versions/*.json 最新修改時間）。
    讀不到的欄位省略，不能讓清單失敗。"""
    info = {}
    mtimes = []
    score = d / "score.json"
    if score.exists():
        info.update(_score_summary(score))
        try:
            mtimes.append(score.stat().st_mtime)
        except OSError:
            pass
    vdir = d / "versions"
    if vdir.is_dir():
        count = 0
        for f in vdir.glob("*.json"):
            try:
                mtimes.append(f.stat().st_mtime)
            except OSError:
                continue
            if _is_edited(f):
                count += 1
        info["versions"] = count
    elif score.exists():
        info["versions"] = 0
    if mtimes:
        info["updated"] = datetime.fromtimestamp(max(mtimes)).isoformat(timespec="seconds")
    return info


def project_list():
    st = runner.status()
    out = []
    for d in sorted(p for p in settings.projects_root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        on_me = st.get("project") == d.name
        mine = on_me and st.get("kind") == "import"
        item = {"name": d.name, "status": "ready", "error": None, **_extra_info(d)}
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
