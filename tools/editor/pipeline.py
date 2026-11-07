"""扒譜流程介面：新增專案時伺服器透過這個模組呼叫 download → separate → transcribe → score。

介面（模組層級的函式，測試可以用環境變數 DRUMCOVER_PIPELINE 換成另一個 .py 檔）：
    title(source) -> str
    download(P, source, opts, report)     # 取得 video.mp4 與 mix.wav（opts: start / dur）
    separate(P, opts, report)             # Demucs 分離鼓聲 -> drums.wav
    transcribe(P, opts, report)           # ADTOF 機率 + 拍點 -> act_*.npy、beats.json
    score(P, opts, report)                # 量化成 score.json（opts: audio 扒譜音源）
P 是專案資料夾；report(0~1) 回報目前步驟進度；失敗就丟例外。
這裡的正式實作都是呼叫 drumcover.py 的子行程，已存在的中間檔該步會自己跳過。
"""
import subprocess
import sys
from pathlib import Path

from render_job import run_logged, TOOLS, ROOT

STEPS = [("下載", "download"), ("分離鼓聲", "separate"), ("扒譜", "transcribe"), ("排版", "score")]


def _drumcover(P, cmd, report, *extra):
    run_logged([sys.executable, str(TOOLS / "drumcover.py"), cmd, P.name, "--projects-root", str(P.parent),
                *extra], report, cwd=str(ROOT))


def title(source):
    if Path(source).is_file():
        return Path(source).stem
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--skip-download", "--print", "title",
                        source], capture_output=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise RuntimeError("取得影片標題失敗：" + r.stderr.decode("utf-8", "replace").strip()[-300:])
    return r.stdout.decode("utf-8", "replace").strip().splitlines()[0]


def download(P, source, opts, report):
    extra = ["--url", source]
    if opts.get("start"):
        extra += ["--start", str(opts["start"])]
    if opts.get("dur"):
        extra += ["--dur", str(opts["dur"])]
    _drumcover(P, "download", report, *extra)


def separate(P, opts, report):
    _drumcover(P, "separate", report)


def transcribe(P, opts, report):
    _drumcover(P, "transcribe", report)


def score(P, opts, report):
    _drumcover(P, "score", report, "--source", opts.get("audio") or "hybrid")
