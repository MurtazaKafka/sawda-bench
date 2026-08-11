"""System A (NLLB) on Modal — the local 8GB machine swap-thrashes on torch.

Same checkpoint (facebook/nllb-200-distilled-600M), same lang codes, same
generation settings as the local path in translate.py; only the host differs
(recorded in each output row as host=modal). Run:

    ./venv/bin/modal run src/nllb_modal.py
"""
import json
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent.parent
NLLB_MODEL = "facebook/nllb-200-distilled-600M"

app = modal.App("sawda-nllb")
image = (modal.Image.debian_slim()
         .pip_install("torch", "transformers", "sentencepiece"))


@app.function(image=image, cpu=8, memory=16384, timeout=1800)
def translate_batch(jobs: list) -> list:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(NLLB_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL)
    out = []
    for j in jobs:
        tok.src_lang = j["src"]
        enc = tok(j["text"], return_tensors="pt")
        gen = model.generate(
            **enc, max_new_tokens=120, num_beams=2,
            forced_bos_token_id=tok.convert_tokens_to_ids(j["tgt"]))
        out.append({"item_id": j["item_id"],
                    "output": tok.batch_decode(
                        gen, skip_special_tokens=True)[0]})
    return out


@app.local_entrypoint()
def main():
    items = [json.loads(l) for l in
             (ROOT / "items" / "items.jsonl").open() if l.strip()]
    heldout = set(json.loads(
        (ROOT / "results" / "heldout_ids.json").read_text()))
    out_path = ROOT / "results" / "translations.jsonl"
    done = {(r["item_id"], r["system"])
            for r in map(json.loads, out_path.open())}
    jobs = []
    for it in items:
        if not it.get("validated") or it["id"] in heldout:
            continue
        if (it["id"], "nllb") in done:
            continue
        if it["direction"] == "fa2en":
            src, tgt = it.get("lang_code", "pes_Arab"), "eng_Latn"
        else:
            src, tgt = "eng_Latn", it.get("lang_code", "pes_Arab")
        jobs.append({"item_id": it["id"], "text": it["utterance_src"],
                     "src": src, "tgt": tgt})
    print(f"{len(jobs)} NLLB jobs -> Modal")
    if not jobs:
        return
    results = translate_batch.remote(jobs)
    with out_path.open("a") as f:
        for r in results:
            f.write(json.dumps(
                {"item_id": r["item_id"], "system": "nllb",
                 "model": NLLB_MODEL, "host": "modal-cpu8",
                 "output": r["output"]}, ensure_ascii=False) + "\n")
    print(f"appended {len(results)} nllb rows")
