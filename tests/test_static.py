"""前端靜態檔服務：只走 HTTP；用 --web-dist 指到暫存資料夾裡的假 build 產物。"""
import http.client
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

import pytest

from conftest import launch_server

INDEX = "<!doctype html><title>假前端</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text(INDEX, encoding="utf-8")
    (d / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (d / "assets" / "app-abc123.css").write_text("body{}", encoding="utf-8")
    (d / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("機密", encoding="utf-8")   # dist 之外
    return d


@pytest.fixture
def web(projects_root, dist):
    with launch_server(projects_root, args=["--web-dist", str(dist)]) as base:
        yield base


def get(base, path):
    try:
        r = urllib.request.urlopen(base + path)
    except urllib.error.HTTPError as e:
        r = e
    return r.status, r.headers, r.read()


def raw_get(base, path):
    """不讓 client 正規化路徑（要測 .. 跳脫）。"""
    u = urlparse(base)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read()


def test_根路徑回傳index_html_不快取(web):
    status, headers, body = get(web, "/")
    assert status == 200
    assert body.decode("utf-8") == INDEX
    assert headers["Content-Type"].startswith("text/html")
    assert headers["Cache-Control"] == "no-store"


def test_assets檔案帶正確型別與長快取(web):
    status, headers, body = get(web, "/assets/app-abc123.js")
    assert status == 200 and body == b"console.log(1)"
    assert headers["Content-Type"].startswith("text/javascript")
    assert "immutable" in headers["Cache-Control"]
    status, headers, _ = get(web, "/assets/app-abc123.css")
    assert headers["Content-Type"].startswith("text/css")


def test_根目錄的靜態檔回傳原檔_不長快取(web):
    status, headers, body = get(web, "/favicon.svg")
    assert status == 200 and body == b"<svg/>"
    assert headers["Content-Type"] == "image/svg+xml"
    assert headers["Cache-Control"] == "no-store"


def test_前端路由路徑回到index_html(web):
    for path in ("/editor?p=%E5%81%87%E6%AD%8C", "/some/deep/route", "/assets/not-exist.js"):
        status, _, body = get(web, path)
        assert status == 200 and body.decode("utf-8") == INDEX, path


def test_路徑跳脫被擋(web):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt", "/..%5csecret.txt", "/%00"):
        status, body = raw_get(web, path)
        assert "機密".encode("utf-8") not in body, path
        assert status in (200, 400, 404), path


def test_api與media不會被前端接走(web):
    assert get(web, "/api/nope")[0] == 404
    assert get(web, "/media/nope/video.mp4")[0] == 404
    assert get(web, "/media/x")[0] == 404
    status, _, body = get(web, "/api/projects")
    assert status == 200 and json.loads(body) == ["假歌"]


def test_沒有build時回503說明頁_API照常(projects_root, tmp_path):
    with launch_server(projects_root, args=["--web-dist", str(tmp_path / "沒有這個資料夾")]) as base:
        status, headers, body = get(base, "/")
        assert status == 503
        assert headers["Content-Type"].startswith("text/html")
        text = body.decode("utf-8")
        assert "npm install" in text and "npm run build" in text
        assert get(base, "/editor?p=x")[0] == 503
        status, _, body = get(base, "/api/projects")
        assert status == 200 and json.loads(body) == ["假歌"]
