import json
import urllib.parse
import urllib.request

from conftest import FAKE_SCORE


def get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read().decode("utf-8"))


def test_列出專案(server):
    assert get_json(server + "/api/projects") == ["假歌"]


def test_讀取鼓譜(server):
    name = urllib.parse.quote("假歌")
    data = get_json(f"{server}/api/score?p={name}")
    assert data["score"]["bpm"] == FAKE_SCORE["bpm"]
    assert len(data["score"]["bars"]) == 1
