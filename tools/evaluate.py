"""把鼓譜跟標準答案逐格比對。

用法：
  python tools/evaluate.py <name> [--detail]                     score.json 對 gt/gt.txt
  python tools/evaluate.py <name> --ref <鼓譜.json>              改拿一份鼓譜 JSON（例如編輯版本）當標準答案
  python tools/evaluate.py <name> --mode basic|enhanced          不讀 score.json，用分析檔在記憶體內重新扒譜來評分（不寫檔）
  python tools/evaluate.py --all                                 所有有標準答案的專案，basic 與 enhanced 對照
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
CATEGORIES = ["BD", "SD", "HH", "CY", "TOM", "XS"]
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
    return bars_of(json.loads(Path(path).read_text(encoding="utf-8")))


def bars_of(score):
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


def compare(gt, mine):
    """逐小節比對。回傳 (stats, 完全正確的小節數, 每小節差異說明)；stats[類別] = [tp, fp, fn]。"""
    stats = defaultdict(lambda: [0, 0, 0])
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
    return stats, exact, lines


def f1_of(stats):
    """各評分類別合計後的 (精確率, 召回率, F1)。"""
    tp, fp, fn = (sum(stats.get(c, [0, 0, 0])[i] for c in CATEGORIES) for i in range(3))
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return p, r, 2 * p * r / (p + r) if p + r else 0


def evaluate(gt, mine, detail=False):
    stats, exact, lines = compare(gt, mine)
    tot = [0, 0, 0]
    print(f"{'類別':<5}{'正確':>6}{'多抓':>6}{'漏抓':>6}{'精確率':>8}{'召回率':>8}{'F1':>7}")
    for c in CATEGORIES:
        tp, fp, fn = stats.get(c, [0, 0, 0])
        tot = [a + b for a, b in zip(tot, (tp, fp, fn))]
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        f = 2 * p * r / (p + r) if p + r else 0
        print(f"{c:<6}{tp:>6}{fp:>6}{fn:>6}{p:>9.1%}{r:>9.1%}{f:>8.1%}")
    tp, fp, fn = tot
    p, r, f = f1_of(stats)
    print(f"{'全部':<5}{tp:>6}{fp:>6}{fn:>6}{p:>9.1%}{r:>9.1%}{f:>8.1%}")
    print(f"完全正確的小節：{exact}/{len(gt)} ({exact / len(gt):.1%})")
    if detail:
        print("\n".join(lines))
    return stats


REQUIRED_ANALYSIS = ("beats.json", "act_drums.npy", "act_mix.npy", "drums.wav", "mix.wav")
EPS = 1e-9


def missing_analysis(P):
    return [f for f in REQUIRED_ANALYSIS if not (P / f).exists()]


def rescore(P, mode):
    """用專案現有分析檔在記憶體內扒譜（不寫 score.json）。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import drumcover
    return drumcover.build_score(P, mode=mode)


def alignment_warnings(ref, mine, tol=0.25):
    """標準答案鼓譜與被評分的鼓譜是否來自同一次分析：小節數與各小節起點時間要對得上。"""
    out = []
    rb, mb = ref["bars"], mine["bars"]
    if len(rb) != len(mb):
        out.append(f"小節數不符：標準答案 {len(rb)} 小節，被評分的 {len(mb)} 小節（逐小節比對的分數不可信）")
    else:
        late = [i for i, (a, b) in enumerate(zip(rb, mb), 1)
                if "t0" in a and "t0" in b and abs(a["t0"] - b["t0"]) > tol]
        if late:
            out.append(f"{len(late)} 個小節的起點時間差超過 {tol}s（第 {late[0]} 小節起），可能不是同一次分析")
    return out


def pick_reference(P):
    """標準答案：有 gt/gt.txt 就用它；否則用最新修改的 versions/*.json。
    回傳 (說明, 小節 dict, 鼓譜 dict 或 None)；都沒有回傳 None。"""
    gt = P / "gt" / "gt.txt"
    if gt.exists():
        return "gt/gt.txt", load_gt(gt), None
    vdir = P / "versions"
    vs = sorted(vdir.glob("*.json"), key=lambda f: f.stat().st_mtime) if vdir.is_dir() else []
    if vs:
        score = json.loads(vs[-1].read_text(encoding="utf-8"))
        return f"versions/{vs[-1].name}", bars_of(score), score
    return None


def metrics(gt, mine):
    stats, exact, _ = compare(gt, mine)
    return {"f1": f1_of(stats)[2], "exact": exact, "total": len(gt)}


def regressions(rows):
    """enhanced 比 basic 退步的列：F1 較低或完全正確小節較少。"""
    return [r for r in rows if r["enhanced"]["f1"] < r["basic"]["f1"] - EPS
            or r["enhanced"]["exact"] < r["basic"]["exact"]]


def format_table(rows):
    lines = [f"{'專案':<14}{'標準答案':<22}{'basic F1':>9}{'正確小節':>10}{'enhanced F1':>13}{'正確小節':>10}{'差異(F1 / 小節)':>20}"]
    for r in rows:
        b, e = r["basic"], r["enhanced"]
        bx, ex = f"{b['exact']}/{b['total']}", f"{e['exact']}/{e['total']}"
        diff = f"{(e['f1'] - b['f1']) * 100:+.1f}pt / {e['exact'] - b['exact']:+d}"
        lines.append(f"{r['name']:<14}{r['ref']:<22}{b['f1']:>9.1%}{bx:>10}{e['f1']:>13.1%}{ex:>10}{diff:>20}")
    return "\n".join(lines)


def run_all(projects_root):
    rows = []
    for P in sorted(d for d in projects_root.iterdir() if d.is_dir()):
        ref = pick_reference(P)
        if not ref:
            continue
        label, gt, ref_score = ref
        miss = missing_analysis(P)
        if miss:
            print(f"略過 {P.name}：缺分析檔 {', '.join(miss)}")
            continue
        print(f"{P.name}：標準答案用 {label}", flush=True)
        row = {"name": P.name, "ref": label}
        for mode in ("basic", "enhanced"):
            score = rescore(P, mode)
            for w in (alignment_warnings(ref_score, score) if ref_score else []):
                print(f"  警告（{mode}）：{w}")
            row[mode] = metrics(gt, bars_of(score))
        rows.append(row)
    print()
    if not rows:
        print("沒有可評分的專案")
        return rows
    print(format_table(rows))
    bad = regressions(rows)
    print()
    if bad:
        print("enhanced 比 basic 退步的歌：" + "、".join(r["name"] for r in bad))
    else:
        print("沒有任何一首歌 enhanced 比 basic 退步")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--ref", type=Path, help="拿這份鼓譜 JSON（例如 versions/<id>.json）當標準答案，取代 gt.txt")
    ap.add_argument("--mode", choices=["basic", "enhanced"], help="不讀 score.json，改用分析檔在記憶體內以此模式扒譜後評分")
    ap.add_argument("--all", action="store_true", help="所有有標準答案的專案，basic 與 enhanced 各跑一次並對照")
    ap.add_argument("--projects-root", type=Path, default=ROOT / "projects")
    a = ap.parse_args()
    if a.all:
        if a.name or a.ref or a.mode:
            ap.error("--all 不能搭配專案名稱、--ref、--mode")
        run_all(a.projects_root)
        return
    if not a.name:
        ap.error("需要專案名稱（或用 --all）")
    P = a.projects_root / a.name
    if a.mode:
        miss = missing_analysis(P)
        if miss:
            ap.error(f"缺分析檔：{', '.join(miss)}")
        mine_score = rescore(P, a.mode)
        print(f"以 {a.mode} 模式重新扒譜（不寫入 score.json）")
    else:
        mine_score = json.loads((P / "score.json").read_text(encoding="utf-8"))
    if a.ref:
        ref_score = json.loads(a.ref.read_text(encoding="utf-8"))
        gt = bars_of(ref_score)
        for w in alignment_warnings(ref_score, mine_score):
            print(f"警告：{w}")
    else:
        gt = load_gt(P / "gt" / "gt.txt")
    evaluate(gt, bars_of(mine_score), a.detail)


if __name__ == "__main__":
    main()
