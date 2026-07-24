#!/usr/bin/env python3
"""Deterministically re-derive the engine/cache matrix from the shipped response
artifacts — NO network, NO API key. Reads the *.md files already in
artifacts/raw/ and recomputes: byte size, distinct-author recall (/8), and the
two self-reported degradation flags Jina emits ("cached snapshot" /
"not fully loaded"). Then cross-checks those recomputed values against the
recorded engine-matrix.ndjson so that the recall/byte numbers used in the
writeup are provably computed from the responses, not hand-typed constants.

Ground truth: quotes.toscrape.com page 1 shows 10 quotes from 8 DISTINCT authors.
Recall = distinct authors whose surname token appears in the returned markdown / 8.
The surname tokens match the reproduction harness (tests/run_engine_matrix.sh).

  python3 tests/recompute_recall.py            # prints table + writes JSON
  python3 tests/recompute_recall.py --check     # exit 1 if it disagrees with ndjson
"""
import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "artifacts" / "raw"

# 8 distinct authors on quotes.toscrape.com page 1 (surname tokens == harness).
AUTHORS = ["Einstein", "Rowling", "Austen", "Monroe", "Gide", "Edison", "Roosevelt", "Martin"]

# label -> response file that the harness wrote for it.
LABELS = [
    "nc_js_default", "nc_js_direct", "nc_js_browser", "nc_js_browser_wait",
    "nc_static_default", "nc_static_direct", "cached_js",
]


def recall(text: str) -> int:
    lo = text.lower()
    return sum(1 for a in AUTHORS if a.lower() in lo)


def flags(text: str):
    lo = text.lower()
    return (
        bool(re.search(r"cached snapshot", lo)),
        bool(re.search(r"not.*fully loaded", lo)),
    )


def recompute():
    rows = []
    for label in LABELS:
        f = RAW / f"{label}.md"
        raw = f.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        cached, notloaded = flags(text)
        rows.append({
            "label": label,
            "bytes": len(raw),
            "recall_of_8": recall(text),
            "cached_snapshot": cached,
            "not_fully_loaded": notloaded,
        })
    return rows


def load_ndjson():
    """The shipped matrix is a pretty-printed JSON array of one object per line."""
    text = (RAW / "engine-matrix.ndjson").read_text()
    objs = []
    for line in text.splitlines():
        line = line.strip()
        if line in ("[", "]", ""):
            continue
        objs.append(json.loads(line.rstrip(",")))
    return {o["label"]: o for o in objs}


def main():
    rows = recompute()
    shipped = load_ndjson()

    print(f"{'label':22} {'bytes':>6} {'recall/8':>9} {'cached':>7} {'notload':>8}  matrix")
    ok = True
    for r in rows:
        s = shipped.get(r["label"], {})
        agree = (
            s.get("bytes") == r["bytes"]
            and s.get("recall_of_8") == r["recall_of_8"]
            and bool(s.get("cached_snapshot")) == r["cached_snapshot"]
            and bool(s.get("not_fully_loaded")) == r["not_fully_loaded"]
        )
        ok = ok and agree
        print(f"{r['label']:22} {r['bytes']:>6} {r['recall_of_8']:>9} "
              f"{str(r['cached_snapshot']):>7} {str(r['not_fully_loaded']):>8}  "
              f"{'OK' if agree else 'MISMATCH'}")

    out = RAW / "recall_recompute.json"
    out.write_text(json.dumps(
        {"ground_truth_authors": len(AUTHORS), "rows": rows,
         "consistent_with_shipped_matrix": ok}, indent=2) + "\n")
    print(f"\nground truth = {len(AUTHORS)} distinct authors; wrote {out.name}; "
          f"consistent_with_shipped_matrix = {ok}")

    if "--check" in sys.argv and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
