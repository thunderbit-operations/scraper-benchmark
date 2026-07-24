#!/usr/bin/env python3
"""probe_title_mechanism.py — isolates WHY a heading-like line becomes NarrativeText in
plain text (partition_text), separating two candidate mechanisms:

  (A) the title_max_word_length=12 cliff in is_possible_title, vs
  (B) the presence of a VERB, which makes is_possible_narrative_text match — and that
      check runs BEFORE is_possible_title in _text_to_element (text.py: L149 narrative
      -> L155 title). So a verb-bearing line is claimed as NarrativeText before the
      word-count title rule is ever evaluated.

2x2 design (word-count x verb), each fed as a single plain-text line:
  - 5 words  + verb    -> predict NarrativeText  (verb triggers narrative; NOT word count)
  - 5 words  + no verb -> predict Title          (no verb -> title fallback, <=12 words)
  - 13 words + verb    -> predict NarrativeText  (verb triggers narrative; word count irrelevant)  == d3-over shape
  - 13 words + no verb -> predict UncategorizedText (no verb -> not narrative; >12 words -> not title -> base Text)

If (B) is the mechanism, the two verb rows are NarrativeText regardless of word count, and
the two no-verb rows split Title(5w)/Uncategorized(13w) on the word-count boundary — i.e.
the 12-word cliff governs Title-vs-Text ONLY in the no-verb case, and never explains the
verb-bearing d3-over line. Dumps raw categories + the internal heuristic booleans.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from unstructured.partition.text import partition_text
from unstructured.partition.text_type import (
    contains_verb,
    is_possible_narrative_text,
    is_possible_title,
)

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "artifacts" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
HOME = str(Path.home())
TMP = (os.environ.get("TMPDIR", "") or "").rstrip("/")


def redact(o):
    if isinstance(o, str):
        s = o.replace(HOME, "~")
        return s.replace(TMP, "<TMP>") if TMP else s
    if isinstance(o, list):
        return [redact(x) for x in o]
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items()}
    return o


# Each case is ONE line. Verb rows use finite verbs (shipped / contains / exceeding);
# no-verb rows are pure noun phrases. Word counts are exact.
CASES = [
    ("5w_verb",    "The team shipped the release",                                          5,  True),
    ("5w_noverb",  "Quarterly regional vendor category summary",                             5,  False),
    ("13w_verb",   "This heading deliberately contains thirteen separate ordinary words "
                   "exceeding the configured word limit",                                    13, True),
    ("13w_noverb", "Quarterly regional vendor category product office contact record "
                   "summary table appendix index glossary",                                  13, False),
]


def main() -> int:
    out = {"probe": "title-vs-narrative mechanism (word-count x verb)",
           "dispatch_order_note": "text.py _text_to_element: is_possible_narrative_text (L149) "
                                  "returns NarrativeText BEFORE is_possible_title (L155)",
           "cases": []}
    for cid, text, nwords, has_verb_intended in CASES:
        els = partition_text(text=text)
        cats = [e.category for e in els]
        rec = {
            "id": cid,
            "text": text,
            "word_count": len(text.split(" ")),
            "declared_word_count": nwords,
            "declared_has_verb": has_verb_intended,
            "partition_text_categories": cats,
            "primary_category": cats[0] if cats else None,
            "internal_contains_verb": contains_verb(text),
            "internal_is_possible_narrative_text": is_possible_narrative_text(text),
            "internal_is_possible_title": is_possible_title(text),
        }
        out["cases"].append(rec)

    (RAW / "probe_title_mechanism.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("=== title-vs-narrative mechanism probe (partition_text) ===")
    print(f"{'case':11s} {'words':5s} {'verb':5s} {'->category':18s} "
          f"{'narr?':6s} {'title?':7s}")
    for r in out["cases"]:
        print(f"{r['id']:11s} {r['declared_word_count']:<5d} "
              f"{str(r['internal_contains_verb']):5s} {str(r['primary_category']):18s} "
              f"{str(r['internal_is_possible_narrative_text']):6s} "
              f"{str(r['internal_is_possible_title']):7s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
