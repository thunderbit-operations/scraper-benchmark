#!/usr/bin/env python3
"""metrics.py — derives EVERY number from the raw element stream vs the ground-truth
labels (anti-hardcoding gate 3: no metric constant is written by hand).

Matching model (exact, sentinel-based):
  For each ground-truth block (unique sentinel token), find the extracted elements whose
  text contains that sentinel:
    - 0 elements                      -> outcome "DROPPED"
    - 1 element carrying ONLY this
      block's sentinel                -> outcome = that element's category (the clean case)
    - 1 element carrying this AND other
      blocks' sentinels               -> outcome "MERGED"  (structure collapsed)
    - >1 elements                      -> outcome "SPLIT"   (block fragmented)
  The per-block outcome is compared to the block's intended type.

Derived, per format:
  - confusion matrix   rows = intended type, cols = outcome (category | DROPPED|MERGED|SPLIT)
  - per-type recall    = blocks of type T whose outcome == T / blocks of type T
  - per-type precision = elements whose category == T that map to exactly one block of
                         intended type T / elements whose category == T
  - element_count vs intended block count (structure inflation/deflation)

Cross-format (per logical doc, over formats that share a block set):
  - per-block agreement: for each block, the set of outcomes across formats; "agree" iff
    all carriers produced the SAME outcome, "agree_with_intent" iff all == intended type
  - pairwise format agreement (fraction of shared blocks with identical outcome)
"""
from __future__ import annotations

import itertools
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

TYPES = ["Title", "NarrativeText", "ListItem", "Table"]
SPECIAL = ["DROPPED", "MERGED", "SPLIT"]

# The purpose-built CLASSIFICATION fixtures (one instance of each labeled block). d5_*
# (docx bullet-mode variants) and d7_large (60x repeat) reuse canonical blocks and would
# swamp the aggregate, so they are reported on their own axes, not folded into the
# per-type confusion aggregate.
CLASSIFICATION_SET = ["d1_canonical", "d2_table", "d3_adversarial", "d4_shortlist_mdblank"]


def redact(o):
    if isinstance(o, str):
        s = o.replace(HOME, "~")
        if TMP:
            s = s.replace(TMP, "<TMP>")
        return s
    if isinstance(o, list):
        return [redact(x) for x in o]
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items()}
    return o


def _contains(text: str, sentinel: str) -> bool:
    # sentinels are unique lowercase tokens; match case-insensitively so an ALL-CAPS
    # heading (which unstructured preserves in caps) is still located by its sentinel.
    return sentinel.lower() in (text or "").lower()


def outcome_for_block(block: dict, elements: list[dict], all_sentinels: set[str]) -> tuple[str, list[int]]:
    """Return (outcome, element_indices). outcome is a category string or a SPECIAL tag."""
    sent = block["sentinel"]
    hits = [i for i, e in enumerate(elements) if _contains(e.get("text"), sent)]
    if not hits:
        return "DROPPED", []
    if len(hits) > 1:
        return "SPLIT", hits
    idx = hits[0]
    etext = elements[idx].get("text") or ""
    others = [s for s in all_sentinels if s != sent and _contains(etext, s)]
    if others:
        return "MERGED", [idx]
    return (elements[idx].get("category") or "UncategorizedText"), [idx]


def per_format_metrics(blocks: list[dict], elements: list[dict]) -> dict:
    all_sent = {b["sentinel"] for b in blocks}
    # per-block outcome
    outcomes = {}
    for b in blocks:
        oc, idxs = outcome_for_block(b, elements, all_sent)
        outcomes[b["id"]] = {"intended": b["type"], "outcome": oc}

    # confusion matrix
    cols = TYPES + ["UncategorizedText"] + SPECIAL
    conf = {t: {c: 0 for c in cols} for t in TYPES}
    for b in blocks:
        oc = outcomes[b["id"]]["outcome"]
        col = oc if oc in cols else "UncategorizedText"
        if b["type"] in conf:
            conf[b["type"]][col] += 1

    # per-type recall
    recall = {}
    for t in TYPES:
        tot = sum(1 for b in blocks if b["type"] == t)
        hit = sum(1 for b in blocks if b["type"] == t and outcomes[b["id"]]["outcome"] == t)
        recall[t] = {"total": tot, "correct": hit, "recall": round(hit / tot, 4) if tot else None}

    # per-type precision: among extracted elements of category T, how many correspond to
    # exactly one intended-type-T block (clean match)
    precision = {}
    for t in TYPES:
        elems_t = [i for i, e in enumerate(elements) if (e.get("category") == t)]
        clean = 0
        for i in elems_t:
            etext = elements[i].get("text") or ""
            matched = [b for b in blocks if _contains(etext, b["sentinel"])]
            if len(matched) == 1 and matched[0]["type"] == t:
                clean += 1
        precision[t] = {
            "extracted": len(elems_t),
            "clean_correct": clean,
            "precision": round(clean / len(elems_t), 4) if elems_t else None,
        }

    correct_total = sum(1 for b in blocks if outcomes[b["id"]]["outcome"] == b["type"])
    return {
        "intended_block_count": len(blocks),
        "extracted_element_count": len(elements),
        "blocks_correct": correct_total,
        "overall_block_accuracy": round(correct_total / len(blocks), 4) if blocks else None,
        "recall_by_type": recall,
        "precision_by_type": precision,
        "confusion": conf,
        "per_block_outcome": outcomes,
    }


def cross_format(name: str, spec: dict, raw_fx: dict) -> dict | None:
    formats = [f for f in spec["formats"] if f in raw_fx and "elements" in raw_fx[f]]
    if len(formats) < 2:
        return None
    blocks = spec["blocks"]
    # outcome per (block, format)
    oc = {}
    for fmt in formats:
        els = raw_fx[fmt]["elements"]
        all_sent = {b["sentinel"] for b in blocks}
        for b in blocks:
            o, _ = outcome_for_block(b, els, all_sent)
            oc[(b["id"], fmt)] = o

    per_block = []
    agree_all = 0
    agree_intent = 0
    for b in blocks:
        row = {fmt: oc[(b["id"], fmt)] for fmt in formats}
        vals = set(row.values())
        all_same = len(vals) == 1
        all_intent = all(v == b["type"] for v in row.values())
        agree_all += 1 if all_same else 0
        agree_intent += 1 if all_intent else 0
        per_block.append({"id": b["id"], "intended": b["type"], "by_format": row,
                          "all_formats_agree": all_same, "all_match_intent": all_intent})

    # pairwise agreement
    pairwise = {}
    for a, c in itertools.combinations(formats, 2):
        same = sum(1 for b in blocks if oc[(b["id"], a)] == oc[(b["id"], c)])
        pairwise[f"{a}~{c}"] = round(same / len(blocks), 4)

    # element-count divergence
    counts = {fmt: raw_fx[fmt]["element_count"] for fmt in formats}
    return {
        "formats": formats,
        "intended_block_count": len(blocks),
        "element_counts": counts,
        "blocks_all_formats_agree": agree_all,
        "blocks_all_match_intent": agree_intent,
        "fraction_all_agree": round(agree_all / len(blocks), 4),
        "fraction_all_match_intent": round(agree_intent / len(blocks), 4),
        "pairwise_format_agreement": pairwise,
        "per_block": per_block,
    }


def aggregate_confusion(per_doc: dict, doc_names: list[str]) -> dict:
    cols = TYPES + ["UncategorizedText"] + SPECIAL
    out = {}
    for fmt in ["html", "md", "txt", "docx"]:
        conf = {t: {c: 0 for c in cols} for t in TYPES}
        recall_num = {t: [0, 0] for t in TYPES}
        for name in doc_names:
            doc = per_doc.get(name, {})
            if fmt not in doc:
                continue
            fm = doc[fmt]
            for t in TYPES:
                for c in cols:
                    conf[t][c] += fm["confusion"][t][c]
                recall_num[t][0] += fm["recall_by_type"][t]["correct"]
                recall_num[t][1] += fm["recall_by_type"][t]["total"]
        recall = {t: (round(recall_num[t][0] / recall_num[t][1], 4) if recall_num[t][1] else None)
                  for t in TYPES}
        out[fmt] = {"confusion": conf, "recall_by_type": recall,
                    "n_type_instances": {t: recall_num[t][1] for t in TYPES}}
    return out


def main() -> int:
    gt = json.loads((FIX / "ground_truth.json").read_text(encoding="utf-8"))
    raw = json.loads((RAW / "partition_raw.json").read_text(encoding="utf-8"))

    per_doc = {}
    for name, spec in gt.items():
        raw_fx = raw["fixtures"].get(name, {})
        doc_out = {}
        for fmt in spec["formats"]:
            if fmt not in raw_fx or "elements" not in raw_fx[fmt]:
                continue
            doc_out[fmt] = per_format_metrics(spec["blocks"], raw_fx[fmt]["elements"])
        per_doc[name] = doc_out

    cross = {}
    for name, spec in gt.items():
        c = cross_format(name, spec, raw["fixtures"].get(name, {}))
        if c:
            cross[name] = c

    agg = aggregate_confusion(per_doc, CLASSIFICATION_SET)

    # --- derived: docx bullet-mode ListItem recovery (H5) ---
    docx_bullet = {}
    for mode in ("style", "dash", "numpr"):
        name = f"d5_docx_{mode}"
        d = per_doc.get(name, {}).get("docx")
        if d:
            li = d["recall_by_type"]["ListItem"]
            docx_bullet[mode] = {"ListItem_recall": li["recall"],
                                 "ListItem_correct": li["correct"], "ListItem_total": li["total"]}

    # --- derived: markdown list-collapse (H4), blank vs no-blank before list ---
    md_collapse = {}
    for name in ("d4_shortlist_mdblank", "d4_shortlist_mdlazy"):
        d = per_doc.get(name, {}).get("md")
        if d:
            li = d["recall_by_type"]["ListItem"]
            md_collapse[name] = {
                "extracted_element_count": d["extracted_element_count"],
                "intended_block_count": d["intended_block_count"],
                "ListItem_recall": li["recall"], "ListItem_correct": li["correct"],
                "ListItem_total": li["total"],
                "outcomes": {bid: o["outcome"] for bid, o in d["per_block_outcome"].items()},
            }

    metrics = {
        "tool": "unstructured",
        "versions": raw.get("versions"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "classification_set": CLASSIFICATION_SET,
        "per_doc": per_doc,
        "aggregate_by_format_classification_set": agg,
        "docx_bullet_mode_listitem": docx_bullet,
        "markdown_list_collapse": md_collapse,
    }
    (RAW / "metrics.json").write_text(
        json.dumps(redact(metrics), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (RAW / "cross_format.json").write_text(
        json.dumps(redact(cross), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # console summary (derived)
    print("=== aggregate recall_by_type per format (CLASSIFICATION SET: d1,d2,d3,d4) ===")
    for fmt, a in agg.items():
        r = a["recall_by_type"]
        n = a["n_type_instances"]
        print(f"  {fmt:5s} Title={r['Title']}(n{n['Title']}) Narr={r['NarrativeText']}(n{n['NarrativeText']}) "
              f"List={r['ListItem']}(n{n['ListItem']}) Table={r['Table']}(n{n['Table']})")
    print("=== cross-format agreement (fraction all carriers agree / match intent) ===")
    for name, c in cross.items():
        print(f"  {name:26s} formats={','.join(c['formats']):18s} "
              f"all_agree={c['fraction_all_agree']} all_intent={c['fraction_all_match_intent']} "
              f"counts={c['element_counts']}")
    print("=== H5 docx bullet-mode ListItem recall ===")
    for mode, v in docx_bullet.items():
        print(f"  {mode:6s} ListItem_recall={v['ListItem_recall']} ({v['ListItem_correct']}/{v['ListItem_total']})")
    print("=== H4 markdown list collapse (blank vs no-blank) ===")
    for name, v in md_collapse.items():
        print(f"  {name:28s} elements={v['extracted_element_count']}/{v['intended_block_count']} "
              f"ListItem_recall={v['ListItem_recall']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
