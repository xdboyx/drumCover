"""扒譜核心（drumcover.build_score）的模式測試：基本扒譜用固定的合成輸入鎖住輸出，加強扒譜目前須與基本相同。

輸入全部程式合成（拍點、ADTOF 機率曲線、短音檔），不需要真實歌曲、網路、GPU 或模型。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
GOLDEN = Path(__file__).resolve().parent / "golden" / "score_basic.json"

SR = 16000
BARS = 8
BEAT = 0.5   # 120 BPM


def make_project(P):
    """8 小節 4/4：大鼓 1、3 拍，小鼓 2、4 拍，hi-hat 8 分，第 1 小節 crash，後半有幾下 tom，
    另放一些低於門檻的 hi-hat 弱峰值，讓上下文補洞也走一遍。"""
    import soundfile as sf
    P.mkdir(parents=True, exist_ok=True)
    n_beats = BARS * 4
    beats = [i * BEAT for i in range(n_beats + 1)]
    downbeats = [b * 4 * BEAT for b in range(BARS)]
    (P / "beats.json").write_text(json.dumps({"beats": beats, "downbeats": downbeats}))

    duration = BARS * 4 * BEAT
    frames = int(duration * 100) + 20
    drums = np.zeros((frames, 5), np.float32)   # BD SD TM HH CY
    mix = np.zeros((frames, 5), np.float32)

    def peak(a, c, t, h):
        i = int(round(t * 100))
        a[i, c] = h
        a[i - 1, c] = h * 0.4
        a[i + 1, c] = h * 0.4

    jitter = np.random.RandomState(0).randint(-2, 3, size=400) / 100.0
    k = 0
    for bar in range(BARS):
        for beat in range(4):
            t = (bar * 4 + beat) * BEAT
            if beat in (0, 2):
                peak(drums, 0, t + jitter[k], 0.9); k += 1
            else:
                peak(drums, 1, t + jitter[k], 0.8); k += 1
            for half in (0, 1):
                strong = not (bar in (2, 4) and beat == 3 and half == 1)
                peak(mix, 3, t + half * BEAT / 2 + jitter[k], 0.7 if strong else 0.15); k += 1
    peak(drums, 4, 0.0 + 0.02, 0.9)
    for t, h in ((12.0, 0.8), (12.25, 0.7), (12.5, 0.8), (12.75, 0.7), (13.0, 0.6)):
        peak(drums, 2, t, h)
    np.save(P / "act_drums.npy", drums)
    np.save(P / "act_mix.npy", mix)

    ts = np.arange(int(duration * SR)) / SR
    wave = (0.3 * np.sin(2 * np.pi * 180 * ts) * (np.sin(2 * np.pi * 2 * ts) > 0)
            + 0.2 * np.sin(2 * np.pi * 1200 * ts)).astype(np.float32)
    sf.write(str(P / "drums.wav"), wave, SR, subtype="PCM_16")
    sf.write(str(P / "mix.wav"), wave, SR, subtype="PCM_16")


def assert_same(a, b, path="score"):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            assert_same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            assert_same(x, y, f"{path}[{i}]")
    elif isinstance(a, float):
        assert b == pytest.approx(a, abs=1e-6), path
    else:
        assert a == b, path


def build(tmp_path, mode):
    import drumcover
    make_project(tmp_path / "p")
    score = drumcover.build_score(tmp_path / "p", mode=mode)
    return json.loads(json.dumps(score, ensure_ascii=False))


def test_basic_matches_golden(tmp_path):
    score = build(tmp_path, "basic")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert score["mode"] == "basic"
    assert_same(expected, score)


def test_default_mode_is_basic(tmp_path):
    import drumcover
    make_project(tmp_path / "p")
    assert drumcover.build_score(tmp_path / "p")["mode"] == "basic"


def test_enhanced_equals_basic_except_mode(tmp_path):
    basic = build(tmp_path / "a", "basic")
    enhanced = build(tmp_path / "b", "enhanced")
    assert enhanced.pop("mode") == "enhanced"
    basic.pop("mode")
    assert_same(basic, enhanced)


def test_unknown_mode_rejected(tmp_path):
    import drumcover
    make_project(tmp_path / "p")
    with pytest.raises(ValueError):
        drumcover.build_score(tmp_path / "p", mode="turbo")
