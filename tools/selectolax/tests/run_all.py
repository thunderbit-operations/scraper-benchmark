#!/usr/bin/env python3
"""Orchestrate >=3 independent PROCESS runs of each benchmark and aggregate with
cross-run variance (methodology v3 Part 2 item 4).

Each of bench_parse.py / bench_isolate.py / bench_memory_import.py is invoked
N times as a fresh subprocess (--run-id 1..N), each writing
artifacts/raw/runs/<name>.run{K}.json. This script then aggregates the per-run
p50s (and RSS, throughput, etc.) into:

  - median-across-runs (the headline number)
  - min/max across runs
  - cross-run spread as a percentage of the median (the variance report)

and writes the canonical artifacts the research doc cites:
  artifacts/raw/bench_parse.json
  artifacts/raw/bench_parse.csv
  artifacts/raw/bench_isolate.json
  artifacts/raw/bench_memory_import.json

Nothing here re-implements timing; it only runs the single-run scripts in fresh
processes and reduces their outputs. Run count defaults to 3, override with
RUNS_N env or --runs.
"""
import argparse
import csv
import glob
import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(__file__)
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(HERE, "..", "artifacts", "raw")
RUNS_DIR = os.path.join(RAW, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)
PY = sys.executable

SIZES = ["1kb", "10kb", "100kb", "1mb", "10mb"]
PARSERS = ["selectolax_lexbor", "selectolax_modest", "lxml", "parsel", "bs4_lxml", "bs4_htmlparser"]


def spread_pct(values):
    """(max-min)/median * 100, guarding div-by-zero."""
    if not values:
        return None
    med = statistics.median(values)
    if med == 0:
        return 0.0
    return round((max(values) - min(values)) / med * 100.0, 2)


def agg(values):
    """Reduce a list of per-run scalars into a variance block."""
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {
        "median_across_runs": round(statistics.median(values), 4),
        "min_across_runs": round(min(values), 4),
        "max_across_runs": round(max(values), 4),
        "runs": len(values),
        "spread_pct_of_median": spread_pct(values),
        "per_run": [round(v, 4) for v in values],
    }


def clear_runs(prefix):
    for f in glob.glob(os.path.join(RUNS_DIR, f"{prefix}.run*.json")):
        os.remove(f)


def run_n(script, prefix, n):
    clear_runs(prefix)
    child_env = dict(os.environ, PYTHONUNBUFFERED="1")  # stream child stdout to log
    for k in range(1, n + 1):
        print(f"\n===== {script} run {k}/{n} =====", flush=True)
        p = subprocess.run([PY, os.path.join(HERE, script), "--run-id", str(k)], env=child_env)
        if p.returncode != 0:
            raise SystemExit(f"{script} run {k} failed")
    files = sorted(glob.glob(os.path.join(RUNS_DIR, f"{prefix}.run*.json")))
    return [json.load(open(f)) for f in files]


# ---------------- bench_parse aggregation ----------------
def aggregate_parse(runs):
    meta = dict(runs[0]["meta"])
    meta["n_runs"] = len(runs)
    meta.pop("run_id", None)
    out = {"meta": meta, "results": {}}

    for size in SIZES:
        out["results"][size] = {}
        # parity: report reference parity from run 1, and note if any run disagreed
        parity0 = runs[0]["results"][size]["_parity"]
        parity_consistent = all(
            r["results"][size]["_parity"]["matched"] == parity0["matched"] for r in runs)
        out["results"][size]["_parity"] = {
            **parity0,
            "consistent_across_runs": parity_consistent,
        }
        for pname in PARSERS:
            cells = [r["results"][size].get(pname, {}) for r in runs]
            if any(c.get("parity_failed") for c in cells):
                # carry the parity-fail record through
                pf = next(c for c in cells if c.get("parity_failed"))
                out["results"][size][pname] = pf
                continue
            if any("error" in c for c in cells):
                out["results"][size][pname] = next(c for c in cells if "error" in c)
                continue
            p50s = [c.get("p50_ms") for c in cells]
            p90s = [c.get("p90_ms") for c in cells]
            p99s = [c.get("p99_ms") for c in cells if c.get("p99_ms") is not None]
            iters = cells[0].get("iters")
            entry = {
                "iters_per_run": iters,
                "p50_ms": agg(p50s),
                "p90_ms": agg(p90s),
            }
            if p99s and len(p99s) == len(cells):
                entry["p99_ms"] = agg(p99s)
            else:
                entry["p99_ms"] = None
                entry["p99_note"] = cells[0].get("p99_note", "suppressed (n<100)")
            out["results"][size][pname] = entry
    return out


def write_parse_csv(agg_out):
    csvpath = os.path.join(RAW, "bench_parse.csv")
    with open(csvpath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "parser", "iters_per_run", "runs",
                    "p50_median_ms", "p50_min_ms", "p50_max_ms", "p50_spread_pct",
                    "p90_median_ms", "p99_median_ms", "note"])
        for size in SIZES:
            for pname in PARSERS:
                r = agg_out["results"][size].get(pname, {})
                if r.get("parity_failed"):
                    w.writerow([size, pname, "", "", "PARITY_FAIL", "", "", "", "", "",
                                f"Δlinks={r.get('d_links_vs_ref')}"])
                    continue
                if "error" in r:
                    w.writerow([size, pname, "", "", "ERR", "", "", "", "", "", r["error"][:60]])
                    continue
                p50 = r["p50_ms"]
                p90 = r["p90_ms"]
                p99 = r.get("p99_ms")
                w.writerow([
                    size, pname, r.get("iters_per_run"), p50["runs"],
                    p50["median_across_runs"], p50["min_across_runs"],
                    p50["max_across_runs"], p50["spread_pct_of_median"],
                    p90["median_across_runs"] if p90 else "",
                    p99["median_across_runs"] if p99 else "",
                    r.get("p99_note", "")])
    print("written", csvpath)


# ---------------- bench_isolate aggregation ----------------
def aggregate_isolate(runs):
    meta = dict(runs[0]["meta"])
    meta["n_runs"] = len(runs)
    meta.pop("run_id", None)
    out = {"meta": meta, "parse_only": {}, "throughput_100k": {}}

    for size in ["10kb", "100kb", "1mb", "10mb"]:
        out["parse_only"][size] = {}
        for pname in PARSERS:
            cells = [r["parse_only"][size].get(pname, {}) for r in runs]
            p50s = [c.get("p50_ms") for c in cells]
            out["parse_only"][size][pname] = {
                "iters_per_run": cells[0].get("iters"),
                "p50_ms": agg(p50s),
            }
    for pname in ["selectolax_lexbor", "selectolax_modest", "lxml", "parsel", "bs4_lxml"]:
        cells = [r["throughput_100k"].get(pname, {}) for r in runs]
        p50s = [c.get("query_p50_ms") for c in cells]
        nps = [c.get("nodes_per_sec") for c in cells]
        out["throughput_100k"][pname] = {
            "n_nodes": cells[0].get("n_nodes"),
            "query_p50_ms": agg(p50s),
            "nodes_per_sec": agg(nps),
        }
    return out


# ---------------- bench_memory aggregation ----------------
def aggregate_memory(runs):
    meta = dict(runs[0]["meta"])
    meta["n_runs"] = len(runs)
    meta.pop("run_id", None)
    out = {"meta": meta, "memory_rss": {}, "memory_tracemalloc": {}, "import_cold": {}}

    for page in ["page_1mb.html", "page_10mb.html"]:
        out["memory_rss"][page] = {}
        out["memory_tracemalloc"][page] = {}
        for p in PARSERS:
            rss_cells = [r["memory_rss"][page].get(p, {}) for r in runs]
            tm_cells = [r["memory_tracemalloc"][page].get(p, {}) for r in runs]
            rss_vals = [c.get("rss_delta_mb") for c in rss_cells]
            tm_vals = [c.get("tracemalloc_peak_mb") for c in tm_cells]
            out["memory_rss"][page][p] = {
                "rss_delta_mb": agg(rss_vals),
                "counts": rss_cells[0].get("counts"),
            }
            out["memory_tracemalloc"][page][p] = {
                "tracemalloc_peak_mb": agg(tm_vals),
                "counts": tm_cells[0].get("counts"),
            }
    for name in ["selectolax.lexbor", "selectolax.parser", "lxml.html", "bs4", "parsel"]:
        medians = [r["import_cold"][name]["median_ms"] for r in runs]
        out["import_cold"][name] = {"median_ms": agg(medians)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=int(os.environ.get("RUNS_N", "3")))
    ap.add_argument("--only", choices=["parse", "isolate", "memory"], default=None)
    args = ap.parse_args()
    n = args.runs
    print(f"Running each benchmark {n} independent process runs.")

    if args.only in (None, "parse"):
        runs = run_n("bench_parse.py", "bench_parse", n)
        out = aggregate_parse(runs)
        with open(os.path.join(RAW, "bench_parse.json"), "w") as f:
            json.dump(out, f, indent=2)
        write_parse_csv(out)
        print("written", os.path.join(RAW, "bench_parse.json"))

    if args.only in (None, "isolate"):
        runs = run_n("bench_isolate.py", "bench_isolate", n)
        out = aggregate_isolate(runs)
        with open(os.path.join(RAW, "bench_isolate.json"), "w") as f:
            json.dump(out, f, indent=2)
        print("written", os.path.join(RAW, "bench_isolate.json"))

    if args.only in (None, "memory"):
        runs = run_n("bench_memory_import.py", "bench_memory_import", n)
        out = aggregate_memory(runs)
        with open(os.path.join(RAW, "bench_memory_import.json"), "w") as f:
            json.dump(out, f, indent=2)
        print("written", os.path.join(RAW, "bench_memory_import.json"))

    print("\nAll aggregations written.")


if __name__ == "__main__":
    main()
