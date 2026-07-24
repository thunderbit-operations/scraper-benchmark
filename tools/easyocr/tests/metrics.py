#!/usr/bin/env python3
"""metrics.py — computes CER/WER/recall from the RAW EasyOCR boxes vs the ground-truth
strings, for every fixture. Anti-hardcoding gate 3: NO error-rate constant is written by
hand — every CER/WER/threshold here is derived from the raw recognized text + the labels.

口径 (declared):
  - reading-order join (line-aware; see join_boxes): recognized boxes are grouped into
    visual lines by vertical bbox overlap, lines ordered top-to-bottom and boxes within a
    line left-to-right, joined with a single space. A naive global y-then-x sort would
    scramble a line the detector splits into side-by-side boxes.
  - normalization: collapse runs of whitespace to one space, strip ends; CASE-SENSITIVE
    (OCR case fidelity matters). Applied identically to prediction and ground truth.
  - CER = Levenshtein(pred_chars, gt_chars) / len(gt_chars)   (edit distance, standard).
  - WER = Levenshtein(pred_words, gt_words) / len(gt_words).
  - A CER can exceed 1.0 when the prediction inserts a lot of spurious text; reported as-is.

collapse threshold: for a monotone sweep (size / contrast / rotation), the derived boundary
is the sweep value at which CER first crosses COLLAPSE_CER (0.30) — computed, not asserted.

screenshot: each recognized box -> axis-aligned bbox; each GT element matched to the
recognized box of maximum IoU; matched iff IoU >= IOU_MATCH (0.30). detection_recall =
matched GT elements / total; per-element CER computed on the matched text (unmatched -> the
element is a miss, CER=1.0).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX_DIR = HERE / "fixtures"
RAW_DIR = PROJECT / "artifacts" / "raw"

HOME = str(Path.home())
TMP = os.environ.get("TMPDIR", "").rstrip("/")

COLLAPSE_CER = 0.30  # CER at/above which a sweep step is "collapsed"
CLEAN_CER = 0.05  # CER at/below which a step is "clean"
IOU_MATCH = 0.30  # IoU at/above which a recognized box matches a GT element
WS = re.compile(r"\s+")


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


def norm(s: str) -> str:
    return WS.sub(" ", (s or "").strip())


def edit_distance(a: list, b: list) -> int:
    """Levenshtein over sequences (list of chars or list of words)."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def _box_geom(box):
    xs = [p[0] for p in box["bbox"]]
    ys = [p[1] for p in box["bbox"]]
    return {"x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
            "yc": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys)}


def join_boxes(boxes: list) -> str:
    """LINE-AWARE reading-order join: group boxes into visual lines by vertical overlap,
    order lines top-to-bottom and boxes within a line left-to-right, single-space join.

    (A naive y-center-then-x sort scrambles a single visual line when the detector splits it
    into boxes with a few-px y-center jitter — e.g. a digit run detected separately from the
    words. Grouping by y-overlap first fixes that; this is a harness reading-order concern,
    not OCR fidelity.)
    """
    if not boxes:
        return ""
    gs = [(_box_geom(b), b["text"]) for b in boxes]
    gs.sort(key=lambda t: t[0]["yc"])
    lines = []  # each: {"y0","y1","items":[(x0,text)]}
    for g, txt in gs:
        placed = False
        for ln in lines:
            overlap = min(ln["y1"], g["y1"]) - max(ln["y0"], g["y0"])
            smaller_h = max(1.0, min(ln["y1"] - ln["y0"], g["h"]))
            if overlap > 0.5 * smaller_h:  # same visual line
                ln["items"].append((g["x0"], txt))
                ln["y0"] = min(ln["y0"], g["y0"])
                ln["y1"] = max(ln["y1"], g["y1"])
                placed = True
                break
        if not placed:
            lines.append({"y0": g["y0"], "y1": g["y1"], "items": [(g["x0"], txt)]})
    lines.sort(key=lambda ln: ln["y0"])
    parts = []
    for ln in lines:
        ln["items"].sort(key=lambda it: it[0])
        parts.extend(t for _, t in ln["items"])
    return norm(" ".join(parts))


def cer_wer(pred: str, gt: str) -> dict:
    pred, gt = norm(pred), norm(gt)
    gch, pch = list(gt), list(pred)
    gw, pw = gt.split(), pred.split()
    cer = edit_distance(pch, gch) / len(gch) if gch else (0.0 if not pch else 1.0)
    wer = edit_distance(pw, gw) / len(gw) if gw else (0.0 if not pw else 1.0)
    # case-insensitive CER (the dominant clean-text error is a case-flip, reported so the
    # reader can separate case fidelity from character loss)
    gci, pci = list(gt.lower()), list(pred.lower())
    cer_ci = edit_distance(pci, gci) / len(gci) if gci else (0.0 if not pci else 1.0)
    return {
        "pred": pred,
        "gt_len_chars": len(gch),
        "cer": round(cer, 4),
        "cer_ci": round(cer_ci, 4),
        "wer": round(wer, 4),
        "exact": pred == gt,
        "exact_ci": pred.lower() == gt.lower(),
    }


def aabb(box) -> tuple:
    xs = [p[0] for p in box["bbox"]]
    ys = [p[1] for p in box["bbox"]]
    return (min(xs), min(ys), max(xs), max(ys))


def iou(a: tuple, b: tuple) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / ua if ua > 0 else 0.0


def sweep_boundary(steps: list, value_key: str) -> dict:
    """steps: list of {value, cer} in sweep order. Returns clean/collapsed classification +
    the derived first-collapse value (None if never collapses)."""
    first_collapse = None
    for s in steps:
        if s["cer"] >= COLLAPSE_CER and first_collapse is None:
            first_collapse = s[value_key]
    clean_vals = [s[value_key] for s in steps if s["cer"] <= CLEAN_CER]
    collapsed_vals = [s[value_key] for s in steps if s["cer"] >= COLLAPSE_CER]
    return {
        "first_collapse_value": first_collapse,
        "clean_values": clean_vals,
        "collapsed_values": collapsed_vals,
        "collapse_cer_threshold": COLLAPSE_CER,
        "clean_cer_threshold": CLEAN_CER,
    }


def main() -> int:
    gt = json.loads((FIX_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    raw = json.loads((RAW_DIR / "easyocr_raw.json").read_text(encoding="utf-8"))

    per_fixture = {}
    for fid, spec in gt["single_line"].items():
        r = raw["single_line"][fid]
        gt_text = spec["gt_text"]
        entry = {"kind": spec["kind"], "params": spec["params"]}
        entry["default"] = {
            **cer_wer(join_boxes(r["default"]["boxes"]), gt_text),
            "n_boxes": r["default"]["n_boxes"],
            "latency_s": r["default"]["latency_s"],
        }
        for variant in ("adjust_contrast_hi", "prebrighten", "rotation_info"):
            if variant in r:
                entry[variant] = {
                    **cer_wer(join_boxes(r[variant]["boxes"]), gt_text),
                    "n_boxes": r[variant]["n_boxes"],
                    "latency_s": r[variant]["latency_s"],
                }
        per_fixture[fid] = entry

    # ---- H1: font floor ----
    font_rows = [
        {"font": per_fixture[f]["params"]["font"], "cer": per_fixture[f]["default"]["cer"],
         "cer_ci": per_fixture[f]["default"]["cer_ci"], "wer": per_fixture[f]["default"]["wer"],
         "exact": per_fixture[f]["default"]["exact"], "exact_ci": per_fixture[f]["default"]["exact_ci"]}
        for f in per_fixture if per_fixture[f]["kind"] == "font"
    ]
    font_cers = [r["cer"] for r in font_rows]
    font_cers_ci = [r["cer_ci"] for r in font_rows]
    h1 = {
        "per_font": font_rows,
        "perfect_fonts_case_sensitive": [r["font"] for r in font_rows if r["cer"] == 0.0],
        "perfect_fonts_case_insensitive": [r["font"] for r in font_rows if r["cer_ci"] == 0.0],
        "mean_cer": round(sum(font_cers) / len(font_cers), 4) if font_cers else None,
        "mean_cer_ci": round(sum(font_cers_ci) / len(font_cers_ci), 4) if font_cers_ci else None,
        "max_cer": max(font_cers) if font_cers else None,
        "note": "residual clean-text CER is dominated by a case-flip (vow->VOW) and punctuation; case-insensitive CER isolates character loss",
    }

    # ---- H2: size sweep ----
    size_steps = sorted(
        ({"value": per_fixture[f]["params"]["font_size"], "cer": per_fixture[f]["default"]["cer"],
          "wer": per_fixture[f]["default"]["wer"], "n_boxes": per_fixture[f]["default"]["n_boxes"]}
         for f in per_fixture if per_fixture[f]["kind"] == "size"),
        key=lambda s: s["value"],
    )
    h2_size = {"steps": size_steps, "boundary": sweep_boundary(size_steps, "value")}

    # ---- H2: contrast sweep (order by increasing fg gray = decreasing contrast) ----
    contrast_steps = sorted(
        ({"value": per_fixture[f]["params"]["fg_gray"], "weber": per_fixture[f]["params"]["weber"],
          "michelson": per_fixture[f]["params"]["michelson"], "cer": per_fixture[f]["default"]["cer"],
          "adjust_contrast_hi_cer": per_fixture[f].get("adjust_contrast_hi", {}).get("cer"),
          "prebrighten_cer": per_fixture[f].get("prebrighten", {}).get("cer")}
         for f in per_fixture if per_fixture[f]["kind"] == "contrast"),
        key=lambda s: s["value"],
    )
    h2_contrast = {"steps": contrast_steps, "boundary": sweep_boundary(contrast_steps, "weber")}

    # ---- H2/H4: rotation sweep ----
    rot_steps = sorted(
        ({"value": per_fixture[f]["params"]["angle_deg"], "cer": per_fixture[f]["default"]["cer"],
          "rotation_info_cer": per_fixture[f].get("rotation_info", {}).get("cer")}
         for f in per_fixture if per_fixture[f]["kind"] == "rotation"),
        key=lambda s: s["value"],
    )
    rot_ortho = sorted(
        ({"value": per_fixture[f]["params"]["angle_deg"], "cer": per_fixture[f]["default"]["cer"],
          "rotation_info_cer": per_fixture[f].get("rotation_info", {}).get("cer")}
         for f in per_fixture if per_fixture[f]["kind"] == "rotation_ortho"),
        key=lambda s: s["value"],
    )
    h2_rot = {"small_angle_steps": rot_steps, "orthogonal_steps": rot_ortho,
              "boundary": sweep_boundary(rot_steps, "value")}

    # ---- backgrounds ----
    bg_rows = [
        {"bg_kind": per_fixture[f]["params"]["bg_kind"], "cer": per_fixture[f]["default"]["cer"],
         "wer": per_fixture[f]["default"]["wer"]}
        for f in per_fixture if per_fixture[f]["kind"] == "background"
    ]

    # ---- H5: screenshot per-element ----
    sboxes = raw["screenshot"]["default"]["boxes"]
    rec_aabb = [(aabb(b), b["text"]) for b in sboxes]
    elems = gt["screenshot"]["elements"]
    el_results = []
    matched = 0
    for el in elems:
        gbb = tuple(el["bbox"])
        best_iou, best_txt = 0.0, ""
        for rbb, rtxt in rec_aabb:
            v = iou(gbb, rbb)
            if v > best_iou:
                best_iou, best_txt = v, rtxt
        is_match = best_iou >= IOU_MATCH
        if is_match:
            matched += 1
        cw = cer_wer(best_txt if is_match else "", el["gt_text"])
        el_results.append({
            "id": el["id"], "gt_text": el["gt_text"], "font_size": el["font_size"],
            "note": el.get("note", ""), "matched": is_match, "best_iou": round(best_iou, 3),
            "recognized": best_txt if is_match else None, "cer": cw["cer"], "exact": cw["exact"],
        })
    matched_cers = [e["cer"] for e in el_results if e["matched"]]
    h5 = {
        "n_elements": len(elems),
        "detection_recall": round(matched / len(elems), 4) if elems else None,
        "n_matched": matched,
        "missed_elements": [e["id"] for e in el_results if not e["matched"]],
        "mean_cer_matched": round(sum(matched_cers) / len(matched_cers), 4) if matched_cers else None,
        "exact_matched": sum(1 for e in el_results if e["matched"] and e["exact"]),
        "elements": el_results,
    }

    # ---- resource summary ----
    res = raw["resource"]
    warm = sorted(res["warm_latency_s_samples"])
    n = len(warm)

    def pct(p):
        if n == 0:
            return None
        k = min(n - 1, int(round((p / 100) * (n - 1))))
        return warm[k]

    def median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None

    resource_summary = {
        "model_total_bytes": res["model_footprint"]["total_bytes"],
        "model_total_mib": round(res["model_footprint"]["total_bytes"] / (1024 * 1024), 1),
        "model_files_bytes": res["model_footprint"]["files_bytes"],
        "reader_init_s_cold_model_load": res["reader_init_s_cold_model_load"],
        "warm_latency_p50_s": pct(50),
        "warm_latency_p25_s": pct(25),
        "warm_latency_p75_s": pct(75),
        "warm_latency_min_s": warm[0] if warm else None,
        "warm_latency_max_s": warm[-1] if warm else None,
        "warm_samples_n": n,
        "detail1_median_s": median(res["detail1_latency_s_reps"]),
        "detail0_median_s": median(res["detail0_latency_s_reps"]),
        "peak_rss_bytes_fresh_process": res["peak_rss_bytes_fresh_process"],
        "peak_rss_mib_fresh_process": round(res["peak_rss_bytes_fresh_process"] / (1024 * 1024), 1)
        if res.get("peak_rss_bytes_fresh_process") else None,
        "determinism_all_identical": res["determinism"]["all_identical"],
        "timing_caveat": res["timing_caveat"],
    }

    out = {
        "tool": "easyocr",
        "meta": raw["meta"],
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "join": "line-aware: boxes grouped into visual lines by vertical bbox overlap, lines top-to-bottom, boxes left-to-right within a line, single-space",
            "normalization": "collapse whitespace, strip, CASE-SENSITIVE",
            "cer": "Levenshtein(chars)/len(gt_chars)",
            "wer": "Levenshtein(words)/len(gt_words)",
            "collapse_cer": COLLAPSE_CER, "clean_cer": CLEAN_CER, "iou_match": IOU_MATCH,
        },
        "H1_font_floor": h1,
        "H2_size_sweep": h2_size,
        "H2_contrast_sweep": h2_contrast,
        "H2_H4_rotation": h2_rot,
        "backgrounds": bg_rows,
        "H5_screenshot": h5,
        "resource": resource_summary,
        "per_fixture": per_fixture,
    }
    (RAW_DIR / "easyocr_metrics.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        "metrics done. "
        f"font floor mean CER={h1['mean_cer']} (ci {h1['mean_cer_ci']}) perfect_ci={h1['perfect_fonts_case_insensitive']}; "
        f"size collapse<{h2_size['boundary']['first_collapse_value']}px; "
        f"contrast first-collapse weber={h2_contrast['boundary']['first_collapse_value']}; "
        f"rot collapse>={h2_rot['boundary']['first_collapse_value']}deg; "
        f"screenshot recall={h5['detection_recall']} missed={h5['missed_elements']}; "
        f"warm p50={resource_summary['warm_latency_p50_s']}s "
        f"rss={resource_summary['peak_rss_mib_fresh_process']}MiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
