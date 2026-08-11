"""Phase 4 / Gate B: blind human judging CLI.

Builds a judging plan once (results/judging_plan.json): a random 30-item
subset stratified by direction and failure_class, crossed with all systems.
System identity is hidden, order is randomized (seeded), and two candidates
for the same item are never adjacent. Each screen shows source, context, and
ONE candidate translation. Ratings: intent 3/2/1, appropriateness 1-7,
optional note. Every judgment is appended to results/human_judgments.jsonl
immediately, so you can quit (q) and resume anytime.

Usage: python src/judge_ui.py
"""
import json
import random
from collections import defaultdict

from config import ITEMS, RESULTS_DIR, SYSTEMS

PLAN = RESULTS_DIR / "judging_plan.json"
TRANSLATIONS = RESULTS_DIR / "translations.jsonl"
JUDGMENTS = RESULTS_DIR / "human_judgments.jsonl"
SUBSET_SIZE = 30
SEED = 7


def load_jsonl(path):
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def stratified_subset(items, rng):
    """~30 items spread across direction x failure_class strata."""
    strata = defaultdict(list)
    for it in items:
        strata[(it["direction"], it["failure_class"])].append(it)
    for v in strata.values():
        rng.shuffle(v)
    picked, i = [], 0
    while len(picked) < min(SUBSET_SIZE, len(items)):
        for key in sorted(strata):
            if i < len(strata[key]) and len(picked) < SUBSET_SIZE:
                picked.append(strata[key][i])
        i += 1
        if i > len(items):
            break
    return picked


def no_adjacent_order(pairs, rng, tries=1000):
    """Shuffle (item_id, system) pairs so equal item_ids are never adjacent."""
    for _ in range(tries):
        rng.shuffle(pairs)
        if all(pairs[i][0] != pairs[i + 1][0] for i in range(len(pairs) - 1)):
            return pairs
    raise RuntimeError("could not find non-adjacent ordering")


def build_plan():
    rng = random.Random(SEED)
    items = [it for it in load_jsonl(ITEMS) if it.get("validated")]
    have = {(r["item_id"], r["system"]) for r in load_jsonl(TRANSLATIONS)}
    translated_ids = {iid for iid, _ in have}
    items = [it for it in items if it["id"] in translated_ids]
    subset = stratified_subset(items, rng)
    pairs = [(it["id"], s) for it in subset for s in SYSTEMS
             if (it["id"], s) in have]
    order = no_adjacent_order(pairs, rng)
    PLAN.write_text(json.dumps({"order": order}, indent=1))
    return order


def main():
    if not PLAN.exists():
        order = build_plan()
    else:
        order = [tuple(p) for p in json.loads(PLAN.read_text())["order"]]
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    trans = {(r["item_id"], r["system"]): r for r in load_jsonl(TRANSLATIONS)}
    done = set()
    if JUDGMENTS.exists():
        done = {(r["item_id"], r["system"]) for r in load_jsonl(JUDGMENTS)}

    todo = [p for p in order if p not in done]
    print(f"{len(done)} done, {len(todo)} to go. "
          "intent: 3=preserved 2=degraded 1=inverted/deleted; approp: 1-7; "
          "q=quit (progress saved).")
    with JUDGMENTS.open("a") as out:
        for n, (iid, system) in enumerate(todo, 1):
            it = items[iid]
            print("\n" + "=" * 78)
            print(f"[{n}/{len(todo)}]")
            print(f"\nSOURCE ({it['direction']}):\n  {it['utterance_src']}")
            print(f"\nCONTEXT:\n  {it['context']}")
            print(f"\nCANDIDATE TRANSLATION:\n  {trans[(iid, system)]['output']}")
            intent = ""
            while intent not in ("1", "2", "3"):
                intent = input("\nintent (3/2/1, q to quit)> ").strip()
                if intent == "q":
                    return
            approp = ""
            while approp not in [str(i) for i in range(1, 8)]:
                approp = input("appropriateness (1-7)> ").strip()
                if approp == "q":
                    return
            note = input("note (optional)> ").strip()
            rec = {"item_id": iid, "system": system, "intent": int(intent),
                   "appropriateness": int(approp), "note": note,
                   "judge": "human"}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
    print("\nAll planned judgments collected.")


if __name__ == "__main__":
    main()
