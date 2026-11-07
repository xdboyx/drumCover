"""把 score.json 跟手抄的標準答案 gt.txt 逐格比對。

用法：python tools/evaluate.py <name> [--detail]
gt.txt 格式見 projects/kickback/gt/gt.txt 開頭註解。
時間位置以「每拍 12 tick」表示，16 分音符 = 3 tick、8 分三連音 = 4 tick。
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

# 評分用的類別（ADTOF 本身分不出的細項先合併）
CATEGORY = {"HH": "HH", "HO": "HH", "RD": "CY", "CR": "CY", "XS": "XS",
            "SD": "SD", "BD": "BD", "TH": "TOM", "TM": "TOM", "TF": "TOM", "HF": None}
SUB = {"": 0, "e": 3, "&": 6, "a": 9, "T2": 4, "T3": 8}
HH8 = "1 1& 2 2& 3 3& 4 4&"


def tick(tok):
    m = re.fullmatch(r"([1-9])(e|&|a|T2|T3)?", tok)
    if not m:
        raise ValueError(tok)
    return (int(m.group(1)) - 1) * 12 + SUB[m.group(2) or ""]


def load_gt(path):
    bars = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        n, body = line.split(":", 1)
        n, body = int(n), body.strip()
        if body.startswith("="):
            bars[n] = {k: set(v) for k, v in bars[int(body[1:])].items()}
            continue
        notes = defaultdict(set)
        if body != "rest":
            for part in body.split(";"):
                part = part.strip()
                if part == "HH8":
                    part = "HH " + HH8
                inst, *toks = part.split()
                notes[inst] |= {tick(t) for t in toks}
        bars[n] = dict(notes)
    return bars


def load_mine(path):
    score = json.loads(Path(path).read_text(encoding="utf-8"))
    bars = {}
    for i, b in enumerate(score["bars"], 1):
        notes = defaultdict(set)
        for e in b["events"]:
            for n in e["notes"]:
                notes[n].add(e["tick"] if "tick" in e else e["slot"] * 3)
        bars[i] = dict(notes)
    return bars


def by_category(bar):
    out = defaultdict(set)
    for inst, ticks in bar.items():
        c = CATEGORY.get(inst, inst)
        if c:
            out[c] |= ticks
    return out


def tick_name(t):
    beat, sub = divmod(t, 12)
    name = {v: k for k, v in SUB.items()}.get(sub, f"+{sub}")
    return f"{beat + 1}{name}"


def evaluate(gt, mine, detail=False):
    stats = defaultdict(lambda: [0, 0, 0])   # tp, fp, fn
    exact = 0
    lines = []
    for n in sorted(gt):
        g = by_category(gt[n])
        m = by_category(mine.get(n, {}))
        bar_ok = True
        diffs = []
        for c in sorted(set(g) | set(m)):
            tp = len(g.get(c, set()) & m.get(c, set()))
            fp = m.get(c, set()) - g.get(c, set())
            fn = g.get(c, set()) - m.get(c, set())
            stats[c][0] += tp
            stats[c][1] += len(fp)
            stats[c][2] += len(fn)
            if fp or fn:
                bar_ok = False
                diffs.append(f"{c}: " + " ".join([f"+{tick_name(t)}" for t in sorted(fp)] +
                                                  [f"-{tick_name(t)}" for t in sorted(fn)]))
        exact += bar_ok
        if diffs:
            lines.append(f"bar {n:3d}: " + " | ".join(diffs))
    tot = [0, 0, 0]
    print(f"{'類別':<5}{'正確':>6}{'多抓':>6}{'漏抓':>6}{'精確率':>8}{'召回率':>8}{'F1':>7}")
    for c in ["BD", "SD", "HH", "CY", "TOM", "XS"]:
        tp, fp, fn = stats.get(c, [0, 0, 0])
        tot = [a + b for a, b in zip(tot, (tp, fp, fn))]
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        f = 2 * p * r / (p + r) if p + r else 0
        print(f"{c:<6}{tp:>6}{fp:>6}{fn:>6}{p:>9.1%}{r:>9.1%}{f:>8.1%}")
    tp, fp, fn = tot
    p, r = tp / (tp + fp), tp / (tp + fn)
    print(f"{'全部':<5}{tp:>6}{fp:>6}{fn:>6}{p:>9.1%}{r:>9.1%}{2 * p * r / (p + r):>8.1%}")
    print(f"完全正確的小節：{exact}/{len(gt)} ({exact / len(gt):.1%})")
    if detail:
        print("\n".join(lines))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    P = ROOT / "projects" / a.name
    evaluate(load_gt(P / "gt" / "gt.txt"), load_mine(P / "score.json"), a.detail)


if __name__ == "__main__":
    main()
