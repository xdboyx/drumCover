"""版本管理：AI 譜、舊 AI 譜、編輯版本的讀寫、唯讀規則、命名檢查。"""
import json
import re
import uuid
from datetime import datetime

from common import HttpError
from filenames import filename_key

AI = "ai"           # AI 譜（score.json）的版本 id，唯讀
AI_NAME = "AI 譜"
OLD_AI = "old_ai"   # 舊 AI 譜（versions/ 裡 meta.kind == "old_ai"），唯讀
DIFF_SEC = 0.1      # 新舊 AI 譜小節起點差超過這個秒數就算對不齊


def version_file(P, vid):
    if vid == AI:
        return P / "score.json"
    f = P / "versions" / f"{vid}.json"
    if not re.fullmatch(r"[0-9a-f]{8}", vid or "") or not f.exists():
        raise FileNotFoundError(f"版本 {vid}")
    return f


def read_version(P, vid):
    return json.loads(version_file(P, vid).read_text(encoding="utf-8"))


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


def save_version(P, vid, score, normalize):
    """存檔（覆蓋編輯版本）；AI 譜與舊 AI 譜拒絕。回傳存檔後的鼓譜。"""
    if vid == AI:
        raise HttpError(403, "AI 譜是唯讀的，請先複製成編輯版本")
    require_editable(P, vid)
    f = version_file(P, vid)
    meta = json.loads(f.read_text(encoding="utf-8")).get("meta", {})
    score = normalize(score)
    score["meta"] = meta   # 中繼資料以伺服器端為準
    f.write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8")
    return score
