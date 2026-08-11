"""Merge draft item files into items/items.jsonl with schema validation.

Drafts live in drafts/*.jsonl (one item per line). This script validates the
schema, checks ID uniqueness, and writes the combined items/items.jsonl.
It never invents content — it only assembles what was drafted and reviewed.

Usage: python src/generate.py
"""
import json
import sys
from pathlib import Path

from config import ITEMS, FAILURE_CLASSES, ROOT

REQUIRED = ["id", "direction", "utterance_src", "context", "literal_render",
            "intent_render", "pragmatic_note", "failure_class", "tranche",
            "validated", "validator_note"]
DIRECTIONS = {"fa2en", "en2fa"}
TRANCHES = {"seed", "lit", "synth"}


def validate(item: dict, lineno: str) -> list:
    errs = []
    for k in REQUIRED:
        if k not in item:
            errs.append(f"{lineno}: missing field '{k}'")
    if item.get("direction") not in DIRECTIONS:
        errs.append(f"{lineno}: bad direction {item.get('direction')!r}")
    if item.get("failure_class") not in FAILURE_CLASSES:
        errs.append(f"{lineno}: bad failure_class {item.get('failure_class')!r}")
    if item.get("tranche") not in TRANCHES:
        errs.append(f"{lineno}: bad tranche {item.get('tranche')!r}")
    return errs


def main():
    items, errors, seen = [], [], set()
    for path in sorted((ROOT / "drafts").glob("*.jsonl")):
        with path.open() as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                where = f"{path.name}:{i}"
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"{where}: bad JSON ({e})")
                    continue
                errors.extend(validate(item, where))
                if item.get("id") in seen:
                    errors.append(f"{where}: duplicate id {item['id']}")
                seen.add(item.get("id"))
                items.append(item)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    # Preserve Gate A state: edits made in items.jsonl win over stale drafts.
    if ITEMS.exists():
        with ITEMS.open() as f:
            current = {it["id"]: it for it in map(json.loads, f) if it}
        items = [current.get(it["id"], it) for it in items]
    ITEMS.parent.mkdir(exist_ok=True)
    with ITEMS.open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    by_tranche = {}
    for it in items:
        by_tranche[it["tranche"]] = by_tranche.get(it["tranche"], 0) + 1
    print(f"Wrote {len(items)} items to {ITEMS} — {by_tranche}")


if __name__ == "__main__":
    main()
