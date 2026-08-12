"""Phase 6: tables, preregistered answers, costs, results.md, LaTeX.

Human labels are the primary (and only) evaluation data: both LLM-judge arms
failed calibration (<80% exact intent agreement after one rubric iteration),
so machine labels are reported as an agreement finding, never as evaluation.

Every number traces to: items/items.jsonl, results/translations.jsonl,
results/human_judgments.jsonl, results/llm_judgments.jsonl,
results/fable_judgments.jsonl, calls/*.jsonl.

Usage: python src/analyze.py
"""
import json
from collections import Counter, defaultdict

import pandas as pd

import fw
from config import ITEMS, MODELS, PRICES, RESULTS_DIR, SYSTEMS

# Self-hosting assumptions (stated in results.md):
GPU_HOUR_USD = 2.50              # ~1x A100-80G on-demand, mid-2026
NLLB_MSGS_PER_GPU_HOUR = 40000   # 600M model, batched, ~11 msg/s
SMALL_MSGS_PER_GPU_HOUR = 6000   # 20B MoE via vLLM, short messages

SYSTEM_LABELS = {
    "nllb": "A nllb-600M",
    "frontier_naive": "B kimi-k3 naive",
    "frontier_audience": "C kimi-k3 audience",
    "frontier_instructional": "D kimi-k3 instructional",
    "small_naive": "E gpt-oss-20b naive",
    "small_audience": "F gpt-oss-20b audience",
}


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def human_frame():
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    rows = load_jsonl(RESULTS_DIR / "human_judgments.jsonl")
    df = pd.DataFrame(rows)
    df["direction"] = df.item_id.map(lambda i: items[i]["direction"])
    df["failure_class"] = df.item_id.map(lambda i: items[i]["failure_class"])
    return df


def rate_table(df, by=("system", "direction")):
    out = (df.groupby(list(by))
             .apply(lambda g: pd.Series({
                 "n": len(g),
                 "preserved": (g.intent == 3).mean(),
                 "degraded": (g.intent == 2).mean(),
                 "inverted": (g.intent == 1).mean(),
                 "approp": g.appropriateness.mean()}),
                 include_groups=False)
             .reset_index())
    if "system" in by:
        out["system"] = out["system"].map(SYSTEM_LABELS)
    return out.round(3)


def flags_table(df):
    recs = []
    for system, g in df.groupby("system"):
        c = Counter(f for fl in g["flags"].dropna() for f in fl)
        recs.append({"system": SYSTEM_LABELS[system], "n": len(g),
                     "iranian_register": c.get("iranian_register", 0),
                     "broken_syntax": c.get("broken_syntax", 0),
                     "wrong_language": c.get("wrong_language", 0)})
    return pd.DataFrame(recs)


def cost_table():
    trans = load_jsonl(RESULTS_DIR / "translations.jsonl")
    per = defaultdict(lambda: [0, 0, 0])
    for r in trans:
        u = r.get("usage")
        if u:
            per[r["system"]][0] += 1
            per[r["system"]][1] += u.get("prompt_tokens", 0)
            per[r["system"]][2] += u.get("completion_tokens", 0)
    rows = []
    for s in SYSTEMS:
        if s == "nllb":
            rows.append({"system": SYSTEM_LABELS[s],
                         "basis": "self-hosted est.",
                         "usd_per_1k": round(
                             GPU_HOUR_USD / NLLB_MSGS_PER_GPU_HOUR * 1e3, 4)})
            continue
        n, ti, to = per[s]
        model = MODELS["small" if s.startswith("small") else "frontier"]
        pi, po = PRICES[model]
        rows.append({"system": SYSTEM_LABELS[s], "basis": "API measured",
                     "usd_per_1k": round(
                         (ti / n * pi + to / n * po) / 1e6 * 1e3, 4)})
        if s == "small_audience":
            rows.append({"system": "E/F gpt-oss-20b", "basis":
                         "self-hosted est.",
                         "usd_per_1k": round(
                             GPU_HOUR_USD / SMALL_MSGS_PER_GPU_HOUR * 1e3, 4)})
    return pd.DataFrame(rows)


def agreement(human, other):
    overlap = [k for k in human if k in other]
    n = len(overlap)
    exact = sum(human[k]["intent"] == other[k]["intent"] for k in overlap) / n
    off1 = sum(abs(human[k]["intent"] - other[k]["intent"]) <= 1
               for k in overlap) / n
    h = [human[k]["appropriateness"] for k in overlap]
    l = [other[k]["appropriateness"] for k in overlap]
    mh, ml = sum(h) / n, sum(l) / n
    cov = sum((a - mh) * (b - ml) for a, b in zip(h, l))
    sh = sum((a - mh) ** 2 for a in h) ** 0.5
    sl = sum((b - ml) ** 2 for b in l) ** 0.5
    return n, exact, off1, cov / (sh * sl)


def pick_examples(df, k=5):
    """Worst literal failures paired with the best rival render of same item."""
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    trans = {(r["item_id"], r["system"]): r
             for r in load_jsonl(RESULTS_DIR / "translations.jsonl")}
    H = {(r.item_id, r.system): r for r in df.itertuples()}
    picked, used = [], set()
    cands = sorted(
        (r for r in df.itertuples()
         if r.system in ("nllb", "frontier_naive", "small_naive")
         and r.intent == 1),
        key=lambda r: (r.appropriateness,))
    for bad in cands:
        if bad.item_id in used:
            continue
        rivals = [H[(bad.item_id, s)] for s in SYSTEMS
                  if (bad.item_id, s) in H and s != bad.system]
        if not rivals:
            continue
        best = max(rivals, key=lambda r: (r.intent, r.appropriateness))
        if best.intent <= bad.intent:
            continue
        it = items[bad.item_id]
        picked.append({
            "item": bad.item_id, "source": it["utterance_src"],
            "context": it["context"],
            "bad_sys": SYSTEM_LABELS[bad.system],
            "bad_out": trans[(bad.item_id, bad.system)]["output"],
            "bad_score": f"intent {bad.intent}, approp {bad.appropriateness}",
            "bad_note": getattr(bad, "note", "") or "",
            "good_sys": SYSTEM_LABELS[best.system],
            "good_out": trans[(bad.item_id, best.system)]["output"],
            "good_score": f"intent {best.intent}, approp {best.appropriateness}"})
        used.add(bad.item_id)
        if len(picked) == k:
            break
    return picked


def to_latex(df, fname, caption, label):
    body = df.to_latex(index=False, float_format="%.3f")
    (RESULTS_DIR / fname).write_text(
        "\\begin{table}[t]\n\\centering\n\\small\n" + body +
        f"\\caption{{{caption}}}\n\\label{{{label}}}\n\\end{{table}}\n")


def main():
    df = human_frame()
    headline = rate_table(df)
    overall = rate_table(df, by=("system",))
    byclass = rate_table(df, by=("system", "failure_class"))
    fl = flags_table(df)
    costs = cost_table()

    d = df[df.system == "frontier_instructional"]
    c = df[df.system == "frontier_audience"]
    fa, en = df[df.direction == "fa2en"], df[df.direction == "en2fa"]

    human = {(r["item_id"], r["system"]): r
             for r in load_jsonl(RESULTS_DIR / "human_judgments.jsonl")}
    ds = {(r["item_id"], r["system"]): r
          for r in load_jsonl(RESULTS_DIR / "llm_judgments.jsonl")}
    fb = {(r["item_id"], r["system"]): r
          for r in load_jsonl(RESULTS_DIR / "fable_judgments.jsonl")}
    ags = {name: agreement(human, other)
           for name, other in [("DeepSeek v4-pro", ds), ("Fable agents", fb)]}

    print("== Overall (human labels, n=180) ==")
    print(overall.to_string(index=False))
    print("\n== By direction ==")
    print(headline.to_string(index=False))
    print("\n== Validator flags ==")
    print(fl.to_string(index=False))
    print("\nQ1 threshold test: D preserved "
          f"{(d.intent == 3).mean():.1%} vs C {(c.intent == 3).mean():.1%} "
          f"(n={len(d)} each)")
    print("Q2 direction asymmetry: inversion fa2en "
          f"{(fa.intent == 1).mean():.1%} vs en2fa {(en.intent == 1).mean():.1%}")
    for name, (n, ex, o1, r) in ags.items():
        print(f"judge {name}: n={n} exact {ex:.1%} off1 {o1:.1%} r {r:.2f}")
    print("\n== Cost per 1,000 messages ==")
    print(costs.to_string(index=False))
    print("\n" + fw.cost_report())

    to_latex(headline, "table_headline_human.tex",
             "Intent preservation by system and direction (human labels, "
             "$n=180$ judgments over 30 items).", "tab:headline-human")
    to_latex(byclass, "table_failure_class.tex",
             "Human-rated intent by failure class.", "tab:failure-class")
    to_latex(costs, "table_costs.tex",
             "Cost per 1{,}000 messages (measured tokens; self-hosted "
             "estimates assume \\$2.50/GPU-h A100).", "tab:costs")
    to_latex(fl, "table_flags.tex",
             "Validator quick-flags per system (30 judgments each).",
             "tab:flags")

    write_results_md(overall, headline, byclass, fl, costs, ags, df, d, c,
                     fa, en)
    print(f"\nWrote results/results.md and {RESULTS_DIR}/table_*.tex")


def write_results_md(overall, headline, byclass, fl, costs, ags, df,
                     d, c, fa, en):
    ex = pick_examples(df)
    j = len(df)
    md = []
    md.append("# Sawda pilot — results\n")
    md.append("All systems are open-weights; the full comparison reproduces "
              "with one Fireworks API key (NLLB ran on a Modal CPU worker; "
              "same checkpoint). All numbers below derive from "
              "`results/human_judgments.jsonl` (n=180 blind judgments by one "
              "native Dari-speaking validator over a stratified 30-item "
              "subset), `results/translations.jsonl`, and `calls/*.jsonl`.\n")
    md.append("## Headline: intent preservation (human labels)\n")
    md.append(overall.to_markdown(index=False))
    md.append("\n### By direction\n")
    md.append(headline.to_markdown(index=False))
    md.append("\n### Validator quick-flags\n")
    md.append(fl.to_markdown(index=False))
    md.append("\n## Preregistered questions\n")
    md.append(f"**Q1 (threshold test).** D (instructional) preserved intent "
              f"in {(d.intent == 3).mean():.1%} of judgments vs C (audience) "
              f"{(c.intent == 3).mean():.1%} (n={len(d)} each; 30-item "
              f"subset). Mean appropriateness: D "
              f"{d.appropriateness.mean():.2f} vs C "
              f"{c.appropriateness.mean():.2f}.\n")
    md.append(f"**Q2 (direction asymmetry).** Intent inversion/deletion "
              f"(rating 1): fa2en {(fa.intent == 1).mean():.1%} vs en2fa "
              f"{(en.intent == 1).mean():.1%} "
              f"(n={len(fa)} / {len(en)}).\n")
    md.append("## LLM judge calibration — failed, reported as a finding\n")
    md.append("Machine labels were **not** extended to unjudged items: both "
              "judge arms stayed far below the preregistered 80% exact-"
              "agreement bar after one rubric iteration, so every evaluation "
              "number in this report is human-labeled.\n")
    for name, (n, exx, o1, r) in ags.items():
        md.append(f"- {name}: n={n}, intent exact {exx:.1%}, off-by-one "
                  f"{o1:.1%}, appropriateness Pearson r {r:.2f}")
    md.append("\nJudge families: systems are Kimi (B–D) and gpt-oss (E–F); "
              "judges are DeepSeek (scripted via Fireworks, reproducible) "
              "and Claude Fable 5 agents (run via a Claude Code "
              "subscription session — not reproducible from the API key "
              "alone; Fable also drafted the item pool's reference renders, "
              "a possible style-affinity bias).\n")
    md.append("## Cost per 1,000 messages\n")
    md.append(costs.to_markdown(index=False))
    md.append("\nAssumptions for self-hosted rows: $2.50/GPU-hour (A100-80G "
              "class, mid-2026 on-demand); NLLB-600M ~40k msgs/GPU-h "
              "batched; gpt-oss-20B ~6k msgs/GPU-h via vLLM on short "
              "messages. API rows use measured tokens at pinned prices "
              "(kimi-k3 $3/$15 per 1M in/out; gpt-oss-20b $0.07/$0.30; "
              "docs.fireworks.ai, 2026-08-10). Note gpt-oss-20b's measured "
              "cost includes its (sometimes unbounded) reasoning tokens: 4 "
              "of 108 small-system calls produced no translation at any "
              "budget and are scored as deleted intent.\n")
    md.append("## Five side-by-side failures\n")
    for e in ex:
        md.append(f"### {e['item']}\n")
        md.append(f"> **Source:** {e['source']}\n>\n"
                  f"> **Context:** {e['context']}\n")
        md.append(f"- **{e['bad_sys']}** ({e['bad_score']}"
                  + (f"; validator: “{e['bad_note']}”" if e['bad_note']
                     else "") + f"):\n\n  {e['bad_out'][:400]}\n")
        md.append(f"- **{e['good_sys']}** ({e['good_score']}):\n\n"
                  f"  {e['good_out'][:400]}\n")
    md.append("## By failure class\n")
    md.append(byclass.to_markdown(index=False))
    md.append("\n## Caveats, honestly\n")
    md.append("- n=30 items judged (of 54 evaluated; 60 validated minus 6 "
              "held out for few-shot), 180 judgments; single validator who "
              "is also the item author/editor; no inter-annotator data.\n"
              "- Both LLM-judge families failed calibration; results are "
              "human-only and the judged subset, while stratified, is "
              "small.\n"
              "- Items are fictional and partly synthetic (32 of 60); "
              "synthetic items were human-validated but share pragmatic "
              "cores with their parents.\n"
              "- kimi-k3 outputs sometimes include visible deliberation/"
              "commentary; judged verbatim as delivered text.\n"
              "- The Dari register target is Afghan; several systems "
              "drifted to Iranian Farsi (see flags table) — flagged by the "
              "validator, penalized mainly in appropriateness.\n")
    (RESULTS_DIR / "results.md").write_text("\n".join(md))


if __name__ == "__main__":
    main()
