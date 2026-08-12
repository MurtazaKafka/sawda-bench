"""Merge Fable batch outputs and compare both judge arms to human labels.

Fable agents wrote results/fable_batches/out_*.jsonl keyed by pair_id
(position in judging_plan order). This maps them back to (item_id, system),
writes results/fable_judgments.jsonl, and prints agreement for both the
DeepSeek arm and the Fable arm against the 180 human labels.

Usage: python src/judge_compare.py
"""
import json
from pathlib import Path

from config import RESULTS_DIR

PLAN = RESULTS_DIR / "judging_plan.json"


def load_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def agreement(human, other, name):
    overlap = [k for k in human if k in other]
    n = len(overlap)
    if not n:
        print(f"{name}: no overlap yet")
        return None
    exact = sum(human[k]["intent"] == other[k]["intent"] for k in overlap)
    off1 = sum(abs(human[k]["intent"] - other[k]["intent"]) <= 1
               for k in overlap)
    h = [human[k]["appropriateness"] for k in overlap]
    l = [other[k]["appropriateness"] for k in overlap]
    mh, ml = sum(h) / n, sum(l) / n
    cov = sum((a - mh) * (b - ml) for a, b in zip(h, l))
    sh = sum((a - mh) ** 2 for a in h) ** 0.5
    sl = sum((b - ml) ** 2 for b in l) ** 0.5
    r = cov / (sh * sl) if sh and sl else float("nan")
    print(f"{name} (n={n}): intent exact {exact/n:.1%}, "
          f"off-by-one {off1/n:.1%}, appropriateness r {r:.3f}")
    return exact / n


def main():
    order = [tuple(p) for p in json.loads(PLAN.read_text())["order"]]
    human = {(r["item_id"], r["system"]): r
             for r in load_jsonl(RESULTS_DIR / "human_judgments.jsonl")}

    # merge fable batches
    fable = {}
    for f in sorted((RESULTS_DIR / "fable_batches").glob("out_*.jsonl")):
        for r in load_jsonl(f):
            iid, system = order[r["pair_id"]]
            fable[(iid, system)] = {
                "item_id": iid, "system": system,
                "intent": int(r["intent"]),
                "appropriateness": int(r["appropriateness"]),
                "judge": "fable-agent", "judge_model": "claude-fable-5",
                "machine_generated": True}
    with (RESULTS_DIR / "fable_judgments.jsonl").open("w") as f:
        for rec in fable.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"merged {len(fable)} fable judgments")

    deepseek = {(r["item_id"], r["system"]): r
                for r in load_jsonl(RESULTS_DIR / "llm_judgments.jsonl")}
    a_ds = agreement(human, deepseek, "DeepSeek v4-pro (rubric v2)")
    a_fb = agreement(human, fable, "Fable agents   (rubric v2)")
    print("\nthreshold for extending machine labels to the full set: >= 80%")
    return a_ds, a_fb


if __name__ == "__main__":
    main()
