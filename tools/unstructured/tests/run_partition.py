#!/usr/bin/env python3
"""run_partition.py — the extraction arm. For every fixture x carrier format, calls the
format-specific partitioner and dumps the RAW element stream (category + class + text) +
element count + a 3-rep determinism check + a single-run timing. NO precision/recall is
computed here (anti-hardcoding split — metrics.py owns every derived number).

Format-specific partitioners are used on purpose: (a) it is the documented way to bypass
content sniffing, and (b) this host has NO libmagic, so the auto `partition()` entry is
unavailable. tesseract / poppler / torch are NOT required by any of these four paths.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from unstructured.partition.html import partition_html
from unstructured.partition.text import partition_text
from unstructured.partition.md import partition_md
from unstructured.partition.docx import partition_docx

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX = HERE / "fixtures"
RAW = PROJECT / "artifacts" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

HOME = str(Path.home())
TMP = (os.environ.get("TMPDIR", "") or "").rstrip("/")


def redact(o):
    if isinstance(o, str):
        s = o.replace(HOME, "~")
        if TMP:
            s = s.replace(TMP, "<TMP>")
        s = s.replace("/private/var/folders", "<TMP>").replace("/var/folders", "<TMP>")
        return s
    if isinstance(o, list):
        return [redact(x) for x in o]
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items()}
    return o


PARTITIONERS = {
    "html": lambda p: partition_html(filename=str(p)),
    "md": lambda p: partition_md(filename=str(p)),
    "txt": lambda p: partition_text(filename=str(p)),
    "docx": lambda p: partition_docx(filename=str(p)),
}


def elements_of(fmt: str, path: Path):
    return PARTITIONERS[fmt](path)


def dump_elements(els):
    return [
        {
            "category": getattr(e, "category", None),
            "class": type(e).__name__,
            "text": (e.text or ""),
        }
        for e in els
    ]


def run_one(fmt: str, path: Path) -> dict:
    t0 = time.perf_counter()
    els = elements_of(fmt, path)
    t1 = time.perf_counter()
    dumped = dump_elements(els)
    # determinism: 3 reps, compare the category sequence + text sequence
    seqs = []
    for _ in range(3):
        seqs.append([(getattr(e, "category", None), (e.text or "")) for e in elements_of(fmt, path)])
    determinism = {
        "reps_element_counts": [len(s) for s in seqs],
        "all_identical": all(s == seqs[0] for s in seqs),
    }
    return {
        "element_count": len(dumped),
        "elapsed_ms_single": round((t1 - t0) * 1000, 3),
        "elements": dumped,
        "determinism": determinism,
    }


def main() -> int:
    gt = json.loads((FIX / "ground_truth.json").read_text(encoding="utf-8"))
    out = {
        "tool": "unstructured",
        "run_started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "fixtures": {},
    }
    for name, spec in gt.items():
        rec = {}
        for fmt in spec["formats"]:
            path = FIX / f"{name}.{fmt}"
            if not path.exists():
                rec[fmt] = {"error": "fixture-file-missing"}
                continue
            rec[fmt] = run_one(fmt, path)
        out["fixtures"][name] = rec

    # versions (recorded, not asserted here)
    from unstructured.__version__ import __version__ as uv
    import sys
    vers = {"unstructured": uv, "python": sys.version.split()[0]}
    for mod in ("docx", "markdown", "lxml", "nltk"):
        try:
            m = __import__(mod)
            vers[mod] = getattr(m, "__version__", "unknown")
        except Exception:
            vers[mod] = "not-importable"
    out["versions"] = vers
    out["run_completed_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    (RAW / "partition_raw.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    n = sum(len(v) for v in out["fixtures"].values())
    print(f"run_partition done: {len(out['fixtures'])} docs, {n} (doc,format) runs -> artifacts/raw/partition_raw.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
