"""逐小節鼓譜編輯器（本機伺服器）。

啟動：.venv/Scripts/python.exe tools/editor/server.py [--port 8765] [--projects-root DIR] [--open]
只綁 127.0.0.1。然後開 http://127.0.0.1:8765（--open 會自動開瀏覽器）
"""
import argparse
import base64
import io
import json
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8")

import drumcover as dc                      # noqa: E402
from notation import LineRenderer, Layout   # noqa: E402

# 編輯器的樂器列 -> ADTOF 類別（用來顯示模型信心）
ACT_CLASS = {"CR": "CY", "RD": "CY", "HH": "HH", "HO": "HH", "SD": "SD", "XS": "SD",
             "TH": "TM", "TM": "TM", "TF": "TM", "BD": "BD", "HF": None}
MEDIA = {"video.mp4": "video/mp4", "mix.wav": "audio/wav", "drums.wav": "audio/wav"}

PROJECTS_ROOT = ROOT / "projects"   # 可由 --projects-root 覆寫

renderer = LineRenderer(Layout(width=1920, height=280))
act_cache = {}
renders = {}   # name -> {"proc", "log"}


def project(name):
    p = PROJECTS_ROOT / name
    if not re.fullmatch(r"[\w\-]+", name) or not (p / "score.json").exists():
        raise FileNotFoundError(name)
    return p


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
        bt = b.get("beats") or list(np.linspace(b["t0"], b["t1"], 5))
        row = {}
        for c, cls in enumerate(dc.ACT_CLASSES):
            s16, t3 = [], []
            for j in range(len(bt) - 1):
                dur = bt[j + 1] - bt[j]
                for k, n, half in [(k, 4, dur / 8) for k in range(4)]:
                    t = bt[j] + dur * k / n + off
                    s16.append(float(act[max(0, int((t - half) * 100)):int((t + half) * 100) + 1, c].max(initial=0)))
                for k in range(3):
                    t = bt[j] + dur * k / 3 + off
                    half = dur / 6
                    t3.append(float(act[max(0, int((t - half) * 100)):int((t + half) * 100) + 1, c].max(initial=0)))
            row[cls] = {"s16": [round(v, 3) for v in s16], "t3": [round(v, 3) for v in t3]}
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


def render_line_png(bars, first_no, highlight):
    measures = [{"kind": "bar", "no": first_no + i, "ticks": b["ticks"],
                 "events": [{**e, "idx": k * 1000 + j} for j, e in enumerate(b["events"])]}
                for k, b in enumerate(bars)]
    img, _ = renderer.render_line(measures, show_header=False)
    if highlight is not None and 0 <= highlight < len(bars):
        L = renderer.L
        x0 = L.margin_l + 8 + L.clef_w
        bar_w = (L.width - L.margin_r - x0) / L.bars_per_line
        a = np.array(img).astype(np.int32)
        xa, xb = int(x0 + highlight * bar_w) + 3, int(x0 + (highlight + 1) * bar_w) - 3
        a[:, xa:xb] = a[:, xa:xb] * np.array([255, 246, 200]) // 255
        from PIL import Image
        img = Image.fromarray(a.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

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
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/projects":
                names = sorted(p.parent.name for p in PROJECTS_ROOT.glob("*/score.json"))
                return self._send(200, names)
            if u.path == "/api/score":
                P = project(q["p"])
                score = json.loads((P / "score.json").read_text(encoding="utf-8"))
                return self._send(200, {"score": score, "act": bar_activations(P, score),
                                        "has_auto": (P / "score.auto.json").exists(),
                                        "media": [m for m in MEDIA if (P / m).exists()]})
            if u.path == "/api/auto_bar":
                P = project(q["p"])
                auto = P / "score.auto.json"
                src = auto if auto.exists() else P / "score.json"
                bars = json.loads(src.read_text(encoding="utf-8"))["bars"]
                return self._send(200, bars[int(q["i"])])
            if u.path == "/api/render_status":
                r = renders.get(q["p"])
                if not r:
                    return self._send(200, {"state": "idle"})
                state = "running" if r["proc"].poll() is None else ("done" if r["proc"].returncode == 0 else "error")
                return self._send(200, {"state": state, "log": r["log"][-400:]})
            m = re.fullmatch(r"/media/([\w\-]+)/([\w.]+)", u.path)
            if m and m.group(2) in MEDIA:
                P = project(m.group(1))
                return self._media(P / m.group(2))
            self._send(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send(404, {"error": f"找不到 {e}"})

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/score":
                P = project(q["p"])
                score = normalize(self._body())
                auto = P / "score.auto.json"
                if not auto.exists():   # 第一次存檔前保留 AI 自動扒譜的原始版本
                    auto.write_text((P / "score.json").read_text(encoding="utf-8"), encoding="utf-8")
                (P / "score.json").write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8")
                return self._send(200, {"ok": True, "edited": sum(1 for b in score["bars"] if b.get("edited"))})
            if u.path == "/api/line":
                body = self._body()
                png = render_line_png(body["bars"], body["first_no"], body.get("highlight"))
                return self._send(200, {"png": base64.b64encode(png).decode()})
            if u.path == "/api/render":
                P = project(q["p"])
                body = self._body()
                r = renders.get(P.name)
                if r and r["proc"].poll() is None:
                    return self._send(409, {"error": "已經在輸出中"})
                cmd = [sys.executable, str(TOOLS / "drumcover.py"), "render", P.name,
                       "--crop-y", str(float(body.get("crop_y", 0.5)))]
                if not body.get("simile", True):
                    cmd.append("--no-simile")
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(ROOT))
                rec = {"proc": proc, "log": ""}
                renders[P.name] = rec

                def pump():
                    buf = b""
                    while True:
                        ch = proc.stdout.read(256)
                        if not ch:
                            break
                        buf += ch
                        rec["log"] = buf.decode("utf-8", "replace").replace("\r", "\n")
                threading.Thread(target=pump, daemon=True).start()
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send(404, {"error": f"找不到 {e}"})


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
