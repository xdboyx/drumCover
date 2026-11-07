"""鼓譜影片流水線。

用法（在 F:\\drumCover 底下，用 .venv 的 python）：
    python tools/drumcover.py all      <name> --url <youtube url>
    python tools/drumcover.py download <name> --url <youtube url>
    python tools/drumcover.py analyze  <name>     # 分離鼓聲 + 扒譜 + 拍點
    python tools/drumcover.py score    <name>     # 量化成 score.json + 預覽圖
    python tools/drumcover.py render   <name> [--start 0 --dur 20]

所有中間檔放在 projects/<name>/。
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def proj(name):
    p = ROOT / "projects" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def run(cmd):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


# ---------------------------------------------------------------- download
def cmd_download(a):
    P = proj(a.name)
    run([sys.executable, "-m", "yt_dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
         "--merge-output-format", "mp4", "--no-progress", "--ffmpeg-location", ffmpeg_exe(),
         "-o", P / "video.mp4", "--no-playlist", a.url])
    extract_audio(P)


def extract_audio(P):
    run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", P / "video.mp4", "-vn", "-ac", "2", "-ar", "44100",
         P / "mix.wav"])


# ---------------------------------------------------------------- analyze
def cmd_analyze(a):
    P = proj(a.name)
    if not (P / "mix.wav").exists():
        extract_audio(P)
    device = "cuda" if __import__("torch").cuda.is_available() else "cpu"

    # 1) Demucs 分離鼓聲
    if not (P / "drums.wav").exists():
        run([sys.executable, "-m", "demucs", "--two-stems", "drums", "-n", "htdemucs_ft", "-d", device,
             "-o", P / "demucs", P / "mix.wav"])
        src = next((P / "demucs").glob("*/mix/drums.wav"))
        src.replace(P / "drums.wav")

    # 2) ADTOF 逐幀擊打機率（100fps，5 類 BD/SD/TT/HH/CY）。鼓聲音軌與完整混音各跑一次：
    #    ADTOF 是用完整混音訓練的，分離後的音軌會讓輕的 hi-hat 變弱，兩者互補。
    from adtof_pytorch import transcribe_to_midi
    for src in ("drums", "mix"):
        out = P / f"act_{src}.npy"
        if not out.exists():
            act = transcribe_to_midi(str(P / f"{src}.wav"), str(P / "tmp.mid"), device=device,
                                     return_activations=True)
            np.save(out, act[0])

    # 3) 拍點 / 小節線（用完整混音，節奏資訊最完整）
    if not (P / "beats.json").exists():
        from beat_this.inference import File2Beats
        beats, downbeats = File2Beats(checkpoint_path="final0", device=device, dbn=False)(str(P / "mix.wav"))
        (P / "beats.json").write_text(json.dumps({"beats": list(map(float, beats)),
                                                  "downbeats": list(map(float, downbeats))}))
    print("analyze done")


# ---------------------------------------------------------------- score
GM_TO_INST = {35: "BD", 36: "BD", 38: "SD", 40: "SD", 42: "HH", 44: "HH", 46: "HHO",
              47: "TM", 45: "TM", 48: "TH", 50: "TH", 41: "TF", 43: "TF",
              49: "CY", 57: "CY", 51: "RD", 59: "RD", 52: "CY", 55: "CY"}


ACT_CLASSES = ["BD", "SD", "TM", "HH", "CY"]   # ADTOF 輸出順序；TM 之後再由 split_toms 分高低
# 每類的判定門檻（套用在合併後的機率峰值上），以 KICK BACK 標準答案調校
THRESHOLDS = {"BD": 0.30, "SD": 0.25, "TM": 0.30, "HH": 0.25, "CY": 0.30}


# hybrid 模式下每類用哪個來源：完整混音的 hi-hat 較準（分離會把輕的 hi-hat 弄弱），其他用鼓聲音軌
HYBRID_SOURCE = {"BD": "drums", "SD": "drums", "TM": "drums", "HH": "mix", "CY": "drums"}


def load_activations(P, source):
    """source: drums / mix / max（兩者逐幀取大）/ hybrid（依 HYBRID_SOURCE 逐類挑）。"""
    acts = {s: np.load(P / f"act_{s}.npy") for s in ("drums", "mix")}
    n = min(len(a) for a in acts.values())
    acts = {k: v[:n] for k, v in acts.items()}
    if source == "max":
        return np.maximum(acts["drums"], acts["mix"])
    if source == "hybrid":
        return np.stack([acts[HYBRID_SOURCE[c]][:, i] for i, c in enumerate(ACT_CLASSES)], axis=1)
    return acts[source]


def load_onsets(P, source="hybrid", floor=0.05):
    """回傳 [(time, inst, height)]：每類機率曲線的所有局部峰值（門檻很低，之後依格點再篩）。"""
    act = load_activations(P, source)
    out = []
    for c, name in enumerate(ACT_CLASSES):
        a = act[:, c]
        pk = np.where((a[1:-1] >= floor) & (a[1:-1] >= a[:-2]) & (a[1:-1] > a[2:]))[0] + 1
        out += [(i / 100.0, name, float(a[i])) for i in pk]
    out.sort()
    return out


def grid_offset(onsets, flat_times):
    """擊打點相對格線的系統性偏移（秒）：只用明確的擊打估計。"""
    t = np.array([o[0] for o in onsets if o[2] > 0.5])
    if len(t) < 20:
        return 0.0
    idx = np.searchsorted(flat_times, t).clip(1, len(flat_times) - 1)
    near = np.where(np.abs(flat_times[idx] - t) < np.abs(flat_times[idx - 1] - t), flat_times[idx], flat_times[idx - 1])
    return float(np.median(t - near))


def repair_beats(beats):
    """修正 beat tracker 的倍速/半速錯誤，並平滑時間抖動。

    以全曲主要拍距 T0 為基準：拍距 ≈2T 的地方補插中間拍（半速段），
    拍距 <0.65T 的多餘拍丟掉（倍速段）。局部拍距會跟著演奏速度慢慢變，所以現場演出的速度漂移也能保留。
    """
    beats = np.asarray(beats, dtype=float)
    d = np.diff(beats)
    m = np.median(d)
    T0 = float(np.mean(d[(d > 0.75 * m) & (d < 1.33 * m)]))
    out = [beats[0]]
    for t in beats[1:]:
        recent = np.diff(out[-9:])
        Tl = float(np.clip(np.mean(recent), 0.85 * T0, 1.15 * T0)) if len(recent) >= 2 else T0
        k = int(np.floor((t - out[-1]) / Tl + 0.35))
        if k < 1:
            continue
        prev = out[-1]
        out += [prev + (t - prev) * j / k for j in range(1, k)]
        out.append(t)
    out = np.array(out)
    # 局部線性回歸平滑（beat_this 輸出以 20ms 為單位，會有抖動）
    sm = out.copy()
    n = np.arange(len(out))
    for i in range(len(out)):
        lo, hi = max(0, i - 4), min(len(out), i + 5)
        a, b = np.polyfit(n[lo:hi], out[lo:hi], 1)
        sm[i] = a * i + b
    return sm, T0


def downbeat_phase(beats, downbeats, meter):
    """每個 downbeat 的拍位相位（idx % meter），用滑動多數決去掉零星錯誤。回傳 [(beat_idx, phase)]。"""
    pairs = []
    for db in downbeats:
        i = int(np.argmin(np.abs(beats - db)))
        if abs(beats[i] - db) < 0.12:
            pairs.append(i)
    ph = [i % meter for i in pairs]
    smooth = []
    for j in range(len(ph)):
        win = ph[max(0, j - 4):j + 5]
        smooth.append(int(np.bincount(win, minlength=meter).argmax()))
    return list(zip(pairs, smooth))


def build_grid(beats, downbeats, duration):
    """回傳 bars: [{beats:[t...含結尾]}]；頭尾用平均拍長外插補滿。"""
    beats, ibi = repair_beats(beats)
    meter = 4
    db_ph = downbeat_phase(beats, downbeats, meter)
    # 依相位產生小節起點；相位改變時（例如中間插了一個 2/4 小節）從該 downbeat 起換新相位
    changes = [i for j, (i, p) in enumerate(db_ph) if j == 0 or p != db_ph[j - 1][1]]
    db_idx = []
    for k, s in enumerate(changes):
        end = changes[k + 1] if k + 1 < len(changes) else len(beats)
        db_idx += list(range(s, end, meter))
    # 往前外插到 0 秒之前，且第一個 downbeat 前的拍數補成整小節
    first = db_idx[0]
    pre = list(beats[:first])
    while not pre or pre[0] > 0 or len(pre) % meter:
        pre.insert(0, (pre[0] if pre else beats[first]) - ibi)
    all_beats = pre + list(beats[first:])
    db_idx = [i + len(pre) - first for i in db_idx]
    starts = list(range(0, db_idx[0], meter)) + db_idx
    # 往後外插
    while all_beats[-1] < duration:
        all_beats.append(all_beats[-1] + ibi)
    last = starts[-1]
    while last + meter < len(all_beats):
        last += meter
        starts.append(last)
    bars = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else min(s + meter, len(all_beats) - 1)
        if e <= s:
            continue
        bars.append({"beats": [float(t) for t in all_beats[s:e + 1]]})
    return bars, 60.0 / ibi, meter


def grid_points(bars, subdiv=4):
    flat = []   # (time, bar_i, slot)
    for bi, b in enumerate(bars):
        bt = b["beats"]
        for j in range(len(bt) - 1):
            for s in range(subdiv):
                flat.append((bt[j] + (bt[j + 1] - bt[j]) * s / subdiv, bi, j * subdiv + s))
    return flat


# 量化到反拍 16 分格（e / a）的額外代價（單位：16 分音符）。
# 人類演奏的 8 分反拍常常拖後 30~60ms，單純四捨五入會被誤判成「a」；扒譜者會優先記成 8 分音符。
OFFBEAT16_PENALTY = {"HH": 0.8, "default": 0.2}


TICKS = 12   # 每拍 tick 數：16 分音符 = 3、8 分三連音 = 4


def triplet_beats(onsets, bars):
    """找出用 8 分三連音演奏的拍：拍內非正拍的擊打點貼近 1/3、2/3 遠多於貼近 16 分格，
    且至少有一個非 hi-hat 的音明確落在三連音位置（hi-hat 的反拍常拖拍，單靠它會誤判）。"""
    starts = [(bi, j, b["beats"][j], b["beats"][j + 1]) for bi, b in enumerate(bars) for j in range(len(b["beats"]) - 1)]
    t0s = np.array([s[2] for s in starts])
    support = {}
    for t, name, h in onsets:
        k = int(np.searchsorted(t0s, t)) - 1
        if k < 0:
            continue
        bi, j, a, b = starts[k]
        f = (t - a) / (b - a)
        if not 0.12 < f < 0.88:
            continue
        e16 = min(abs(f - g) for g in (0.25, 0.5, 0.75))
        e3 = min(abs(f - g) for g in (1 / 3, 2 / 3))
        s = support.setdefault((bi, j), [0.0, False])
        s[0] += e16 - e3
        if name != "HH" and e3 < 0.05 and e16 > 0.05:
            s[1] = True
    return {k for k, (score, strong) in support.items() if score > 0.08 and strong}


def quantize(onsets, bars, subdiv=4, penalty=OFFBEAT16_PENALTY):
    """把 onset 對到格點。一般拍用 16 分格（反拍 16 分格加代價），三連音拍用三連音格。
    回傳每小節 {tick: set(inst)}，tick 以每拍 TICKS 為單位。"""
    flat = grid_points(bars, subdiv)
    times = np.array([f[0] for f in flat])
    tri = triplet_beats(onsets, bars)
    grid = [dict() for _ in bars]
    for t, name, vel in onsets:
        j = int(np.clip(np.searchsorted(times, t) - 1, 0, len(times) - 2))
        cands = [k for k in (j - 1, j, j + 1, j + 2) if 0 <= k < len(times)]
        spans = [(times[min(k + 1, len(times) - 1)] - times[max(k - 1, 0)]) / 2 for k in cands]
        pen = penalty.get(name, penalty["default"])
        dist = [abs(t - times[k]) / sp for k, sp in zip(cands, spans)]
        cost = [d + (pen if flat[k][2] % 2 else 0) for d, k in zip(dist, cands)]
        k = cands[int(np.argmin(cost))]
        # 吸附到 8 分格時若該格已有同一樂器（真的 16 分音符節奏），改放最近的格
        if name in grid[flat[k][1]].get(flat[k][2] * 3, ()):
            k = cands[int(np.argmin(dist))]
        _, bi, slot = flat[k]
        tick = slot * 3
        # 三連音拍：改用 1/3 拍格（落在拍尾的仍歸下一拍正拍，維持 16 分結果）
        beat = int(np.clip(np.searchsorted(times[::4], t) - 1, 0, len(times) // 4 - 1))
        bbi, bj = flat[beat * 4][1], flat[beat * 4][2] // 4
        if (bbi, bj) in tri:
            a = bars[bbi]["beats"][bj]
            f = (t - a) / (bars[bbi]["beats"][bj + 1] - a)
            r = int(round(f * 3))
            if 0 <= r < 3:
                bi, tick = bbi, bj * TICKS + r * 4
        grid[bi].setdefault(tick, set()).add(name)
    return grid, flat


CONTEXT_INSTS = {"HH": 0.08}   # 可用上下文放寬門檻的樂器 -> 放寬後的門檻


def fill_from_context(grid, all_onsets, bars, th):
    """節奏型的延續：hi-hat 被 crash 餘音或同時的大鼓蓋住時，模型只有微弱反應。
    若前後各兩小節中至少 3 小節在同一位置有這個樂器，就用較低門檻接受這裡的微弱峰值。"""
    for name, low in CONTEXT_INSTS.items():
        weak = [o for o in all_onsets if o[1] == name and low <= o[2] < th[name]]
        if not weak:
            continue
        cand = [dict() for _ in bars]
        quantized, _ = quantize(weak, bars)
        for bi, slots in enumerate(quantized):
            # 過門小節 / 段落結尾不套用：這小節本身要是 8 分音符律動，或缺口緊接在 crash 之後
            offbeats = sum(1 for tk, v in grid[bi].items() if name in v and tk % TICKS == TICKS // 2)
            crashes = [tk for tk, v in grid[bi].items() if "CY" in v]
            for tick in slots:
                if name in grid[bi].get(tick, ()):
                    continue
                votes = sum(1 for d in (-2, -1, 1, 2)
                            if 0 <= bi + d < len(grid) and name in grid[bi + d].get(tick, ()))
                after_crash = any(0 < tick - c <= 2 * TICKS for c in crashes)
                if votes >= 3 and (offbeats >= 2 or after_crash):
                    cand[bi][tick] = True
        for bi, ticks in enumerate(cand):
            for tick in ticks:
                grid[bi].setdefault(tick, set()).add(name)


def tick_time(bar, tick):
    j, sub = divmod(tick, TICKS)
    bt = bar["beats"]
    return bt[j] + (bt[j + 1] - bt[j]) * sub / TICKS


def tidy(grid):
    """規則式清理：Crash/Ride 判定、與 crash 同時的 hi-hat 去掉。"""
    for bar in grid:
        # 同一小節以 cross-stick 為主時，其餘「小鼓」多半也是 cross-stick（疊到其他聲音才被誤判）
        xs, sd = (sum(1 for v in bar.values() if k in v) for k in ("XS", "SD"))
        if xs >= 2 and xs >= sd:
            for v in bar.values():
                if "SD" in v:
                    v.discard("SD")
                    v.add("XS")
        cy_count = sum(1 for v in bar.values() if "CY" in v)
        for slot, v in bar.items():
            if "CY" in v:
                v.discard("CY")
                v.add("RD" if cy_count >= 4 else "CR")
            if "CR" in v:
                v.discard("HH")
                v.discard("HHO")
            if "RD" in v and "HH" in v:
                v.discard("HH")
    return grid


def merge_short_bars(bars, meter, duration):
    """相鄰的短小節（例如被切成兩半的 4/4）合併；去掉影片結束後才開始的小節。"""
    out = []
    for b in bars:
        n = len(b["beats"]) - 1
        if out and n < meter and len(out[-1]["beats"]) - 1 < meter \
                and (len(out[-1]["beats"]) - 1) + n <= meter:
            out[-1]["beats"] += b["beats"][1:]
        else:
            out.append({"beats": list(b["beats"])})
    return [b for b in out if b["beats"][0] < duration - 0.5]


def detect_cross_stick(onsets, P):
    """ADTOF 把 cross-stick（鼓棒橫敲框）當成小鼓。它的聲音清脆、幾乎沒有鼓身低頻，
    頻譜峰值在 600Hz 以上；一般小鼓則有明顯 100~300Hz 鼓身共鳴。"""
    import soundfile as sf
    y, sr = sf.read(str(P / "drums.wav"), always_2d=True)
    y = y.mean(axis=1)
    win = int(0.06 * sr)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    band = (freqs > 200) & (freqs < 10000)
    body = (freqs > 100) & (freqs < 300)
    out = []
    for t, name, h in onsets:
        if name == "SD":
            s = int((t + 0.005) * sr)
            seg = y[s:s + win]
            if len(seg) == win:
                sp = np.abs(np.fft.rfft(seg * np.hanning(win)))
                low = sp[body].sum() / (sp[band].sum() + 1e-9)
                peak = freqs[band][np.argmax(sp[band])]
                if low < 0.075 and peak > 600:
                    name = "XS"
        out.append((t, name, h))
    return out


def split_toms(onsets, P):
    """ADTOF 的 Tom 只有一類：用 drums.wav 在擊打瞬間的低頻主頻率，把 Tom 分成 TH / TM / TF。"""
    import soundfile as sf
    toms = [i for i, o in enumerate(onsets) if o[1] == "TM"]
    if len(toms) < 4:
        return onsets
    y, sr = sf.read(str(P / "drums.wav"), always_2d=True)
    y = y.mean(axis=1)
    win = int(0.09 * sr)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    band = (freqs >= 50) & (freqs <= 450)
    f0 = []
    for i in toms:
        s = int((onsets[i][0] + 0.01) * sr)
        seg = y[s:s + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        spec = np.abs(np.fft.rfft(seg * np.hanning(win)))
        f0.append(freqs[band][np.argmax(spec[band])])
    f0 = np.log2(np.array(f0))
    # 一維分群：音高差距不到半個八度就視為同一顆鼓
    lo, hi = np.percentile(f0, 10), np.percentile(f0, 90)
    if hi - lo < 0.5:
        return onsets
    cuts = [lo + (hi - lo) / 3, lo + 2 * (hi - lo) / 3]
    out = list(onsets)
    for i, f in zip(toms, f0):
        name = "TF" if f < cuts[0] else ("TM" if f < cuts[1] else "TH")
        out[i] = (onsets[i][0], name, onsets[i][2])
    return out


def cmd_score(a):
    P = proj(a.name)
    score = build_score(P, source=a.source)
    (P / "score.json").write_text(json.dumps(score, ensure_ascii=False, indent=1))
    n_ev = sum(len(b["events"]) for b in score["bars"])
    print(f"BPM≈{score['bpm']}  meter={score['meter']}  bars={len(score['bars'])}  events={n_ev}  "
          f"grid offset={score['offset_ms']}ms")
    preview(P, score)


def build_score(P, source="hybrid", thresholds=None):
    th = {**THRESHOLDS, **(thresholds or {})}
    bj = json.loads((P / "beats.json").read_text())
    import soundfile as sf
    duration = sf.info(str(P / "mix.wav")).duration
    bars, bpm, meter = build_grid(bj["beats"], bj["downbeats"], duration)
    bars = merge_short_bars(bars, meter, duration)
    all_onsets = load_onsets(P, source)
    times = np.array([f[0] for f in grid_points(bars)])
    offset = grid_offset(all_onsets, times)
    all_onsets = [(t - offset, n, h) for t, n, h in all_onsets]
    onsets = [o for o in all_onsets if o[2] >= th[o[1]]]
    onsets = detect_cross_stick(split_toms(onsets, P), P)
    grid, flat = quantize(onsets, bars)
    fill_from_context(grid, all_onsets, bars, th)
    grid = tidy(grid)

    out_bars, idx = [], 0
    for bi, b in enumerate(bars):
        events = []
        for tick in sorted(grid[bi]):
            notes = sorted(grid[bi][tick])
            if not notes:
                continue
            events.append({"tick": tick, "notes": notes, "t": tick_time(b, tick), "idx": idx})
            idx += 1
        out_bars.append({"t0": b["beats"][0], "t1": b["beats"][-1], "beats": b["beats"],
                         "ticks": (len(b["beats"]) - 1) * TICKS, "events": events})
    while out_bars and not out_bars[0]["events"]:   # 開頭外插出來、沒有任何音的小節
        out_bars.pop(0)
    return {"bpm": round(bpm, 1), "meter": meter, "duration": duration, "offset_ms": round(offset * 1000, 1),
            "bars": out_bars}


MULTIREST_MIN = 4   # 連續幾個空小節以上合併成多小節休止


def _pattern(bar):
    return [(e["tick"], tuple(e["notes"])) for e in bar["events"]]


def display_measures(score, simile=True):
    """把小節轉成顯示用的單位：一般小節、與前一小節相同（%）、多小節休止。"""
    bars = score["bars"]
    out, i = [], 0
    while i < len(bars):
        b = bars[i]
        j = i
        while j < len(bars) and not bars[j]["events"]:
            j += 1
        if j - i >= MULTIREST_MIN:
            out.append({"kind": "multirest", "no": i + 1, "count": j - i, "events": [],
                        "t0": b["t0"], "t1": bars[j - 1]["t1"]})
            i = j
            continue
        same = simile and i > 0 and b["events"] and _pattern(b) == _pattern(bars[i - 1])
        out.append({"kind": "repeat" if same else "bar", "no": i + 1, "ticks": b["ticks"],
                    "events": b["events"], "t0": b["t0"], "t1": b["t1"]})
        i += 1
    return out


def lines_of(score, per_line=4, simile=True):
    ms = display_measures(score, simile)
    return [ms[i:i + per_line] for i in range(0, len(ms), per_line)]


def render_lines(score, renderer, simile=True):
    """回傳 [(t_start, t_end, PIL image, [(t, x)])]。"""
    lines = lines_of(score, simile=simile)
    out = []
    for li, ms in enumerate(lines):
        img, xs = renderer.render_line(ms, show_header=li == 0, is_last_line=li == len(lines) - 1,
                                       tempo=int(round(score["bpm"])))
        evs = sorted((e["t"], xs[e["idx"]]) for m in ms for e in m["events"] if e["idx"] in xs)
        out.append((ms[0]["t0"], ms[-1]["t1"], img, evs))
    return out


def preview(P, score):
    """整份譜畫成一張長圖，方便檢查扒譜結果。"""
    from PIL import Image
    from notation import LineRenderer
    imgs = [img.crop((0, 0, img.width, img.height - 30)) for _, _, img, _ in render_lines(score, LineRenderer())]
    H = sum(i.height for i in imgs)
    sheet = Image.new("RGB", (imgs[0].width, H), (255, 255, 255))
    y = 0
    for i in imgs:
        sheet.paste(i, (0, y))
        y += i.height
    sheet.save(P / "score_preview.png")
    print("preview ->", P / "score_preview.png")


# ---------------------------------------------------------------- render
def video_fps(path):
    import imageio_ffmpeg
    gen = imageio_ffmpeg.read_frames(str(path))
    meta = next(gen)
    gen.close()
    return meta["fps"], meta["duration"], meta["size"]


def cmd_render(a):
    from notation import LineRenderer, Layout, render_cursor
    P = proj(a.name)
    score = json.loads((P / "score.json").read_text(encoding="utf-8"))
    W, H = 1920, 1080
    strip_h = a.strip_h
    top_h = H - strip_h
    L = Layout(width=W, height=strip_h)
    r = LineRenderer(L)

    fps, vdur, _ = video_fps(P / "video.mp4")
    rendered = [(t0, t1, np.array(img), evs) for t0, t1, img, evs in render_lines(score, r, simile=not a.no_simile)]

    start = a.start
    dur = a.dur if a.dur else vdur - start
    n_frames = int(math.floor(dur * fps))
    out = P / (a.out or ("out.mp4" if not a.dur else f"preview_{int(start)}s.mp4"))

    vf = (f"[0:v]scale={W}:-2,crop={W}:{top_h}:0:(ih-{top_h})*{a.crop_y}[top];"
          f"[top][1:v]vstack=inputs=2,format=yuv420p[v]")
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-stats",
           "-ss", f"{start}", "-t", f"{dur}", "-i", str(P / "video.mp4"),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{strip_h}", "-r", f"{fps}", "-i", "pipe:0",
           "-filter_complex", vf, "-map", "[v]", "-map", "0:a",
           "-r", f"{fps}",   # 固定輸出幀率：vstack 兩路時間戳不完全對齊時會輸出雙倍幀數
           "-c:v", a.codec, *(["-preset", "p5", "-cq", "23"] if "nvenc" in a.codec else ["-crf", "23"]),
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    print(">", " ".join(cmd[:6]), "...", flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    li = 0
    blank = np.full((strip_h, W, 3), 255, np.uint8)
    for f in range(n_frames):
        t = start + f / fps
        while li + 1 < len(rendered) and t >= rendered[li + 1][0]:
            li += 1
        t0, t1, img, evs = rendered[li]
        frame = img.copy() if t >= t0 - 2 else blank   # 開頭前兩秒先顯示第一行
        cur = None
        for et, ex in evs:
            if et <= t + a.lead:
                cur = ex
            else:
                break
        if cur is not None and t >= t0 - 0.01:
            render_cursor(frame, cur, layout=L)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print("render ->", out)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["download", "analyze", "score", "render", "all"])
    ap.add_argument("name")
    ap.add_argument("--url")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=0)
    ap.add_argument("--out")
    ap.add_argument("--strip-h", type=int, default=280)
    ap.add_argument("--crop-y", type=float, default=0.5, help="畫面上下裁切位置 0=保留頂部 1=保留底部")
    ap.add_argument("--lead", type=float, default=0.0, help="游標提早量（秒）")
    ap.add_argument("--codec", default="h264_nvenc")
    ap.add_argument("--no-simile", action="store_true", help="不使用 % 反覆記號，每小節都寫出來")
    ap.add_argument("--source", default="hybrid", choices=["drums", "mix", "max", "hybrid"], help="ADTOF 機率來源")
    a = ap.parse_args()
    if a.cmd in ("download", "all"):
        cmd_download(a)
    if a.cmd in ("analyze", "all"):
        cmd_analyze(a)
    if a.cmd in ("score", "all"):
        cmd_score(a)
    if a.cmd in ("render", "all"):
        cmd_render(a)


if __name__ == "__main__":
    main()
