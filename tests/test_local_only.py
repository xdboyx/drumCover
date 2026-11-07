"""只接受本機請求：Host 必須是 127.0.0.1/localhost，POST 若帶 Origin 也必須是本機（防 DNS rebinding / CSRF）。"""
import http.client
from urllib.parse import urlparse


def raw(base, method, path, headers):
    u = urlparse(base)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    c.putrequest(method, path, skip_host=True)
    for k, v in headers.items():
        c.putheader(k, v)
    c.putheader("Content-Length", "2")
    c.endheaders(b"{}")
    r = c.getresponse()
    r.read()
    return r.status


def port(base):
    return urlparse(base).port


def test_本機Host可通過(server):
    assert raw(server, "GET", "/api/projects", {"Host": f"127.0.0.1:{port(server)}"}) == 200
    assert raw(server, "GET", "/api/projects", {"Host": f"localhost:{port(server)}"}) == 200


def test_外部Host被拒絕(server):
    assert raw(server, "GET", "/api/projects", {"Host": f"evil.example.com:{port(server)}"}) == 403
    assert raw(server, "GET", "/api/projects", {"Host": "evil.example.com"}) == 403
    assert raw(server, "POST", "/api/open_exports?p=x", {"Host": "evil.example.com"}) == 403


def test_POST帶外部Origin被拒絕_本機Origin通過(server):
    h = {"Host": f"127.0.0.1:{port(server)}"}
    assert raw(server, "POST", "/api/projects/retry?p=nope", {**h, "Origin": "http://evil.example.com"}) == 403
    assert raw(server, "POST", "/api/projects/retry?p=nope", {**h, "Origin": f"http://localhost:{port(server)}"}) == 404
    assert raw(server, "POST", "/api/projects/retry?p=nope", h) == 404