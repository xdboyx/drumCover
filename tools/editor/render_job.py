"""輸出練習影片的工作：先快照鼓譜，再呼叫 drumcover render 子行程。"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
ROOT = TOOLS.parent
PROGRESS = re.compile(r"PROGRESS (\d+)/(\d+)")


ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')   # Windows 檔名不允許的字元（專案名稱檢查與檔名清理共用）


def safe_filename(name):
    """Windows 檔名不允許的字元換成底線。"""
    s = ILLEGAL_CHARS.sub("_", name).strip().rstrip(".")
    return s or "_"


def run_logged(cmd, report, cwd=None):
    """跑子行程，解析 'PROGRESS n/m' 回報進度；失敗時丟出含輸出尾段的例外。"""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    tail = b""
    for chunk in iter(lambda: proc.stdout.read1(256), b""):
        tail = (tail + chunk)[-2000:]
        m = PROGRESS.findall(tail.decode("utf-8", "replace"))
        if m and int(m[-1][1]):
            report(int(m[-1][0]) / int(m[-1][1]))
    if proc.wait() != 0:
        log = tail.decode("utf-8", "replace").replace("\r", "\n").strip()
        raise RuntimeError(f"輸出失敗（結束碼 {proc.returncode}）\n{log[-400:]}")


def render_steps(projects_root, project_dir, version_name, score, crop_y, simile):
    """回傳 (steps, output_path, discard)；工作被拒絕時要呼叫 discard() 清掉快照。score 是送出當下的鼓譜內容，這裡立刻寫成快照檔。"""
    exports = project_dir / "exports"
    final = exports / f"{safe_filename(version_name)}.mp4"
    snap_dir = project_dir / "_tmp"
    snap_dir.mkdir(exist_ok=True)
    fd, snap_name = tempfile.mkstemp(suffix=".json", prefix="render-", dir=snap_dir)
    snap = Path(snap_name)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(score, f, ensure_ascii=False)
    part = exports / (final.stem + ".part.mp4")
    script = os.environ.get("DRUMCOVER_RENDER_SCRIPT") or str(TOOLS / "drumcover.py")   # 測試可替換

    def step(report):
        exports.mkdir(exist_ok=True)
        cmd = [sys.executable, script, "render", project_dir.name, "--projects-root", str(projects_root),
               "--score", str(snap), "--out", str(part), "--crop-y", str(crop_y)]
        if not simile:
            cmd.append("--no-simile")
        try:
            run_logged(cmd, report, cwd=str(ROOT))
            os.replace(part, final)   # 成功才覆蓋舊檔
        finally:
            snap.unlink(missing_ok=True)
            part.unlink(missing_ok=True)

    return [("輸出練習影片", step)], final, lambda: snap.unlink(missing_ok=True)
