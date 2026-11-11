"""即時預覽：鼓譜正規化、AI 信心（ADTOF 機率）、依鼓譜排版出譜面圖。"""
import base64
import io

import numpy as np

import drumcover as dc
from notation import Layout, LineRenderer

ACT_FPS = 100   # ADTOF 機率曲線的幀率（幀/秒）

renderer = LineRenderer(Layout(width=1920, height=280))
act_cache = {}


def window_max(col, t, half):
    """機率曲線在 t±half 秒窗內的最大值。"""
    return float(col[max(0, int((t - half) * ACT_FPS)):int((t + half) * ACT_FPS) + 1].max(initial=0))


def slot_levels(col, spans, divs, off):
    """每拍切成 divs 格，回傳每格（以格中心為準、窗半寬為格寬的一半）的最大機率，依拍序攤平。
    divs=4 是 16 分格，divs=3 是三連音格。"""
    levels = []
    for beat_start, beat_end in spans:
        beat_len = beat_end - beat_start
        for k in range(divs):
            center = beat_start + beat_len * k / divs + off
            levels.append(round(window_max(col, center, beat_len / (2 * divs)), 3))
    return levels


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
        out.append({cls: {"s16": slot_levels(act[:, c], spans, 4, off),
                          "t3": slot_levels(act[:, c], spans, 3, off)}
                    for c, cls in enumerate(dc.ACT_CLASSES)})
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
