#!/usr/bin/env python3
"""Bonus comparison arm: run trafilatura on the SAME annotated fixtures.

Reads each tests/fixtures/*.html, runs trafilatura's core extraction (HTML -> clean
article text, comments off), and dumps the RAW extracted text per fixture. NO metric is
computed here — metrics.py computes unit-level + token-level precision/recall for BOTH
tools from their raw dumps with ONE tokenizer, so the Readability-vs-trafilatura contrast
is same-testbed and fair. trafilatura reads the HTML with its own parser (not jsdom);
both tools see identical HTML bytes.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import trafilatura

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX_DIR = HERE / "fixtures"
RAW_DIR = PROJECT / "artifacts" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HOME = str(Path.home())
TMP = os.environ.get("TMPDIR", "").rstrip("/")


def redact(obj):
    if isinstance(obj, str):
        s = obj.replace(HOME, "~")
        if TMP:
            s = s.replace(TMP, "<TMP>")
        return s
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def main() -> int:
    gt = json.loads((FIX_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    out = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "trafilatura",
        "trafilatura_version": trafilatura.__version__,
        "settings": "extract(output_format='txt', include_comments=False, favor_recall default)",
        "fixtures": {},
    }
    for name in gt.keys():
        html = (FIX_DIR / f"{name}.html").read_text(encoding="utf-8")
        text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
        out["fixtures"][name] = {
            "extraction_ok": bool(text),
            "extracted_text": text,
            "extracted_len": len(text),
        }
    out["run_completed_at"] = datetime.now(timezone.utc).isoformat()
    (RAW_DIR / "trafilatura_raw.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"trafilatura arm done: {len(out['fixtures'])} fixtures -> trafilatura_raw.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
