#!/usr/bin/env python
"""Verify the Reviewer-2 factual claims against repo data before editing the paper.

Run from repo root:  ./venv/bin/python paper/stats/verify_review_claims.py

Checks (all traceable to repo files):
 1. Human intent-label base rates and majority-class agreement baseline.
 2. Cohen's kappa for each LLM-judge arm vs human intent labels.
 3. DeepSeek missing pairs: which two, their human labels, agreement if
    counted as disagreements.
 4. Rubric v1 DeepSeek exact agreement.
 5. System D intent-1 judgments: direction, flags, notes.
 6. Item lang_codes (pes_Arab vs prs_Arab).
 7. Validation edit counts: drafts/*.jsonl vs items/items.jsonl fields.
 8. B (frontier_naive) broken-syntax flag split by direction.
 9. en2fa tranche composition (full pool and judged subset).
10. Direction asymmetry excluding the no-output small-model judgments.
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(p):
    return [json.loads(l) for l in (ROOT / p).read_text().splitlines() if l.strip()]

items = {d["id"]: d for d in load("items/items.jsonl")}
human = load("results/human_judgments.jsonl")
deeps = load("results/llm_judgments.jsonl")
fable = load("results/fable_judgments.jsonl")
v1 = load("results/llm_judgments_rubric_v1.jsonl")

hmap = {(j["item_id"], j["system"]): j for j in human}

# 1. base rates
cnt = Counter(j["intent"] for j in human)
print(f"1. human intent counts 3/2/1: {cnt[3]}/{cnt[2]}/{cnt[1]}  "
      f"majority-class baseline = {max(cnt.values())/len(human):.3f}")

# 2. kappas
def kappa(machine):
    pairs = [(hmap[(m['item_id'], m['system'])]['intent'], m['intent'])
             for m in machine if (m['item_id'], m['system']) in hmap]
    n = len(pairs)
    po = sum(1 for h, m in pairs if h == m) / n
    hc, mc = Counter(h for h, _ in pairs), Counter(m for _, m in pairs)
    pe = sum(hc[k] * mc[k] for k in set(hc) | set(mc)) / (n * n)
    return n, po, (po - pe) / (1 - pe)

for name, m in [("DeepSeek v2", deeps), ("Fable", fable), ("DeepSeek v1", v1)]:
    n, po, k = kappa(m)
    print(f"2/4. {name}: n={n} exact={po:.3f} kappa={k:.3f}")

# 3. DeepSeek missing pairs
dkeys = {(m["item_id"], m["system"]) for m in deeps}
missing = [k for k in hmap if k not in dkeys]
print(f"3. DeepSeek missing pairs: {missing} -> human intents "
      f"{[hmap[k]['intent'] for k in missing]}")
n178, po178, _ = kappa(deeps)
agree = round(po178 * n178)
print(f"   agreement counting missing as disagreement: {agree}/180 = {agree/180:.3f}")

# 5. D intent-1 judgments
print("5. D (frontier_instructional) intent-1 judgments:")
for j in human:
    if j["system"] == "frontier_instructional" and j["intent"] == 1:
        it = items[j["item_id"]]
        print(f"   {j['item_id']} dir={it['direction']} flags={j.get('flags')} "
              f"note={(j.get('note') or '')[:60]!r}")

# 6. lang codes
print(f"6. lang_code counts: {Counter(d.get('lang_code') for d in items.values())}")

# 7. validation edits: compare drafts vs final items
drafts = {}
for f in ["tranche1_seed.jsonl", "tranche2_lit.jsonl", "tranche3_synth.jsonl"]:
    for d in load(f"drafts/{f}"):
        drafts[d["id"]] = d
print(f"7. drafts total: {len(drafts)}; final items: {len(items)}; "
      f"validated: {sum(1 for d in items.values() if d.get('validated'))}")
print(f"   draft ids not in final: {sorted(set(drafts) - set(items))}")
edited = defaultdict(list)
for iid, it in items.items():
    if iid in drafts:
        for f in ["utterance_src", "literal_render", "intent_render", "context"]:
            if drafts[iid].get(f) != it.get(f):
                edited[iid].append(f)
fc = Counter(f for fl in edited.values() for f in fl)
print(f"   items with any edited field: {len(edited)}; per-field: {dict(fc)}")
noted = sum(1 for d in items.values() if (d.get('validator_note') or '').strip())
print(f"   items with validator_note: {noted}")

# 8. B broken-syntax split
b_bs = [j for j in human if j["system"] == "frontier_naive"
        and "broken_syntax" in (j.get("flags") or [])]
print(f"8. B broken_syntax total {len(b_bs)}: "
      f"{Counter(items[j['item_id']]['direction'] for j in b_bs)}")

# 9. en2fa tranche composition
en_all = [d for d in items.values() if d["direction"] == "en2fa"]
judged_ids = {j["item_id"] for j in human}
en_j = [d for d in en_all if d["id"] in judged_ids]
print(f"9. en2fa pool tranches: {Counter(d['tranche'] for d in en_all)} of {len(en_all)}; "
      f"judged en2fa: {Counter(d['tranche'] for d in en_j)} of {len(en_j)}")

# 10. direction excluding no-output judgments (empty translations)
trans = load("results/translations.jsonl")
tmap = {(t["item_id"], t["system"]): t for t in trans}
noout = [k for k, t in tmap.items() if not (t.get("output") or "").strip()]
print(f"10. empty translations: {noout}")
ex = set(noout)
for d in ["en2fa", "fa2en"]:
    js = [j for j in human if items[j["item_id"]]["direction"] == d
          and (j["item_id"], j["system"]) not in ex]
    k = sum(1 for j in js if j["intent"] == 1)
    print(f"    {d} excluding no-output: {k}/{len(js)} = {k/len(js):.3f}")
