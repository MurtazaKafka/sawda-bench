"""Pinned models, prices, and paths for the Sawda pilot.

All scripted model calls go through Fireworks serverless. Model IDs pinned
2026-08-10 from the live catalog (see README for the selection rationale).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "items" / "items.jsonl"
CALLS_DIR = ROOT / "calls"
RESULTS_DIR = ROOT / "results"

# Exact serverless model IDs (verified with a 1-token ping on 2026-08-10).
MODELS = {
    # Systems B, C, D — frontier open instruct (Kimi flagship class)
    "frontier": "accounts/fireworks/models/kimi-k3",
    # Systems E, F — mid-size self-hostable arm. NOTE: no 32B-class Qwen was
    # on the serverless catalog at pin time; gpt-oss-20b (Apache-2.0, 20B MoE)
    # is the closest open-weights mid-size option.
    "small": "accounts/fireworks/models/gpt-oss-20b",
    # LLM judge — DeepSeek family, disjoint from Kimi (B-D) and gpt-oss (E-F).
    "judge": "accounts/fireworks/models/deepseek-v4-pro",
}

# $ per 1M tokens (input, output), Standard tier, docs.fireworks.ai/serverless/pricing
# fetched 2026-08-10. Cached-input discounts ignored (slight overestimate).
PRICES = {
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
    "accounts/fireworks/models/gpt-oss-20b": (0.07, 0.30),
    "accounts/fireworks/models/deepseek-v4-pro": (1.74, 3.48),
}

NLLB_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_CODES = {"fa": "pes_Arab", "prs": "prs_Arab", "en": "eng_Latn"}

FAILURE_CLASSES = [
    "intent_inversion",
    "ritual_refusal_literal",
    "obligation_face_deleted",
    "register_violation",
    "indirect_refusal_as_assent",
]

SYSTEMS = ["nllb", "frontier_naive", "frontier_audience",
           "frontier_instructional", "small_naive", "small_audience"]

# Held-out item IDs used only as few-shot examples for system D
# (excluded from evaluation for ALL systems). Written after Gate A.
HELDOUT_FILE = RESULTS_DIR / "heldout_ids.json"
