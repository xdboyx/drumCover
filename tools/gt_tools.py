"""驗證用工具：從「附鼓譜的影片」擷取譜行、產生抄譜用放大圖、以及「影片譜 vs 自動扒譜」逐行對照圖。

用法：
    python tools/gt_tools.py extract <name> [--y0 860 --y1 1080]   # 擷取影片底部譜條每一次換行
    python tools/gt_tools.py compare <name>                         # 產生 gt/cmp_XX.png 對照圖
輸出都在 projects/<name>/gt/。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")


def cmd_extract(a):
    import imageio_ffmpeg
    P = ROOT / "projects" / a.name
    out = P / "gt"
    out.mkdir(exist_ok=True)
    H, W = a.y1 - a.y0, 1920
    gen = imageio_ffmpeg.read_frames(str(P / "video.mp4"),
                                     output_params=["-vf", f"fps={a.fps},scale=1920:-2,crop={W}:{H}:0:{a.y0}"])
    next(gen)
    prev, lines = None, []
    for i, fr in enumerate(gen):
        g = np.frombuffer(fr, np.uint8).reshape(H, W, 3).mean(axis=2).astype(np.uint8)
        ink = g < 128
        if prev is None or (ink ^ prev).mean() > 0.01:     # 譜條內容明顯改變 = 換行
            if ink.mean() > 0.005:                           # 排除全白/全黑（轉場）
                k = len(lines)
                Image.fromarray(g).save(out / f"line_{k:03d}.png")
                # 抄譜用：左右兩半放大上下排
                im = Image.fromarray(g)
                s = Image.new("L", (940, 450), 180)
                s.paste(im.crop((60, 0, 1000, H)).resize((940, 220)), (0, 0))
                s.paste(im.crop((960, 0, 1900, H)).resize((940, 220)), (0, 230))
                s.resize((1410, 675)).save(out / f"half_{k:03d}.png")
                lines.append({"k": k, "t": i / a.fps})
            prev = ink
    (out / "lines.json").write_text(json.dumps(lines, indent=1))
    print(f"{len(lines)} 行：", [round(l["t"], 1) for l in lines])


def cmd_compare(a):
    import drumcover as dc
    from notation import LineRenderer
    P = ROOT / "projects" / a.name
    glines = json.loads((P / "gt" / "lines.json").read_text())
    score = json.loads((P / "score.json").read_text(encoding="utf-8"))
    mine = dc.render_lines(score, LineRenderer())
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 26)
    pairs = []
    for L in glines:
        li = min(range(len(mine)), key=lambda i: abs(mine[i][0] - L["t"]))
        gt = Image.open(P / "gt" / f"line_{L['k']:03d}.png").convert("RGB").resize((1920, 220))
        m = mine[li][2].crop((0, 0, 1920, 250))
        im = Image.new("RGB", (1920, 476), "white")
        im.paste(gt, (0, 0))
        im.paste(m, (0, 226))
        d = ImageDraw.Draw(im)
        d.text((1700, 2), f"video #{L['k']}", font=font, fill=(200, 0, 0))
        d.text((1700, 228), "auto", font=font, fill=(0, 0, 200))
        d.line([(0, 222), (1920, 222)], fill=(200, 0, 0), width=3)
        pairs.append(im)
    for g in range(0, len(pairs), 2):
        grp = pairs[g:g + 2]
        sheet = Image.new("RGB", (1920, sum(p.height for p in grp) + 16), (200, 200, 200))
        y = 0
        for p in grp:
            sheet.paste(p, (0, y))
            y += p.height + 16
        sheet.save(P / "gt" / f"cmp_{g // 2:02d}.png")
    print(f"{len(pairs)} 組對照 -> {P / 'gt'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["extract", "compare"])
    ap.add_argument("name")
    ap.add_argument("--y0", type=int, default=860, help="譜條在 1080p 畫面中的上緣")
    ap.add_argument("--y1", type=int, default=1080, help="譜條下緣")
    ap.add_argument("--fps", type=float, default=4)
    a = ap.parse_args()
    {"extract": cmd_extract, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    main()
