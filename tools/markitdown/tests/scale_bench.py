#!/usr/bin/env python3
"""
Scale / stress benchmark for MarkItDown, run in its OWN process so the
high-water memory (ru_maxrss) is not contaminated by any prior heavy stage.

Subjects (each timed over N runs, distribution reported):
  - large PDF: NIST SP 800-53r5, 492 pages, ~6 MB   (PDF scale)
  - large XLSX: 50,000 rows x 8 cols                 (spreadsheet scale)
  - wide XLSX: 200 rows x 64 cols                    (spreadsheet width)
  - arXiv PDF: 15 pages, real tables                 (mid PDF baseline)

Memory: peak RSS via resource.getrusage(RUSAGE_SELF).ru_maxrss, sampled as the
delta from a baseline captured right before the FIRST convert of each subject.
Because subjects run in one process sequentially, ru_maxrss is monotonic, so we
report the *incremental* peak (max_rss_after - max_rss_before) which is only a
valid lower bound for later subjects; the PDF (first, heaviest) gets the clean
reading. A note is emitted for subjects after the peak-setter.  Timings are
independent of this and always valid.

For a clean per-subject peak, pass a subject name as argv[1] and the caller runs
one subprocess per subject (run_scale.sh does this).
"""
import json
import os
import resource
import sys
import time

from markitdown import MarkItDown

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))


def _pick(*candidates):
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


# Works in both the research pack and the clean public repo layout.
DOCS = _pick(os.path.join(BASE, "artifacts", "fixtures", "docs"),
             os.path.join(BASE, "fixtures", "docs"))
RAW = _pick(os.path.join(BASE, "artifacts", "raw"), os.path.join(BASE, "results"))

# macOS ru_maxrss is bytes; Linux is kilobytes. Detect by platform.
RSS_UNIT = 1 if sys.platform == "darwin" else 1024  # -> bytes


def maxrss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * RSS_UNIT / (1024 * 1024)


SUBJECTS = {
    "pdf_nist_492p": ("large_report_nist.pdf", 3),
    "xlsx_50k": ("large_sheet.xlsx", 3),
    "xlsx_wide64": ("wide_sheet.xlsx", 5),
    "pdf_arxiv": ("arxiv_1706.03762.pdf", 3),
}


def bench_one(md_engine, name, fn, iters):
    p = os.path.join(DOCS, fn)
    if not os.path.exists(p):
        return {"subject": name, "error": f"missing {p}"}
    rss_before = maxrss_mb()
    # content-producing first run
    t0 = time.perf_counter()
    res = md_engine.convert(p)
    first_ms = (time.perf_counter() - t0) * 1000.0
    text = res.text_content
    rss_after_first = maxrss_mb()
    timings = [first_ms]
    for _ in range(iters - 1):
        t0 = time.perf_counter()
        md_engine.convert(p)
        timings.append((time.perf_counter() - t0) * 1000.0)
    st = sorted(timings)
    return {
        "subject": name,
        "input_bytes": os.path.getsize(p),
        "output_chars": len(text),
        "n_runs": len(timings),
        "timings_ms": [round(t, 1) for t in timings],
        "t_ms_min": round(st[0], 1),
        "t_ms_median": round(st[len(st) // 2], 1),
        "t_ms_max": round(st[-1], 1),
        "rss_mb_before": round(rss_before, 1),
        "rss_mb_after_first_convert": round(rss_after_first, 1),
        "rss_mb_peak_delta_firstconvert": round(rss_after_first - rss_before, 1),
        "crashed": False,
    }


def main():
    md_engine = MarkItDown(enable_plugins=False)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    results = []
    baseline = maxrss_mb()
    for name, (fn, iters) in SUBJECTS.items():
        if only and name != only:
            continue
        try:
            r = bench_one(md_engine, name, fn, iters)
        except Exception as e:
            r = {"subject": name, "crashed": True, "error": f"{type(e).__name__}: {e}"}
        r["process_baseline_rss_mb"] = round(baseline, 1)
        results.append(r)
        print(json.dumps(r))
    tag = only or "all"
    outp = os.path.join(RAW, f"scale_bench_{tag}.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump({"python": sys.version.split()[0], "results": results}, f, indent=2)
    print(f"wrote {outp}")


if __name__ == "__main__":
    main()
