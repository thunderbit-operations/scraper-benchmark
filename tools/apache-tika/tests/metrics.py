#!/usr/bin/env python3
"""metrics.py — derives EVERY number from artifacts/raw/tika_raw.json vs the ground-truth
labels (anti-hardcoding gate 3: no metric constant is written by hand). Reads only raw
observations; writes artifacts/raw/metrics.json.

H2 content recall (per carrier): fraction of ground-truth block sentinels that survive into
  Tika's --text output. Exact, case-insensitive sentinel substring membership.

H3 metadata behavior (per carrier): for each APPLICABLE field (author/title/created, per the
  fixture's metadata_applicability), did Tika surface it? author/title matched by sentinel
  membership across Tika's known metadata keys; created matched by exact ISO value.

H1 mime detection: per (true-type, ext-condition, filename-mode) cell, detected vs true —
  exact match + text-family match; rolled up into magic-bearing robustness vs magic-less
  degradation.

H4 robustness: exit codes (crash / no-crash) + detected charset + sentinel survival.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX = HERE / "fixtures"
RAW = PROJECT / "artifacts" / "raw"

HOME = str(Path.home())
TMP = (os.environ.get("TMPDIR", "") or "").rstrip("/")

# Tika metadata keys that may carry each logical field (observed on this host / documented).
AUTHOR_KEYS = ["dc:creator", "author", "meta:author", "creator"]
TITLE_KEYS = ["dc:title", "title"]
CREATED_KEYS = ["dcterms:created", "meta:creation-date", "pdf:docinfo:created", "created"]


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


def _has(text: str, sentinel: str) -> bool:
    return sentinel.lower() in (text or "").lower()


def _meta_val(meta: dict, keys) -> str | None:
    if not isinstance(meta, dict):
        return None
    for k in keys:
        if k in meta and meta[k]:
            v = meta[k]
            return v if isinstance(v, str) else (v[0] if isinstance(v, list) and v else str(v))
    return None


# ---- H2 content recall + H3 metadata ----------------------------------------------------
def content_metrics(gt: dict, raw_content: dict) -> dict:
    per_doc = {}
    for name, spec in gt.items():
        blocks = spec["blocks"]
        by_id = {b["id"]: b for b in blocks}
        blocks_by_format = spec.get("blocks_by_format", {})
        applic = spec.get("metadata_applicability", {})
        gt_meta = spec.get("metadata") or {}
        per_fmt = {}
        for fmt in spec["formats"]:
            r = raw_content.get(name, {}).get(fmt)
            if not r or "text" in r and r.get("text") is None:
                per_fmt[fmt] = {"error": "missing"}
                continue
            if "error" in r:
                per_fmt[fmt] = r
                continue
            text = r.get("text", "")
            # score recall against the blocks ACTUALLY authored into this carrier
            authored_ids = blocks_by_format.get(fmt, [b["id"] for b in blocks])
            sentinels = [by_id[i]["sentinel"] for i in authored_ids if i in by_id]
            found = [s for s in sentinels if _has(text, s)]
            missing = [s for s in sentinels if not _has(text, s)]
            # metadata field recovery (only applicable fields scored)
            meta = r.get("metadata", {})
            fa = applic.get(fmt, {})
            meta_result = {}
            if fa.get("author"):
                av = _meta_val(meta, AUTHOR_KEYS)
                meta_result["author"] = {"applicable": True,
                                         "recovered": bool(av and _has(av, gt_meta.get("author", "").split()[-1])),
                                         "value_key_present": av is not None}
            if fa.get("title"):
                tv = _meta_val(meta, TITLE_KEYS)
                meta_result["title"] = {"applicable": True,
                                        "recovered": bool(tv and _has(tv, gt_meta.get("title", "").split()[-1])),
                                        "value_key_present": tv is not None}
            if fa.get("created"):
                cv = _meta_val(meta, CREATED_KEYS)
                want = gt_meta.get("created")
                meta_result["created"] = {"applicable": True,
                                          "recovered_exact": bool(cv and want and cv[:19] == want[:19]),
                                          "value_present": cv is not None, "value": cv}
            per_fmt[fmt] = {
                "content_recall": round(len(found) / len(sentinels), 4) if sentinels else None,
                "blocks_total": len(sentinels), "blocks_found": len(found),
                "missing_sentinels": missing,
                "detected_content_type": _meta_val(meta, ["Content-Type"]),
                "text_exit": r.get("text_exit"),
                "determinism_text_identical": r.get("determinism_text_identical"),
                "metadata_fields": meta_result,
            }
        per_doc[name] = per_fmt
    return per_doc


# ---- H1 mime detection ------------------------------------------------------------------
def _text_family(mt: str) -> bool:
    return (mt or "").startswith("text/")


def mime_metrics(raw_mime: dict) -> dict:
    rows = []
    magic_cells_total = magic_cells_true = 0
    magicless_collapse_to_plain = 0
    magicless_cells = 0
    for e in raw_mime["entries"]:
        true = e["true_media_type"]
        has_magic = e["has_magic"]
        cells = {}
        for cond, d in e["detect"].items():
            for mode in ("with_filename", "from_stream"):
                detected = d[mode]
                exact = detected == true
                fam = _text_family(detected) and _text_family(true)
                cell = {"detected": detected, "exact": exact, "text_family": fam}
                cells[f"{cond}/{mode}"] = cell
                if has_magic:
                    magic_cells_total += 1
                    magic_cells_true += 1 if exact else 0
                else:
                    magicless_cells += 1
                    if detected == "text/plain" and true != "text/plain":
                        magicless_collapse_to_plain += 1
        rows.append({"tag": e["tag"], "true_media_type": true, "has_magic": has_magic,
                     "lying_ext_is": e["lying_ext_is"], "cells": cells})
    summary = {
        "magic_bearing_cells": magic_cells_total,
        "magic_bearing_exact": magic_cells_true,
        "magic_bearing_exact_rate": round(magic_cells_true / magic_cells_total, 4) if magic_cells_total else None,
        "magicless_cells": magicless_cells,
        "magicless_collapsed_to_text_plain": magicless_collapse_to_plain,
    }
    return {"rows": rows, "summary": summary}


# ---- H4 robustness ----------------------------------------------------------------------
def robustness_metrics(raw_robust: dict) -> dict:
    rows = []
    for e in raw_robust["entries"]:
        spec = e.get("spec", {})
        sent = spec.get("must_contain") or spec.get("sentinel")
        contains = _has(e.get("text", ""), sent) if sent else None
        extract_exits = [e.get("text_exit"), e.get("metadata_exit")]
        detect_exits = [e.get("detect_with_filename_exit"), e.get("detect_from_stream_exit")]
        rows.append({
            "name": e["name"], "case": e["case"],
            # extraction path exit 0 iff it did NOT throw; detection path exit 0 = triage survives
            "extraction_exit_zero": all(x == 0 for x in extract_exits),
            "detection_exit_zero": all(x == 0 for x in detect_exits),
            "text_exception": e.get("text_exception"),
            "exits": {"text": e.get("text_exit"), "metadata": e.get("metadata_exit"),
                      "detect_fn": e.get("detect_with_filename_exit"), "detect_stream": e.get("detect_from_stream_exit")},
            "detect_with_filename": e.get("detect_with_filename"),
            "detect_from_stream": e.get("detect_from_stream"),
            "detected_encoding": e.get("detected_encoding_meta"),
            "sentinel_survives": contains,
        })
    return {"rows": rows}


def main() -> int:
    gt = json.loads((FIX / "ground_truth.json").read_text(encoding="utf-8"))
    raw = json.loads((RAW / "tika_raw.json").read_text(encoding="utf-8"))

    metrics = {
        "tool": "apache-tika",
        "versions": raw.get("versions"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "content_and_metadata": content_metrics(gt, raw.get("content", {})),
        "mime_detection": mime_metrics(raw.get("mime", {})),
        "robustness": robustness_metrics(raw.get("robustness", {})),
    }
    (RAW / "metrics.json").write_text(
        json.dumps(redact(metrics), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # console summary (all derived)
    print("=== H2 content recall by carrier (fraction of block sentinels surviving --text) ===")
    for name, fm in metrics["content_and_metadata"].items():
        for fmt, m in fm.items():
            if "content_recall" in m:
                miss = f" MISSING={m['missing_sentinels']}" if m["missing_sentinels"] else ""
                print(f"  {name:10s} {fmt:5s} recall={m['content_recall']} "
                      f"({m['blocks_found']}/{m['blocks_total']}) ct={m['detected_content_type']}{miss}")
    print("=== H3 metadata field recovery (applicable fields only) ===")
    for name, fm in metrics["content_and_metadata"].items():
        for fmt, m in fm.items():
            mf = m.get("metadata_fields") or {}
            if mf:
                bits = []
                for f, v in mf.items():
                    ok = v.get("recovered") if "recovered" in v else v.get("recovered_exact")
                    bits.append(f"{f}={'Y' if ok else 'N'}")
                print(f"  {name:10s} {fmt:5s} {' '.join(bits)}")
    print("=== H1 mime detection summary ===")
    s = metrics["mime_detection"]["summary"]
    print(f"  magic-bearing exact: {s['magic_bearing_exact']}/{s['magic_bearing_cells']} "
          f"({s['magic_bearing_exact_rate']}); magic-less collapsed to text/plain: "
          f"{s['magicless_collapsed_to_text_plain']}/{s['magicless_cells']}")
    for r in metrics["mime_detection"]["rows"]:
        cells = r["cells"]
        line = " ".join(f"{k.split('/')[0][:4]}.{k.split('/')[1][:2]}={v['detected']}" for k, v in cells.items())
        print(f"  {r['tag']:5s} true={r['true_media_type']}")
        print(f"        {line}")
    print("=== H4 robustness (extraction_exit0 / detection_exit0 / exception) ===")
    for r in metrics["robustness"]["rows"]:
        print(f"  {r['name']:16s} extract_exit0={r['extraction_exit_zero']} detect_exit0={r['detection_exit_zero']} "
              f"det_fn={r['detect_with_filename']} enc={r['detected_encoding']} survives={r['sentinel_survives']}")
        if r["text_exception"]:
            print(f"        exception: {r['text_exception']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
