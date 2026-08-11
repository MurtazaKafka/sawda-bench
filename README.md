# Sawda

A pilot benchmark for **intent-preserving translation of culturally loaded
trade communication** (Dari/Farsi ↔ English). ~60 fictional items, six
translation systems, one native-speaker validator/judge, an LLM judge
calibrated against the human labels afterward.

Every system is **open-weights**, so the whole comparison is reproducible
with one Fireworks API key and directly relevant to self-hosting economics.

## Pipeline

```
Phase 0  env check          FIREWORKS_API_KEY ping, model pinning, NLLB load
Phase 1  scaffold           this repo
Phase 2  item drafting      drafts/*.jsonl -> src/generate.py -> items/items.jsonl
GATE A   human validation   src/validate_ui.py  (>=55 items validated=true)
Phase 3  translation runs   src/translate.py -> results/translations.jsonl
Phase 4  human judging      src/judge_ui.py -> results/human_judgments.jsonl
GATE B   wait for labels
Phase 5  LLM judge          src/llm_judge.py (calibrate; --full if >=80% exact)
Phase 6  analysis           src/analyze.py -> tables, LaTeX, results.md
```

## Systems

| id | system | model | condition |
|---|---|---|---|
| A | nllb | facebook/nllb-200-distilled-600M (local) | lang codes pes_Arab / prs_Arab / eng_Latn |
| B | frontier_naive | `accounts/fireworks/models/kimi-k3` | bare "Translate to X" |
| C | frontier_audience | kimi-k3 | + audience/relationship from context |
| D | frontier_instructional | kimi-k3 | C + explicit norms + 3 few-shot (6 held-out items, excluded from eval for all systems) |
| E | small_naive | `accounts/fireworks/models/gpt-oss-20b` | same as B |
| F | small_audience | gpt-oss-20b | same as C |

LLM judge: `accounts/fireworks/models/deepseek-v4-pro` (DeepSeek family —
disjoint from Kimi and gpt-oss to reduce self-preference bias).

Note: the spec preferred a 32B-class Qwen for E/F; no 32B model was on the
Fireworks serverless catalog at pin time (2026-08-10), so gpt-oss-20b
(Apache-2.0, 20B MoE) is the mid-size arm.

## Item schema (items/items.jsonl)

`id, direction (fa2en|en2fa), utterance_src, context, literal_render,
intent_render, pragmatic_note, failure_class, tranche (seed|lit|synth),
validated, validator_note, lang_code (set at Gate A)`

failure_class ∈ intent_inversion, ritual_refusal_literal,
obligation_face_deleted, register_violation, indirect_refusal_as_assent.

All items are fictional: no real names, businesses, or identifying details.

## Ground rules

- Temperature 0 everywhere; every API call cached in `calls/*.jsonl`
  (sha256 of request), so reruns are free. Tokens logged per call;
  `python src/fw.py` prints the running dollar estimate.
- No fabricated items, translations, or labels. Every number in results.md
  traces to a file in this repo.
- Garbled/script-broken model output is recorded as-is and flagged, never
  silently fixed.

## Setup

```
python3 -m venv venv
./venv/bin/pip install anthropic requests transformers torch sentencepiece pandas
cp /path/to/.env .env   # FIREWORKS_API_KEY=...  (gitignored)
```
