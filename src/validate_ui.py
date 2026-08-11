"""Gate A: one-item-at-a-time CLI review with inline editing.

For each unreviewed item: shows all fields, lets the validator edit any field,
set the NLLB lang_code (prs_Arab for Dari-register, pes_Arab otherwise),
then approve (validated=true) or reject. Progress is written back to
items/items.jsonl after every decision, so you can stop and resume anytime.

Usage: python src/validate_ui.py            # review unreviewed items
       python src/validate_ui.py --redo ID  # reopen a specific item
"""
import json
import sys

from config import ITEMS, FAILURE_CLASSES

EDITABLE = ["utterance_src", "context", "literal_render", "intent_render",
            "pragmatic_note", "failure_class", "direction"]


def load():
    with ITEMS.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def save(items):
    tmp = ITEMS.with_suffix(".tmp")
    with tmp.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    tmp.replace(ITEMS)


def show(item, pos, total):
    print("\n" + "=" * 78)
    print(f"[{pos}/{total}]  {item['id']}  dir={item['direction']}  "
          f"class={item['failure_class']}  tranche={item['tranche']}")
    print("=" * 78)
    for k in ("utterance_src", "context", "literal_render", "intent_render",
              "pragmatic_note"):
        print(f"\n  {k}:\n    {item[k]}")
    print(f"\n  lang_code: {item.get('lang_code', '(unset)')}")


def edit_field(item):
    for i, k in enumerate(EDITABLE, 1):
        print(f"  {i}. {k}")
    try:
        idx = int(input("field #> ")) - 1
        k = EDITABLE[idx]
    except (ValueError, IndexError):
        print("  ?")
        return
    print(f"  current: {item[k]}")
    if k == "failure_class":
        print("  options: " + ", ".join(FAILURE_CLASSES))
    new = input("  new value> ").strip()
    if new:
        item[k] = new
        print("  updated.")


def review(item, pos, total):
    """Returns True when a decision was made, 'quit' to stop."""
    while True:
        show(item, pos, total)
        print("\n[a]pprove  [r]eject  [e]dit field  [d]ari register (prs_Arab)"
              "  [f]arsi register (pes_Arab)  [n]ote  [s]kip  [q]uit")
        c = input("> ").strip().lower()
        if c == "a":
            if "lang_code" not in item:
                item["lang_code"] = "pes_Arab"
                print("  (lang_code defaulted to pes_Arab)")
            item["validated"] = True
            item.pop("rejected", None)
            return True
        if c == "r":
            item["validated"] = False
            item["rejected"] = True
            note = input("  reject reason> ").strip()
            item["validator_note"] = note or item.get("validator_note", "")
            return True
        if c == "e":
            edit_field(item)
        elif c == "d":
            item["lang_code"] = "prs_Arab"
            print("  lang_code=prs_Arab")
        elif c == "f":
            item["lang_code"] = "pes_Arab"
            print("  lang_code=pes_Arab")
        elif c == "n":
            item["validator_note"] = input("  note> ").strip()
        elif c == "s":
            return True
        elif c == "q":
            return "quit"


def main():
    items = load()
    if len(sys.argv) > 2 and sys.argv[1] == "--redo":
        targets = [it for it in items if it["id"] == sys.argv[2]]
    else:
        targets = [it for it in items
                   if not it["validated"] and not it.get("rejected")]
    total = len(targets)
    if not total:
        print("Nothing to review.")
    for pos, item in enumerate(targets, 1):
        if review(item, pos, total) == "quit":
            break
        save(items)
    done = sum(1 for it in items if it["validated"])
    rej = sum(1 for it in items if it.get("rejected"))
    print(f"\nvalidated={done}  rejected={rej}  "
          f"pending={len(items) - done - rej}  (need >=55 validated)")


if __name__ == "__main__":
    main()
