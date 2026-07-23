#!/usr/bin/env python3
"""metrics.py — computes precision/recall from RAW extracted text vs the ground-truth
labels, for BOTH tools, with ONE tokenizer (anti-hardcoding gate 3: no metric constant
is written by hand; every number here is derived from the extracted text + the labels).

Two granularities, both derived, both reported:

  UNIT-LEVEL (headline, unambiguous):
    - article recall  = article units whose UNIQUE sentinel survives in extracted text
                        / total article units
    - boilerplate leak = boilerplate units whose sentinel survives (per btype)
    Sentinels are unique tokens, so "recovered/leaked" is exact substring membership —
    never fuzzy, never guessed.

  TOKEN-LEVEL (literature-comparable secondary, word-overlap word-F1):
    - tokenizer: lowercase, split on [^a-z0-9]+ (declared 口径)
    - gt article tokens = multiset over the union of ARTICLE unit texts (per-unit vocab
      is disjoint by construction, so tokens map to exactly one unit)
    - precision = |extracted ∩ gt_article| / |extracted|
    - recall    = |extracted ∩ gt_article| / |gt_article|   (multiset min-count overlap)
    - F1 = harmonic mean
    Reported per fixture + micro-averaged over the CONTENT-FIDELITY SET (fixtures with
    >=1 article AND >=1 boilerplate unit). Scoped as a CONTROLLED-fixture number, NOT a
    replacement for the public real-corpus benchmark (scrapinghub F1 0.887).
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX_DIR = HERE / "fixtures"
RAW_DIR = PROJECT / "artifacts" / "raw"

HOME = str(Path.home())
TMP = os.environ.get("TMPDIR", "").rstrip("/")

TOKEN_RE = re.compile(r"[a-z0-9]+")


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


def toks(text: str) -> Counter:
    return Counter(TOKEN_RE.findall((text or "").lower()))


def overlap(a: Counter, b: Counter) -> int:
    return sum((a & b).values())


def unit_metrics(units: list[dict], extracted: str) -> dict:
    et = extracted or ""
    art = [u for u in units if u["label"] == "article"]
    boiler = [u for u in units if u["label"] == "boilerplate"]
    art_recovered = [u["id"] for u in art if u["sentinel"] in et]
    boiler_leaked = [u["id"] for u in boiler if u["sentinel"] in et]
    # per-btype leak
    by = {}
    for u in boiler:
        b = u["btype"]
        by.setdefault(b, {"total": 0, "leaked": 0})
        by[b]["total"] += 1
        if u["sentinel"] in et:
            by[b]["leaked"] += 1
    return {
        "article_units": len(art),
        "article_units_recovered": len(art_recovered),
        "article_recall": round(len(art_recovered) / len(art), 4) if art else None,
        "article_missing_ids": [u["id"] for u in art if u["sentinel"] not in et],
        "boilerplate_units": len(boiler),
        "boilerplate_units_leaked": len(boiler_leaked),
        "boilerplate_leak_ids": boiler_leaked,
        "leak_by_btype": by,
    }


def token_metrics(units: list[dict], extracted: str) -> dict:
    gt_article = Counter()
    gt_boiler = Counter()
    for u in units:
        (gt_article if u["label"] == "article" else gt_boiler).update(toks(u["text"]))
    ex = toks(extracted)
    tp = overlap(ex, gt_article)  # extracted tokens that are article tokens
    ex_total = sum(ex.values())
    gt_total = sum(gt_article.values())
    contam = overlap(ex, gt_boiler)  # extracted tokens that are boilerplate tokens
    precision = tp / ex_total if ex_total else None
    recall = tp / gt_total if gt_total else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and (precision + recall) > 0
        else (0.0 if (precision is not None and recall is not None) else None)
    )
    return {
        "extracted_tokens": ex_total,
        "gt_article_tokens": gt_total,
        "gt_boilerplate_tokens": sum(gt_boiler.values()),
        "article_token_overlap": tp,
        "boilerplate_token_contamination": contam,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def compute_for_tool(gt: dict, raw: dict, tool_key: str) -> dict:
    per_fixture = {}
    for name, spec in gt.items():
        units = spec["units"]
        fx = raw["fixtures"].get(name, {})
        # readability raw nests extraction under "default"; trafilatura raw is flat
        extracted = fx.get("extracted_text")
        if extracted is None:
            extracted = fx.get("default", {}).get("extracted_text", "")
        per_fixture[name] = {
            "extraction_ok": bool(extracted),
            "unit_level": unit_metrics(units, extracted),
            "token_level": token_metrics(units, extracted),
        }
    # content-fidelity set: fixtures with >=1 article AND >=1 boilerplate unit
    cf_set = [
        n
        for n, s in gt.items()
        if any(u["label"] == "article" for u in s["units"])
        and any(u["label"] == "boilerplate" for u in s["units"])
    ]
    # micro-average token metrics over the content-fidelity set
    tp = ex = gt_tok = contam = 0
    art_units = art_rec = boiler_units = boiler_leak = 0
    for n in cf_set:
        tl = per_fixture[n]["token_level"]
        ul = per_fixture[n]["unit_level"]
        tp += tl["article_token_overlap"]
        ex += tl["extracted_tokens"]
        gt_tok += tl["gt_article_tokens"]
        contam += tl["boilerplate_token_contamination"]
        art_units += ul["article_units"]
        art_rec += ul["article_units_recovered"]
        boiler_units += ul["boilerplate_units"]
        boiler_leak += ul["boilerplate_units_leaked"]
    micro_p = tp / ex if ex else None
    micro_r = tp / gt_tok if gt_tok else None
    micro_f1 = (
        2 * micro_p * micro_r / (micro_p + micro_r)
        if micro_p and micro_r
        else None
    )
    return {
        "tool": tool_key,
        "per_fixture": per_fixture,
        "content_fidelity_set": cf_set,
        "micro_avg_over_content_fidelity_set": {
            "token_precision": round(micro_p, 4) if micro_p is not None else None,
            "token_recall": round(micro_r, 4) if micro_r is not None else None,
            "token_f1": round(micro_f1, 4) if micro_f1 is not None else None,
            "unit_article_recall": round(art_rec / art_units, 4) if art_units else None,
            "unit_boilerplate_leak_rate": round(boiler_leak / boiler_units, 4)
            if boiler_units
            else None,
            "article_units": art_units,
            "article_units_recovered": art_rec,
            "boilerplate_units": boiler_units,
            "boilerplate_units_leaked": boiler_leak,
            "boilerplate_token_contamination": contam,
        },
    }


def main() -> int:
    gt = json.loads((FIX_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    rd_raw = json.loads((RAW_DIR / "readability_raw.json").read_text(encoding="utf-8"))
    rd = compute_for_tool(gt, rd_raw, "@mozilla/readability")
    rd["source_versions"] = {
        "readability": rd_raw.get("readability_version"),
        "jsdom": rd_raw.get("jsdom_version"),
        "node": rd_raw.get("node_version"),
    }
    rd["computed_at"] = datetime.now(timezone.utc).isoformat()
    (RAW_DIR / "readability_metrics.json").write_text(
        json.dumps(redact(rd), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    comparison = {"note": "trafilatura arm not run"}
    tr_path = RAW_DIR / "trafilatura_raw.json"
    if tr_path.exists():
        tr_raw = json.loads(tr_path.read_text(encoding="utf-8"))
        tr = compute_for_tool(gt, tr_raw, "trafilatura")
        tr["source_versions"] = {"trafilatura": tr_raw.get("trafilatura_version")}
        tr["computed_at"] = datetime.now(timezone.utc).isoformat()
        (RAW_DIR / "trafilatura_metrics.json").write_text(
            json.dumps(redact(tr), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # same-testbed comparison table (per fixture: article recall + leak count)
        rows = []
        for n in gt.keys():
            r = rd["per_fixture"][n]
            t = tr["per_fixture"][n]
            rows.append(
                {
                    "fixture": n,
                    "readability_article_recall": r["unit_level"]["article_recall"],
                    "trafilatura_article_recall": t["unit_level"]["article_recall"],
                    "readability_boiler_leaked": r["unit_level"]["boilerplate_units_leaked"],
                    "trafilatura_boiler_leaked": t["unit_level"]["boilerplate_units_leaked"],
                    "readability_token_f1": r["token_level"]["f1"],
                    "trafilatura_token_f1": t["token_level"]["f1"],
                }
            )
        comparison = {
            "same_testbed": True,
            "readability_micro": rd["micro_avg_over_content_fidelity_set"],
            "trafilatura_micro": tr["micro_avg_over_content_fidelity_set"],
            "per_fixture": rows,
            "caveat": (
                "Controlled synthetic fixtures; NOT a replacement for the public "
                "real-corpus benchmark (scrapinghub Readability.js word-F1 0.887). Both "
                "tools see identical HTML bytes; trafilatura uses its own parser, "
                "Readability uses jsdom."
            ),
        }
    (RAW_DIR / "comparison.json").write_text(
        json.dumps(redact(comparison), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    m = rd["micro_avg_over_content_fidelity_set"]
    print(
        "metrics done. readability micro over content-fidelity set: "
        f"token P={m['token_precision']} R={m['token_recall']} F1={m['token_f1']} | "
        f"unit article_recall={m['unit_article_recall']} "
        f"boiler_leak_rate={m['unit_boilerplate_leak_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
