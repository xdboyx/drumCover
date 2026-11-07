"""鼓譜圖檔輸出：把一份鼓譜排成 A4 直式，存成 PDF（多頁一檔）或 PNG（每頁一張）到專案的 exports/。"""
import os
import re

from notation import render_sheet

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = re.compile(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$")


def safe_filename(name):
    """版本名稱 -> Windows 可用的檔名（不含副檔名）。"""
    s = _ILLEGAL.sub("_", name).strip().rstrip(". ")
    if not s:
        s = "_"
    if _RESERVED.match(s):
        s = "_" + s
    return s


def export_sheet(P, score, display_measures, version_name, fmt, simile=True):
    """回傳 {"files": [...], "pages": n, "folder": str}。同一版本再輸出會覆蓋（含清掉多餘的舊頁）。"""
    pages = render_sheet(display_measures(score, simile), P.name, version_name, score.get("bpm") or 0)
    out = P / "exports"
    out.mkdir(exist_ok=True)
    stem = safe_filename(version_name)
    # 先清掉同版本的舊輸出（PDF 與 PNG 各清自己那一種）
    if fmt == "pdf":
        old = [out / f"{stem}.pdf"]
    else:
        old = [f for f in out.glob(f"{glob_escape(stem)}_*.png") if re.fullmatch(re.escape(stem) + r"_\d+\.png", f.name)]
    for f in old:
        if f.exists():
            f.unlink()
    if fmt == "pdf":
        f = out / f"{stem}.pdf"
        pages[0].save(f, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
        files = [f.name]
    else:
        files = []
        for i, pg in enumerate(pages, 1):
            f = out / f"{stem}_{i}.png"
            pg.save(f, "PNG")
            files.append(f.name)
    return {"files": files, "pages": len(pages), "folder": str(out)}


def glob_escape(s):
    return re.sub(r"([*?\[])", r"[\1]", s)


def open_folder(folder):
    os.startfile(folder)   # Windows 檔案總管
