#!/usr/bin/env python
"""Statistics for the Sawda paper, computed directly from repo data files.

Run from repo root:  ./venv/bin/python paper/stats/compute_stats.py

All tests are exact (no scipy needed):
- Wilson 95% score CIs for per-system preserved rates (n=30 each).
- Exact McNemar (two-sided exact binomial on discordant pairs) for paired
  system comparisons on the same 30 judged items.
- Fisher's exact test (two-sided, minimum-likelihood method) for the
  direction asymmetry (judgment-level; judgments are clustered within
  items, which the paper states as a caveat).
- Exact sign test for paired appropriateness comparisons (ordinal scale).

Every number printed here traces to results/human_judgments.jsonl and
items/items.jsonl.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ---------- load ----------
items = {}
for line in (ROOT / "items" / "items.jsonl").read_text().splitlines():
    if line.strip():
        d = json.loads(line)
        items[d["id"]] = d

judg = []
for line in (ROOT / "results" / "human_judgments.jsonl").read_text().splitlines():
    if line.strip():
        d = json.loads(line)
        d["direction"] = items[d["item_id"]]["direction"]
        judg.append(d)

assert len(judg) == 180, len(judg)

SYS = {
    "nllb": "A nllb-600M",
    "frontier_naive": "B kimi-k3 naive",
    "frontier_audience": "C kimi-k3 audience",
    "frontier_instructional": "D kimi-k3 instructional",
    "small_naive": "E gpt-oss-20b naive",
    "small_audience": "F gpt-oss-20b audience",
}

by_sys = defaultdict(dict)   # system -> item_id -> judgment
for j in judg:
    by_sys[j["system"]][j["item_id"]] = j

# ---------- exact helpers ----------

def wilson_ci(k, n, z=1.959963984540054):
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return center - half, center + half


def exact_binom_two_sided(b, n, p=0.5):
    """Two-sided exact binomial p-value, minimum-likelihood method."""
    if n == 0:
        return 1.0
    pmf = [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]
    obs = pmf[b]
    return min(1.0, sum(x for x in pmf if x <= obs + 1e-12))


def mcnemar_exact(pairs, pred):
    """pairs: list of (j1, j2); pred: judgment -> bool. Returns (b, c, n01, p)."""
    b = sum(1 for j1, j2 in pairs if pred(j1) and not pred(j2))
    c = sum(1 for j1, j2 in pairs if not pred(j1) and pred(j2))
    return b, c, exact_binom_two_sided(min(b, c), b + c)


def fisher_exact_two_sided(a, b, c, d):
    """2x2 table [[a,b],[c,d]], two-sided (min-likelihood)."""
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def hyper(x):
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)

    lo, hi = max(0, c1 - r2), min(r1, c1)
    obs = hyper(a)
    return min(1.0, sum(hyper(x) for x in range(lo, hi + 1) if hyper(x) <= obs + 1e-12))


def sign_test(pairs, key):
    """Exact sign test on paired ordinal values."""
    pos = sum(1 for j1, j2 in pairs if j1[key] > j2[key])
    neg = sum(1 for j1, j2 in pairs if j1[key] < j2[key])
    return pos, neg, exact_binom_two_sided(min(pos, neg), pos + neg)


def paired(s1, s2):
    ids = sorted(set(by_sys[s1]) & set(by_sys[s2]))
    assert len(ids) == 30, ids
    return [(by_sys[s1][i], by_sys[s2][i]) for i in ids]


pres = lambda j: j["intent"] == 3
inv = lambda j: j["intent"] == 1

# ---------- 1. Wilson CIs for preserved rates ----------
print("== Wilson 95% CIs, preserved (intent=3) rate per system, n=30 ==")
for s, name in SYS.items():
    js = list(by_sys[s].values())
    k = sum(pres(j) for j in js)
    lo, hi = wilson_ci(k, len(js))
    print(f"  {name}: {k}/{len(js)} = {k/len(js):.3f}  CI [{lo:.3f}, {hi:.3f}]")

# ---------- 2. Preregistered Q1: D vs C ----------
print("\n== Exact McNemar, paired on 30 items ==")
for s1, s2, label in [
    ("frontier_instructional", "frontier_audience", "D vs C, preserved"),
    ("frontier_instructional", "frontier_audience", "D vs C, inverted"),
    ("small_audience", "frontier_audience", "F vs C, preserved"),
    ("small_audience", "frontier_instructional", "F vs D, preserved"),
    ("small_audience", "frontier_naive", "F vs B, preserved"),
]:
    pred = inv if "inverted" in label else pres
    b, c, p = mcnemar_exact(paired(s1, s2), pred)
    print(f"  {label}: discordant {b}+{c}, exact p = {p:.3f}")

# ---------- 3. Preregistered Q2: direction asymmetry (judgment level) ----------
en2fa = [j for j in judg if j["direction"] == "en2fa"]
fa2en = [j for j in judg if j["direction"] == "fa2en"]
a = sum(inv(j) for j in en2fa)
bb = len(en2fa) - a
c = sum(inv(j) for j in fa2en)
d = len(fa2en) - c
p = fisher_exact_two_sided(a, bb, c, d)
print(f"\n== Direction asymmetry, intent=1 (inverted/deleted) ==")
print(f"  en2fa {a}/{len(en2fa)} = {a/len(en2fa):.3f}  vs  fa2en {c}/{len(fa2en)} = {c/len(fa2en):.3f}")
print(f"  Fisher exact (judgment level, two-sided) p = {p:.4f}")
print("  (judgments clustered within items: 6 judgments per item)")

# item-level robustness: per item count of intent-1 across 6 systems
per_item = defaultdict(int)
for j in judg:
    if inv(j):
        per_item[j["item_id"]] += 1
en_items = sorted(i for i in by_sys["nllb"] if items[i]["direction"] == "en2fa")
fa_items = sorted(i for i in by_sys["nllb"] if items[i]["direction"] == "fa2en")
en_counts = [per_item[i] for i in en_items]
fa_counts = [per_item[i] for i in fa_items]
print(f"  item-level inv counts (of 6): en2fa {sorted(en_counts, reverse=True)}")
print(f"                                 fa2en {sorted(fa_counts, reverse=True)}")
# cluster-robust check: items with >=1 inversion across the 6 systems
en_any = sum(1 for x in en_counts if x > 0)
fa_any = sum(1 for x in fa_counts if x > 0)
p_item = fisher_exact_two_sided(en_any, 15 - en_any, fa_any, 15 - fa_any)
print(f"  item-level (>=1 of 6 systems inverted): en2fa {en_any}/15 vs fa2en {fa_any}/15,"
      f" Fisher exact p = {p_item:.4f}")

# ---------- 4. Appropriateness, paired sign tests ----------
print("\n== Exact sign tests, appropriateness (paired, ordinal) ==")
for s1, s2, label in [
    ("frontier_audience", "frontier_instructional", "C vs D"),
    ("small_audience", "frontier_audience", "F vs C"),
    ("small_audience", "frontier_instructional", "F vs D"),
]:
    pos, neg, p = sign_test(paired(s1, s2), "appropriateness")
    print(f"  {label}: +{pos}/-{neg}, exact p = {p:.3f}")

# ---------- 5. sanity: en2fa intent-1 flag decomposition ----------
n_en_inv = [j for j in en2fa if inv(j)]
print(f"\n== en2fa judgments rated 1: {len(n_en_inv)} ==")
flagged = sum(
    1 for j in n_en_inv
    if set(j.get("flags") or []) & {"broken_syntax", "wrong_language"}
    or "wrong lang" in (j.get("note") or "").lower()
)
print(f"  with broken_syntax/wrong_language flags: {flagged}")
for j in n_en_inv:
    print(f"    {j['item_id']} {j['system']} flags={j.get('flags')} note={(j.get('note') or '')[:80]!r}")

def _load_jsonl(rel):
    return [json.loads(l) for l in (ROOT / rel).read_text().splitlines() if l.strip()]


def cohen_kappa():
    """Cohen's kappa on intent labels, each judge arm vs the human labels."""
    human = {(r["item_id"], r["system"]): r["intent"]
             for r in _load_jsonl("results/human_judgments.jsonl")}
    for name, path in [("DeepSeek v4-pro", "results/llm_judgments.jsonl"),
                       ("Fable agents", "results/fable_judgments.jsonl")]:
        other = {(r["item_id"], r["system"]): r["intent"]
                 for r in _load_jsonl(path)}
        keys = [k for k in human if k in other]
        n = len(keys)
        po = sum(human[k] == other[k] for k in keys) / n
        pe = sum((sum(human[k] == c for k in keys) / n) *
                 (sum(other[k] == c for k in keys) / n) for c in (1, 2, 3))
        print(f"  {name}: n={n}  observed={po:.3f}  expected={pe:.3f}  "
              f"kappa={(po - pe) / (1 - pe):.3f}")
    counts = {c: sum(1 for v in human.values() if v == c) for c in (1, 2, 3)}
    n = len(human)
    print(f"  human label counts: {counts} -> majority-class baseline "
          f"{max(counts.values())/n:.1%}")

print("\n== Cohen's kappa, judge vs human (intent) ==")
cohen_kappa()
