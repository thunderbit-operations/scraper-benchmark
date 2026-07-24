#!/usr/bin/env python3
"""resource_cost.py — partition wall-time + peak RSS per carrier format, each measured in
an ISOLATED subprocess (methodology Part 2 §6: RSS must not be cross-contaminated by a
prior format's load). For each format it runs the d7_large fixture N times:
  - cold (rep 0): includes the one-time spaCy/NLTK model + library load in that process
  - warm p50 (reps 1..N-1): steady-state partition time, median + [min,max] interval
  - peak RSS: resource.getrusage(RUSAGE_SELF).ru_maxrss after the runs (per-process peak)

Timing caveat (recorded, honest): this host may run sibling evaluation workers in
parallel, so wall-time can be contaminated. We therefore report the WARM MEDIAN + full
interval, run each format in its own process, and treat RSS (a high-water mark) as the
more stable signal. No timing number supports a "faster/slower" verdict here — the arm
exists to size the model-load and per-format cost, not to race the formats.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
        return s
    if isinstance(o, list):
        return [redact(x) for x in o]
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items()}
    return o


WORKER = r'''
import json, sys, time, resource
fmt = sys.argv[1]; path = sys.argv[2]; reps = int(sys.argv[3])
if fmt == "html":
    from unstructured.partition.html import partition_html as P
elif fmt == "md":
    from unstructured.partition.md import partition_md as P
elif fmt == "txt":
    from unstructured.partition.text import partition_text as P
elif fmt == "docx":
    from unstructured.partition.docx import partition_docx as P
else:
    raise SystemExit("bad fmt")
times = []
n_elements = None
for i in range(reps):
    t0 = time.perf_counter()
    els = P(filename=path)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1000.0)
    n_elements = len(els)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS, KB on Linux
print(json.dumps({"format": fmt, "elapsed_ms": times, "n_elements": n_elements,
                  "ru_maxrss_raw": peak, "platform": sys.platform}))
'''


def p50(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def main() -> int:
    reps = 6
    fixture = FIX / "d7_large"
    results = {}
    for fmt in ("html", "md", "txt", "docx"):
        path = fixture.with_suffix(f".{fmt}")
        if not path.exists():
            results[fmt] = {"error": "missing"}
            continue
        proc = subprocess.run(
            [sys.executable, "-c", WORKER, fmt, str(path), str(reps)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            results[fmt] = {"error": proc.stderr[-400:]}
            continue
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        times = data["elapsed_ms"]
        cold = times[0]
        warm = times[1:] if len(times) > 1 else times
        # macOS ru_maxrss is bytes; Linux is kilobytes
        raw = data["ru_maxrss_raw"]
        peak_mb = raw / (1024 * 1024) if data["platform"] == "darwin" else raw / 1024
        results[fmt] = {
            "n_elements": data["n_elements"],
            "reps": reps,
            "cold_first_call_ms": round(cold, 2),
            "warm_p50_ms": round(p50(warm), 2),
            "warm_min_ms": round(min(warm), 2),
            "warm_max_ms": round(max(warm), 2),
            "peak_rss_mb": round(peak_mb, 1),
            "ru_maxrss_raw": raw,
            "platform": data["platform"],
        }

    out = {
        "tool": "unstructured",
        "fixture": "d7_large (canonical x60, 660 elements)",
        "isolation": "one subprocess per format (RSS not cross-contaminated)",
        "timing_caveat": (
            "warm median + interval only; sibling workers may contaminate wall time; "
            "no faster/slower verdict is drawn from these numbers"
        ),
        "results": results,
    }
    (RAW / "resource_cost.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("=== resource cost per format (d7_large, isolated subprocess, 6 reps) ===")
    for fmt, r in results.items():
        if "error" in r:
            print(f"  {fmt:5s} ERROR {r['error'][:80]}")
            continue
        print(f"  {fmt:5s} cold={r['cold_first_call_ms']}ms warm_p50={r['warm_p50_ms']}ms "
              f"[{r['warm_min_ms']},{r['warm_max_ms']}] peakRSS={r['peak_rss_mb']}MB "
              f"({r['n_elements']} els)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
