"""Phase 5: LLM judge (DeepSeek family — disjoint from Kimi B-D and gpt-oss E-F).

Judges the SAME (item, system) pairs the human labeled, blind to system
identity, with a rubric mirroring the human labeling instructions. Reports
agreement (exact + off-by-one for intent; Pearson r for appropriateness).
With --full it judges the remaining pairs; those labels are written with
judge="llm" and machine_generated=true.

Usage: python src/llm_judge.py           # calibration vs human labels
       python src/llm_judge.py --full    # extend to remaining pairs
"""
import json
import re
import sys

import fw
from config import ITEMS, MODELS, RESULTS_DIR

TRANSLATIONS = RESULTS_DIR / "translations.jsonl"
HUMAN = RESULTS_DIR / "human_judgments.jsonl"
OUT = RESULTS_DIR / "llm_judgments.jsonl"

RUBRIC = """You are evaluating one candidate translation of a culturally \
loaded message (Dari/Farsi <-> English trade and family-business \
communication). Judge whether the SPEAKER'S INTENDED MEANING survives, not \
surface fidelity. Persian norms that matter: taarof (ritual refusal/offer \
that is not literal), indirect refusal, face-preserving obligation formulas, \
deferential register.

Rate two things:
1. intent — 3: the intended meaning and force are preserved for the target \
reader; 2: degraded (weakened, ambiguous, or partly lost); 1: inverted or \
deleted (the reader would understand the opposite, or a ritual/indirect \
meaning is rendered literally so the real message is gone).
2. appropriateness — 1-7: how socially appropriate the wording is for this \
speaker, listener, and situation (7 = exactly right register and tone).

Answer with only JSON: {"intent": <1|2|3>, "appropriateness": <1-7>}"""


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def judge_pair(item, translation):
    user = (f"SOURCE MESSAGE ({item['direction']}):\n{item['utterance_src']}\n\n"
            f"CONTEXT:\n{item['context']}\n\n"
            f"CANDIDATE TRANSLATION:\n{translation}")
    r = fw.call(MODELS["judge"],
                [{"role": "system", "content": RUBRIC},
                 {"role": "user", "content": user}], max_tokens=2048)
    m = re.search(r'\{[^{}]*"intent"[^{}]*\}', r["text"])
    if not m:
        return None, r["text"]
    d = json.loads(m.group(0))
    return d, r["text"]


def main():
    full = "--full" in sys.argv
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    trans = {(r["item_id"], r["system"]): r for r in load_jsonl(TRANSLATIONS)}
    human = {(r["item_id"], r["system"]): r for r in load_jsonl(HUMAN)}
    already = {(r["item_id"], r["system"]) for r in load_jsonl(OUT)}

    targets = set(human) if not full else set(trans)
    targets -= already
    print(f"Judging {len(targets)} pairs with {MODELS['judge']} "
          f"({'full' if full else 'calibration'})")
    with OUT.open("a") as out:
        for iid, system in sorted(targets):
            d, raw = judge_pair(items[iid], trans[(iid, system)]["output"])
            if d is None:
                print(f"  UNPARSEABLE {iid}/{system}: {raw[:80]}")
                continue
            rec = {"item_id": iid, "system": system,
                   "intent": int(d["intent"]),
                   "appropriateness": int(d["appropriateness"]),
                   "judge": "llm", "judge_model": MODELS["judge"],
                   "machine_generated": True,
                   "calibration": (iid, system) in human and not full}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()

    # Agreement on the overlap
    llm = {(r["item_id"], r["system"]): r for r in load_jsonl(OUT)}
    overlap = [k for k in human if k in llm]
    if overlap:
        exact = sum(human[k]["intent"] == llm[k]["intent"] for k in overlap)
        off1 = sum(abs(human[k]["intent"] - llm[k]["intent"]) <= 1
                   for k in overlap)
        h = [human[k]["appropriateness"] for k in overlap]
        l = [llm[k]["appropriateness"] for k in overlap]
        n = len(overlap)
        mh, ml = sum(h) / n, sum(l) / n
        cov = sum((a - mh) * (b - ml) for a, b in zip(h, l))
        sh = sum((a - mh) ** 2 for a in h) ** 0.5
        sl = sum((b - ml) ** 2 for b in l) ** 0.5
        r = cov / (sh * sl) if sh and sl else float("nan")
        print(f"\nAgreement over {n} pairs (judge family: DeepSeek):")
        print(f"  intent exact:      {exact / n:.1%}")
        print(f"  intent off-by-one: {off1 / n:.1%}")
        print(f"  appropriateness r: {r:.3f}")
        print("  -> threshold for --full extension: intent exact >= 80%")
    print("\n" + fw.cost_report())


if __name__ == "__main__":
    main()
