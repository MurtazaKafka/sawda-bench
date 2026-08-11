"""Phase 6: tables, preregistered answers, costs, results.md, LaTeX.

Every number traces to items/items.jsonl, results/translations.jsonl,
results/human_judgments.jsonl, results/llm_judgments.jsonl, and calls/*.jsonl.

Usage: python src/analyze.py
"""
import json
from collections import defaultdict

import pandas as pd

import fw
from config import ITEMS, MODELS, PRICES, RESULTS_DIR, SYSTEMS

# Self-hosting assumptions for cost #4 (stated in results.md):
GPU_HOUR_USD = 2.50          # ~1x A100-80G on-demand, mid-2026 cloud pricing
NLLB_MSGS_PER_GPU_HOUR = 40000   # 600M model, batched, ~11 msg/s
SMALL_MSGS_PER_GPU_HOUR = 6000   # 20B MoE, vLLM, short messages


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def judgments_frame():
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    rows = []
    for r in load_jsonl(RESULTS_DIR / "human_judgments.jsonl"):
        rows.append({**r, "source": "human"})
    seen = {(r["item_id"], r["system"]) for r in rows}
    for r in load_jsonl(RESULTS_DIR / "llm_judgments.jsonl"):
        if (r["item_id"], r["system"]) not in seen:
            rows.append({**r, "source": "llm"})
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No judgments found — run judge_ui.py first.")
    df["direction"] = df.item_id.map(lambda i: items[i]["direction"])
    df["failure_class"] = df.item_id.map(lambda i: items[i]["failure_class"])
    return df


def rate_table(df):
    g = df.groupby(["system", "direction"])
    out = g.intent.agg(n="count",
                       preserved=lambda s: (s == 3).mean(),
                       inverted=lambda s: (s == 1).mean(),
                       approp_mean="mean").reset_index()
    out["approp_mean"] = g.appropriateness.mean().values
    return out.round(3)


def failure_class_table(df):
    g = df.groupby(["system", "failure_class"])
    return g.intent.agg(n="count",
                        preserved=lambda s: (s == 3).mean(),
                        inverted=lambda s: (s == 1).mean()
                        ).reset_index().round(3)


def measured_cost_per_1k():
    """Measured tokens per translation call -> $ per 1,000 messages."""
    trans = load_jsonl(RESULTS_DIR / "translations.jsonl")
    per_sys = defaultdict(lambda: [0, 0, 0])  # n, tok_in, tok_out
    for r in trans:
        u = r.get("usage")
        if u:
            per_sys[r["system"]][0] += 1
            per_sys[r["system"]][1] += u.get("prompt_tokens", 0)
            per_sys[r["system"]][2] += u.get("completion_tokens", 0)
    rows = []
    for system in SYSTEMS:
        if system == "nllb":
            cost = GPU_HOUR_USD / NLLB_MSGS_PER_GPU_HOUR * 1000
            rows.append({"system": system, "basis": "self-hosted est.",
                         "usd_per_1k_msgs": round(cost, 4)})
            continue
        n, ti, to = per_sys[system]
        if not n:
            continue
        model = MODELS["small" if system.startswith("small") else "frontier"]
        pi, po = PRICES[model]
        api = (ti / n * pi + to / n * po) / 1e6 * 1000
        rows.append({"system": system, "basis": "API measured",
                     "usd_per_1k_msgs": round(api, 4)})
        if system.startswith("small"):
            sh = GPU_HOUR_USD / SMALL_MSGS_PER_GPU_HOUR * 1000
            rows.append({"system": system, "basis": "self-hosted est.",
                         "usd_per_1k_msgs": round(sh, 4)})
    return pd.DataFrame(rows)


def preregistered(df_human):
    d = df_human[df_human.system == "frontier_instructional"]
    c = df_human[df_human.system == "frontier_audience"]
    q1 = {"D_preserved": (d.intent == 3).mean(), "D_n": len(d),
          "C_preserved": (c.intent == 3).mean(), "C_n": len(c)}
    fa = df_human[df_human.direction == "fa2en"]
    en = df_human[df_human.direction == "en2fa"]
    q2 = {"fa2en_inverted": (fa.intent == 1).mean(), "fa2en_n": len(fa),
          "en2fa_inverted": (en.intent == 1).mean(), "en2fa_n": len(en)}
    return q1, q2


def to_latex(df, path, caption, label):
    body = df.to_latex(index=False, float_format="%.3f")
    (RESULTS_DIR / path).write_text(
        "\\begin{table}[t]\n\\centering\n" + body +
        f"\\caption{{{caption}}}\n\\label{{{label}}}\n\\end{{table}}\n")


def main():
    df = judgments_frame()
    human = df[df.source == "human"]
    print("== HUMAN-LABELED headline ==")
    print(rate_table(human).to_string(index=False))
    if (df.source == "llm").any():
        print("\n== FULL (human + machine-generated) headline ==")
        print(rate_table(df).to_string(index=False))
    print("\n== By failure_class (human) ==")
    print(failure_class_table(human).to_string(index=False))
    q1, q2 = preregistered(human)
    print("\nPreregistered Q1 (threshold test, human intent): "
          f"D={q1['D_preserved']:.1%} (n={q1['D_n']}) vs "
          f"C={q1['C_preserved']:.1%} (n={q1['C_n']})")
    print("Preregistered Q2 (direction asymmetry, human inversion): "
          f"fa2en={q2['fa2en_inverted']:.1%} (n={q2['fa2en_n']}) vs "
          f"en2fa={q2['en2fa_inverted']:.1%} (n={q2['en2fa_n']})")
    costs = measured_cost_per_1k()
    print("\n== Cost per 1,000 messages ==")
    print(costs.to_string(index=False))
    print("\n== Total API spend ==")
    print(fw.cost_report())

    to_latex(rate_table(human), "table_headline_human.tex",
             "Intent preservation by system and direction (human labels).",
             "tab:headline-human")
    to_latex(failure_class_table(human), "table_failure_class.tex",
             "Human-rated intent by failure class.", "tab:failure-class")
    to_latex(costs, "table_costs.tex",
             "Cost per 1{,}000 messages (measured tokens; self-hosted "
             "estimates use stated GPU-hour assumptions).", "tab:costs")
    print(f"\nLaTeX tables written to {RESULTS_DIR}/table_*.tex")
    print("results.md is assembled at Phase 6 with the example picks "
          "and caveats — see README.")


if __name__ == "__main__":
    main()
