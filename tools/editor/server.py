"""逐小節鼓譜編輯器（本機伺服器）。

啟動：.venv/Scripts/python.exe tools/editor/server.py [--port 8765] [--projects-root DIR] [--web-dist DIR] [--open]
只綁 127.0.0.1。然後開 http://127.0.0.1:8765（--open 會自動開瀏覽器）

這個檔案只管進入點、HTTP 處理與路由；各領域邏輯在同資料夾的模組：
common（共用）、projects（專案）、versions（版本）、preview（預覽）。
"""
import argparse
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import common                                   # noqa: F401  (先把 tools/ 加進 sys.path)
sys.stdout.reconfigure(encoding="utf-8")

import drumcover as dc                          # noqa: E402
import sheet_export                             # noqa: E402
from common import HttpError, pipeline, runner, settings   # noqa: E402
from jobs import Busy                           # noqa: E402
from preview import bar_activations, normalize, preview_line   # noqa: E402
from projects import (clean_source, new_project, project, project_list, reimport_project,   # noqa: E402
                      retry_project)
from render_job import render_steps             # noqa: E402
from versions import (AI, create_version, delete_version, list_versions, read_version,   # noqa: E402
                      rename_version, restore_bar, save_version, version_name)

LOCAL_HOSTS = {"127.0.0.1", "localhost"}
MEDIA = {"video.mp4": "video/mp4", "mix.wav": "audio/wav", "drums.wav": "audio/wav"}

# 前端靜態檔的 Content-Type（mimetypes 在 Windows 會讀登錄檔，結果不穩，所以自己列）
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".txt": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}
IMMUTABLE = "public, max-age=31536000, immutable"   # assets/ 下的檔名帶 hash

NO_BUILD_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>前端尚未建置</title>
<style>body{font-family:"Microsoft JhengHei",sans-serif;max-width:40em;margin:4em auto;padding:0 1em;line-height:1.7}
code{background:#eee;padding:.1em .4em;border-radius:3px}</style></head>
<body><h1>前端尚未建置</h1>
<p>找不到 <code>tools/editor/web/dist/index.html</code>。請先建置前端：</p>
<ol>
<li>安裝 Node.js</li>
<li>在 <code>tools/editor/web</code> 執行 <code>npm install</code>，再執行 <code>npm run build</code></li>
</ol>
<p>或直接雙擊根目錄的 <code>啟動操作介面.bat</code>，它會自動建置。</p>
<p>API（<code>/api/...</code>）不受影響，可以正常使用。</p></body></html>
"""


# ---- 路由：每個處理函式收 (handler, query, body) 回傳 (狀態碼, 內容) ----
# GET 沒有 body；POST 的 body 是請求內文解析出的 JSON，讀取時才解析。

def _ok(body):
    return 200, body


def get_project_title(h, q):
    src = clean_source(q.get("source"))
    try:
        title = Path(src).stem if Path(src).is_file() else pipeline().title(src)
    except RuntimeError as e:
        raise HttpError(502, str(e))
    return _ok({"title": title})


def get_score(h, q):
    P = project(q["p"])
    vid = q.get("v", AI)
    score = read_version(P, vid)
    return _ok({"score": score, "version": vid, "act": bar_activations(P, score),
                "media": [m for m in MEDIA if (P / m).exists()]})


def post_score(h, q):
    P = project(q["p"])
    vid = q.get("v", AI)
    score = save_version(P, vid, h.body(), normalize)
    return _ok({"ok": True, "edited": sum(1 for b in score["bars"] if b.get("edited"))})


def post_version_create(h, q):
    body = h.body()
    return _ok(create_version(project(q["p"]), body.get("name"), body.get("source", AI)))


def post_export_sheet(h, q):
    P = project(q["p"])
    body = h.body()
    if body.get("format") not in ("pdf", "png"):
        raise HttpError(400, "format 必須是 pdf 或 png")
    vid = body.get("version", AI)
    score = read_version(P, vid)
    name = version_name(score, vid)
    return _ok(sheet_export.export_sheet(P, score, dc.display_measures, name, body["format"], body.get("simile", True)))


def post_open_exports(h, q):
    P = project(q["p"])
    (P / "exports").mkdir(exist_ok=True)
    sheet_export.open_folder(str(P / "exports"))
    return _ok({"ok": True})


def post_version_delete(h, q):
    delete_version(project(q["p"]), q["v"])
    return _ok({"ok": True})


def post_render(h, q):
    P = project(q["p"])
    vid = q.get("v", AI)
    body = h.body()
    score = read_version(P, vid)   # 送出當下的鼓譜；render 讀快照，之後再改版本不影響
    name = version_name(score, vid)
    steps, out, discard = render_steps(settings.projects_root, P, name, score,
                                       float(body.get("crop_y", 0.5)), body.get("simile", True))
    try:
        runner.submit("render", P.name, steps, output=out.relative_to(P).as_posix())
    except Busy as e:
        discard()
        return 409, {"error": str(e), "busy": True, "job": e.status}
    return _ok({"ok": True})


GET_ROUTES = {
    "/api/project_list": lambda h, q: _ok(project_list()),
    "/api/project_title": get_project_title,
    "/api/projects": lambda h, q: _ok(sorted(p.parent.name for p in settings.projects_root.glob("*/score.json"))),
    "/api/score": get_score,
    "/api/versions": lambda h, q: _ok(list_versions(project(q["p"]))),
    "/api/restore_bar": lambda h, q: _ok(restore_bar(project(q["p"]), q["v"], int(q["i"]))),
    "/api/job": lambda h, q: _ok(runner.status()),
}

POST_ROUTES = {
    "/api/projects/new": lambda h, q: new_project(h.body()),
    "/api/projects/reimport": lambda h, q: reimport_project(q.get("p")),
    "/api/projects/retry": lambda h, q: retry_project(q.get("p")),
    "/api/score": post_score,
    "/api/versions": post_version_create,
    "/api/export_sheet": post_export_sheet,
    "/api/open_exports": post_open_exports,
    "/api/version/rename": lambda h, q: _ok(rename_version(project(q["p"]), q["v"], h.body().get("name"))),
    "/api/version/delete": post_version_delete,
    "/api/preview_line": lambda h, q: _ok(preview_line(h.body())),
    "/api/render": post_render,
}


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

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
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

    def _static(self, url_path):
        """React build 產物：有對應檔案就回傳，否則回 index.html（SPA fallback）；還沒 build 回 503 說明頁。"""
        dist = settings.web_dist.resolve()
        index = dist / "index.html"
        if not index.is_file():
            return self._send(503, NO_BUILD_PAGE, "text/html; charset=utf-8")
        rel = unquote(url_path).lstrip("/")
        target = None
        if rel:
            try:
                cand = (dist / rel).resolve()
                if cand.is_relative_to(dist) and cand.is_file():
                    target = cand
            except (ValueError, OSError):
                pass   # 含 NUL 等非法路徑：當成找不到
        if target is None:
            target = index
        cache = IMMUTABLE if target.parent.name == "assets" and target != index else "no-store"
        ctype = STATIC_TYPES.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype, cache)

    def _dispatch(self, routes, post):
        if not self._local_only(post):
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            route = routes.get(u.path)
            if route:
                return self._send(*route(self, q))
            if u.path.startswith("/api/"):
                return self._send(404, {"error": "not found"})
            if not post:
                m = re.fullmatch(r"/media/([^/]+)/([\w.]+)", u.path)
                if m and m.group(2) in MEDIA:
                    return self._media(project(unquote(m.group(1))) / m.group(2))
                if not u.path.startswith("/media/"):
                    return self._static(u.path)
            self._send(404, {"error": "not found"})
        except FileNotFoundError as e:
            self._send(404, {"error": f"找不到 {e}"})
        except HttpError as e:
            self._send(e.code, {"error": e.msg})

    def do_GET(self):
        self._dispatch(GET_ROUTES, False)

    def do_POST(self):
        self._dispatch(POST_ROUTES, True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--projects-root", type=Path, default=settings.projects_root, help="專案根目錄（預設 projects/）")
    ap.add_argument("--web-dist", type=Path, default=settings.web_dist, help="前端 build 產物資料夾（預設 tools/editor/web/dist）")
    ap.add_argument("--open", action="store_true", help="啟動後自動開瀏覽器")
    a = ap.parse_args()
    settings.projects_root = a.projects_root.resolve()
    settings.web_dist = a.web_dist.resolve()
    url = f"http://127.0.0.1:{a.port}"
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"鼓譜編輯器：{url}（關閉此視窗即結束）", flush=True)
    if a.open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
