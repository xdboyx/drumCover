"""tools/evaluate.py 的評分邏輯（純邏輯，小型假資料）。"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import evaluate as ev  # noqa: E402


def bar(t0, events):
    return {"t0": t0, "t1": t0 + 2, "ticks": 48,
            "events": [{"tick": t, "notes": n, "t": t0, "idx": i} for i, (t, n) in enumerate(events)]}


def score(*bars):
    return {"bpm": 120, "meter": 4, "duration": 10, "offset_ms": 0, "bars": list(bars)}


A = score(bar(0, [(0, ["BD", "HH"]), (12, ["SD"])]), bar(2, [(0, ["BD"])]))


def test_bars_of_merges_categories_and_f1_perfect():
    m = ev.bars_of(A)
    r = ev.metrics(m, m)
    assert r == {"f1": 1.0, "exact": 2, "total": 2}


def test_metrics_counts_missing_and_extra():
    mine = score(bar(0, [(0, ["BD", "HH"])]), bar(2, [(0, ["BD"]), (12, ["SD"])]))
    r = ev.metrics(ev.bars_of(A), ev.bars_of(mine))
    # tp=BD,HH,BD=3  fp=SD(bar2)=1  fn=SD(bar1)=1
    assert r["exact"] == 0
    assert abs(r["f1"] - 0.75) < 1e-9


def test_ho_and_hh_are_same_category():
    ref = score(bar(0, [(0, ["HO"])]))
    mine = score(bar(0, [(0, ["HH"])]))
    assert ev.metrics(ev.bars_of(ref), ev.bars_of(mine))["f1"] == 1.0


def test_alignment_warns_on_bar_count_mismatch():
    assert ev.alignment_warnings(A, A) == []
    short = score(bar(0, []))
    assert "小節數不符" in ev.alignment_warnings(A, short)[0]


def test_alignment_warns_on_shifted_bars():
    shifted = score(bar(1.0, []), bar(3.0, []))
    assert "起點時間" in ev.alignment_warnings(A, shifted)[0]


def test_regressions_flags_lower_f1_or_fewer_exact_bars():
    def row(name, bf, be, ef, ee):
        return {"name": name, "basic": {"f1": bf, "exact": be}, "enhanced": {"f1": ef, "exact": ee}}
    rows = [row("same", 0.9, 5, 0.9, 5), row("better", 0.9, 5, 0.95, 6),
            row("worse_f1", 0.9, 5, 0.88, 5), row("worse_exact", 0.9, 5, 0.92, 4)]
    assert [r["name"] for r in ev.regressions(rows)] == ["worse_f1", "worse_exact"]


def test_pick_reference_prefers_gt_then_newest_version(tmp_path):
    P = tmp_path / "歌"
    assert ev.pick_reference(P) is None
    (P / "versions").mkdir(parents=True)
    old, new = P / "versions" / "old.json", P / "versions" / "new.json"
    old.write_text(json.dumps(A))
    new.write_text(json.dumps(A))
    import os
    os.utime(old, (1, 1))
    assert ev.pick_reference(P)[0] == "versions/new.json"
    (P / "gt").mkdir()
    (P / "gt" / "gt.txt").write_text("1: BD 1\n", encoding="utf-8")
    label, gt, ref_score = ev.pick_reference(P)
    assert label == "gt/gt.txt" and ref_score is None and gt[1]["BD"] == {0}


def test_missing_analysis_lists_absent_files(tmp_path):
    (tmp_path / "beats.json").write_text("{}")
    assert "beats.json" not in ev.missing_analysis(tmp_path)
    assert "drums.wav" in ev.missing_analysis(tmp_path)


def test_format_table_shape():
    rows = [{"name": "x", "ref": "gt/gt.txt", "basic": {"f1": 0.9, "exact": 5, "total": 10},
             "enhanced": {"f1": 0.92, "exact": 6, "total": 10}}]
    out = ev.format_table(rows)
    assert "90.0%" in out and "+2.0pt / +1" in out
