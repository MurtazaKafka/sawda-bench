"""Phase 3: run all six systems over validated items.

Systems (each sees ONLY what its condition allows):
  A nllb                  — local NLLB-200-600M, lang codes from item lang_code
  B frontier_naive        — kimi-k3, bare translate instruction, no context
  C frontier_audience     — kimi-k3, system prompt = audience/relationship
  D frontier_instructional— C + explicit norms + 3 few-shot from 6 held-out items
  E small_naive           — gpt-oss-20b, same prompt as B
  F small_audience        — gpt-oss-20b, same prompt as C

The 6 held-out items (few-shot pool for D) are excluded from evaluation for
ALL systems. Outputs append to results/translations.jsonl (idempotent: pairs
already present are skipped). Prints per-system cost at the end.

Usage: python src/translate.py [system ...]   # default: all
"""
import json
import random
import sys

import fw
from config import (ITEMS, MODELS, NLLB_MODEL, RESULTS_DIR, HELDOUT_FILE,
                    SYSTEMS)

OUT = RESULTS_DIR / "translations.jsonl"

INSTRUCTIONAL_NORMS = """You must account for Persian/Dari communicative norms when translating:
- Taarof: ritual politeness. A first (or second) refusal of an offer, payment, \
or hospitality is often ritual, not literal. "Qabel nadara" / "be my guest" \
style phrases in a shop are politeness, not a real waiver of payment.
- Indirectness: refusals and bad news are softened; phrases like "I'll see", \
"God willing", "we will be in touch" can be polite refusals, and agreement \
words can be mere acknowledgement rather than assent.
- Face and obligation: speakers protect their own and the listener's dignity; \
obligation and gratitude are often expressed through formulaic self-lowering \
("I am your servant") that must not be rendered literally.
- Register: elders, customers, and business partners receive deferential \
address; collapsing it to casual register changes the social meaning.
Translate so the intended meaning, force, and tone land correctly for the \
reader, not the surface words."""


def load_items():
    with ITEMS.open() as f:
        items = [json.loads(l) for l in f if l.strip()]
    return [it for it in items if it.get("validated")]


def pick_heldout(items):
    """6 validated items as D's few-shot pool; deterministic; saved to disk."""
    if HELDOUT_FILE.exists():
        return set(json.loads(HELDOUT_FILE.read_text()))
    rng = random.Random(0)
    fa2en = [it["id"] for it in items if it["direction"] == "fa2en"]
    en2fa = [it["id"] for it in items if it["direction"] == "en2fa"]
    held = rng.sample(fa2en, 4) + rng.sample(en2fa, 2)
    HELDOUT_FILE.write_text(json.dumps(held))
    return set(held)


def target_language(item):
    if item["direction"] == "fa2en":
        return "English"
    return "Dari" if item.get("lang_code") == "prs_Arab" else "Farsi"


def naive_messages(item):
    return [{"role": "user", "content":
             f"Translate the following message to {target_language(item)}: "
             f"{item['utterance_src']}"}]


def audience_messages(item):
    sys_prompt = (f"You are translating a real message. Context: "
                  f"{item['context']} Translate the message into "
                  f"{target_language(item)} so the intended meaning and tone "
                  f"land correctly for that reader. Output only the "
                  f"translation.")
    return [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": item["utterance_src"]}]


def instructional_messages(item, fewshot):
    sys_prompt = (f"You are translating a real message. Context: "
                  f"{item['context']} Translate the message into "
                  f"{target_language(item)} so the intended meaning and tone "
                  f"land correctly for that reader. Output only the "
                  f"translation.\n\n" + INSTRUCTIONAL_NORMS)
    msgs = [{"role": "system", "content": sys_prompt}]
    for ex in fewshot:
        msgs.append({"role": "user", "content": ex["utterance_src"]})
        msgs.append({"role": "assistant", "content": ex["intent_render"]})
    msgs.append({"role": "user", "content": item["utterance_src"]})
    return msgs


_nllb = None


def nllb_translate(item):
    global _nllb
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    if _nllb is None:
        tok = AutoTokenizer.from_pretrained(NLLB_MODEL)
        model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL)
        _nllb = (tok, model)
    tok, model = _nllb
    if item["direction"] == "fa2en":
        src, tgt = item.get("lang_code", "pes_Arab"), "eng_Latn"
    else:
        src, tgt = "eng_Latn", item.get("lang_code", "pes_Arab")
    tok.src_lang = src
    enc = tok(item["utterance_src"], return_tensors="pt")
    out = model.generate(**enc, max_new_tokens=200, num_beams=4,
                         forced_bos_token_id=tok.convert_tokens_to_ids(tgt))
    return tok.batch_decode(out, skip_special_tokens=True)[0]


def existing_pairs():
    done = set()
    if OUT.exists():
        with OUT.open() as f:
            for line in f:
                r = json.loads(line)
                done.add((r["item_id"], r["system"]))
    return done


def main():
    systems = sys.argv[1:] or SYSTEMS
    items = load_items()
    heldout = pick_heldout(items)
    fewshot_pool = [it for it in items if it["id"] in heldout]
    eval_items = [it for it in items if it["id"] not in heldout]
    done = existing_pairs()
    print(f"{len(eval_items)} eval items, {len(heldout)} held out, "
          f"systems: {systems}")

    with OUT.open("a") as out:
        for system in systems:
            for it in eval_items:
                if (it["id"], system) in done:
                    continue
                if system == "nllb":
                    text = nllb_translate(it)
                    rec = {"item_id": it["id"], "system": system,
                           "model": NLLB_MODEL, "output": text}
                else:
                    model = MODELS["small" if system.startswith("small")
                                   else "frontier"]
                    if system.endswith("_naive"):
                        msgs = naive_messages(it)
                    elif system.endswith("_audience"):
                        msgs = audience_messages(it)
                    else:  # frontier_instructional
                        same_dir = [ex for ex in fewshot_pool
                                    if ex["direction"] == it["direction"]]
                        pool = same_dir if len(same_dir) >= 3 else fewshot_pool
                        msgs = instructional_messages(it, pool[:3])
                    r = fw.call(model, msgs, max_tokens=1024)
                    rec = {"item_id": it["id"], "system": system,
                           "model": model, "output": r["text"].strip(),
                           "usage": r["usage"]}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"  {system:<24} {it['id']}")
    print("\nPer-system API cost:")
    print(fw.cost_report())


if __name__ == "__main__":
    main()
