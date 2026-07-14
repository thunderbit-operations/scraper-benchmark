#!/usr/bin/env python3
"""Warm-conversion timing distribution (>=3 runs) for the CHEAP, sub-second items, so
the [reproduced] tag on the warm-timing claims rests on a spread, not a single run.

Scope (deliberately the fast path only): the 7 synthetic table PDFs, the 3 Office
fixtures, and the 2 in-context A/B PDFs. All are already-cached, warm, seconds-or-less
conversions. The two real arXiv PDFs (~90-135 s each) and the model DOWNLOAD (224 s,
one-shot by nature) are NOT repeated here — they stay [single-observation] in the RM;
repeating them 3x would cost ~10+ minutes for no qualitative change.

Reports per file: n_runs, per-run convert_s, median, min, max, spread_pct
(=(max-min)/median*100). Warm baseline is established by one discarded warm-up
conversion of each file before timing.
"""
import json, os, statistics, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PDF = os.path.join(ROOT, "artifacts", "fixtures", "pdf")
DOCS = os.path.join(ROOT, "artifacts", "fixtures", "docs")

N_RUNS = 3

FILES = [
    ("table_t1_simple_grid", os.path.join(PDF, "table_t1_simple_grid.pdf")),
    ("table_t2_borderless", os.path.join(PDF, "table_t2_borderless.pdf")),
    ("table_t3_colspan_header", os.path.join(PDF, "table_t3_colspan_header.pdf")),
    ("table_t4_rowspan", os.path.join(PDF, "table_t4_rowspan.pdf")),
    ("table_t5_span_borderless", os.path.join(PDF, "table_t5_span_borderless.pdf")),
    ("table_t6_financial_blankcol", os.path.join(PDF, "table_t6_financial_blankcol.pdf")),
    ("table_t7_wide_12col", os.path.join(PDF, "table_t7_wide_12col.pdf")),
    ("table_t1b_grid_in_context", os.path.join(PDF, "table_t1b_grid_in_context.pdf")),
    ("table_t4b_rowspan_in_context", os.path.join(PDF, "table_t4b_rowspan_in_context.pdf")),
    ("report.docx", os.path.join(DOCS, "report.docx")),
    ("workbook.xlsx", os.path.join(DOCS, "workbook.xlsx")),
    ("deck.pptx", os.path.join(DOCS, "deck.pptx")),
]


def main():
    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()

    results = []
    for label, path in FILES:
        conv.convert(path)  # discarded warm-up
        runs = []
        for _ in range(N_RUNS):
            t0 = time.perf_counter()
            conv.convert(path)
            runs.append(round(time.perf_counter() - t0, 4))
        med = statistics.median(runs)
        spread = round((max(runs) - min(runs)) / med * 100, 1) if med else 0.0
        results.append({
            "file": label, "n_runs": N_RUNS, "runs_s": runs,
            "median_s": med, "min_s": min(runs), "max_s": max(runs),
            "spread_pct": spread,
        })
        print(f"{label}: runs={runs} median={med}s spread={spread}%")

    out = {
        "tool": "docling",
        "test": "warm_timing_repeats",
        "note": "warm (cached-model) convert timing over 3 runs; cheap fixtures only",
        "results": results,
    }
    outp = os.path.join(ROOT, "artifacts", "raw", "warm_timing_repeats.json")
    with open(outp, "w") as f:
        json.dump(out, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
