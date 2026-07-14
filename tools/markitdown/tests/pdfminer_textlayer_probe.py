#!/usr/bin/env python3
"""
Text-layer probe for the MarkItDown review (root-cause check for FINDING-05).

Purpose: separately confirm that the scanned-PDF fixture used in the
document matrix has *no extractable text layer*, so an empty MarkItDown output
on it is the tool's genuine no-OCR behavior on a real scan, not an artifact of a
broken fixture. This is deliberately NOT MarkItDown: it goes straight to
`pdfminer.six`'s `extract_text` (the same text extractor MarkItDown's PDF path
sits on) and records the raw character count it recovers.

Every field below is computed from the run; nothing is hand-written. Not a
timing benchmark — no perf claims are derived from this script.
"""
import json
import os
import sys

from pdfminer.high_level import extract_text

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))


def _pick(*candidates):
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


# Works in both layouts: research pack (artifacts/fixtures, artifacts/raw)
# and the clean public repo (fixtures, results).
FIX = _pick(os.path.join(BASE, "artifacts", "fixtures"), os.path.join(BASE, "fixtures"))
RAW = _pick(os.path.join(BASE, "artifacts", "raw"), os.path.join(BASE, "results"))
os.makedirs(RAW, exist_ok=True)

SCANNED = os.path.join(FIX, "docs", "scanned_financial.pdf")


def probe(path):
    text = extract_text(path)
    stripped = text.strip()
    return {
        "fixture": os.path.relpath(path, BASE),
        "input_bytes": os.path.getsize(path),
        "extractor": "pdfminer.six high_level.extract_text",
        "raw_chars": len(text),
        "stripped_chars": len(stripped),
        "has_text_layer": len(stripped) > 0,
    }


def main():
    try:
        import pdfminer

        pdfminer_version = getattr(pdfminer, "__version__", "unknown")
    except Exception:
        pdfminer_version = "unknown"

    result = {
        "tool": "pdfminer.six",
        "pdfminer_version": pdfminer_version,
        "python": sys.version.split()[0],
        "scanned_financial": probe(SCANNED),
    }

    outp = os.path.join(RAW, "textlayer_probe.json")
    with open(outp, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    r = result["scanned_financial"]
    print(
        f"scanned_financial.pdf: {r['input_bytes']} bytes -> "
        f"pdfminer extract_text stripped_chars={r['stripped_chars']} "
        f"(has_text_layer={r['has_text_layer']})"
    )
    print(f"wrote {outp}")


if __name__ == "__main__":
    main()
