#!/usr/bin/env python
"""Data for the two figures in the Sawda paper, recomputed from repo files.

Run from repo root:  ./venv/bin/python paper/stats/figure_data.py

Fig 1 (pipeline): tranche counts, validation counts, held-out/evaluated split,
translation count, judged subset, judgment count.
Fig 2 (stacked bars): per system x direction intent-outcome shares from
results/human_judgments.jsonl, asserted against the audited per-direction
table values in results/results.md.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

items = [json.loads(l) for l in (ROOT / "items" / "items.jsonl").read_text().splitlines() if l.strip()]
judg = [json.loads(l) for l in (ROOT / "results" / "human_judgments.jsonl").read_text().splitlines() if l.strip()]
trans = [json.loads(l) for l in (ROOT / "results" / "translations.jsonl").read_text().splitlines() if l.strip()]
heldout = json.loads((ROOT / "results" / "heldout_ids.json").read_text())
if isinstance(heldout, dict):
    heldout = heldout.get("heldout_ids") or heldout.get("ids") or list(heldout.values())[0]

by_id = {d["id"]: d for d in items}

print("== Pipeline figure numbers ==")
print(f"  items total: {len(items)}")
print(f"  validated: {sum(1 for d in items if d.get('validated'))}")
print(f"  tranches: {Counter(d['tranche'] for d in items)}")
print(f"  directions: {Counter(d['direction'] for d in items)}")
print(f"  held out: {len(heldout)} -> evaluated: {len(items) - len(heldout)}")
print(f"  translations: {len(trans)} rows "
      f"({len({t['item_id'] for t in trans})} items x {len({t['system'] for t in trans})} systems)")
judged_items = {j["item_id"] for j in judg}
jdir = Counter(by_id[i]["direction"] for i in judged_items)
print(f"  judged subset: {len(judged_items)} items ({dict(jdir)}), {len(judg)} judgments")
print(f"  judged systems: {len({j['system'] for j in judg})}")

print("\n== Stacked-bar figure data (per system x direction) ==")
SYS_ORDER = ["nllb", "frontier_naive", "frontier_audience", "frontier_instructional",
             "small_naive", "small_audience"]
LABEL = {"nllb": "A", "frontier_naive": "B", "frontier_audience": "C",
         "frontier_instructional": "D", "small_naive": "E", "small_audience": "F"}

# audited values from results/results.md "By direction" table (preserved, degraded, inverted)
AUDIT = {
    ("frontier_audience", "en2fa"): (0.267, 0.600, 0.133),
    ("frontier_audience", "fa2en"): (0.067, 0.933, 0.000),
    ("frontier_instructional", "en2fa"): (0.200, 0.467, 0.333),
    ("frontier_instructional", "fa2en"): (0.400, 0.600, 0.000),
    ("frontier_naive", "en2fa"): (0.067, 0.733, 0.200),
    ("frontier_naive", "fa2en"): (0.333, 0.600, 0.067),
    ("nllb", "en2fa"): (0.133, 0.800, 0.067),
    ("nllb", "fa2en"): (0.133, 0.733, 0.133),
    ("small_audience", "en2fa"): (0.267, 0.667, 0.067),
    ("small_audience", "fa2en"): (0.200, 0.733, 0.067),
    ("small_naive", "en2fa"): (0.200, 0.600, 0.200),
    ("small_naive", "fa2en"): (0.200, 0.733, 0.067),
}

cells = defaultdict(list)
for j in judg:
    cells[(j["system"], by_id[j["item_id"]]["direction"])].append(j["intent"])

for direction in ["fa2en", "en2fa"]:
    print(f"  -- {direction} --")
    for s in SYS_ORDER:
        v = cells[(s, direction)]
        n = len(v)
        p, dg, iv = (sum(1 for x in v if x == 3) / n,
                     sum(1 for x in v if x == 2) / n,
                     sum(1 for x in v if x == 1) / n)
        ap, adg, aiv = AUDIT[(s, direction)]
        assert abs(p - ap) < 5e-4 and abs(dg - adg) < 5e-4 and abs(iv - aiv) < 5e-4, \
            (s, direction, p, dg, iv)
        # percentages for pgfplots
        print(f"    {LABEL[s]} n={n}  preserved {p*100:.1f}  degraded {dg*100:.1f}  inverted {iv*100:.1f}")
print("  all cells match the audited per-direction table.")
