#!/usr/bin/env python3
"""Isolate parse-only cost vs. query cost, and throughput on the 100k-node page.

ONE run; orchestrated >=3x by run_all.py for cross-run variance.
Pass --run-id N -> runs/bench_isolate.run{N}.json.

Two experiments:
  A) PARSE-ONLY: time just constructing the tree (no CSS query). This is the
     closest analogue to the README's "parse top-domains" benchmark and is the
     evidence for the (counter-consensus) finding that lxml's PARSE step is
     faster than selectolax-Lexbor's. Because that finding is the pack's most
     attackable claim, this measures it directly and in isolation.
  B) THROUGHPUT: on the 100k-node wide page, time selecting all 100k <a> and
     reading their href. Reports nodes/sec.

GC stays enabled (real-usage policy, consistent with bench_parse.py). bs4 builds
cyclic trees; each iteration's tree is dropped with `del r` so the generational
collector reclaims them, and for cyclic parsers we run ONE gc.collect() before
the timed loop (not between every iteration -- a per-iteration full-heap scan
would dominate timing). p99 suppressed for capped (n<100) cells.
"""
import argparse
import gc
import json
import os
import statistics
import sys
import time

FIX = os.environ.get("SLX_SYNTH_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "fixtures", "synthetic")
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")
RUNS = os.path.join(RAW, "runs")
os.makedirs(RUNS, exist_ok=True)

CYCLE_PARSERS = {"bs4_lxml", "bs4_htmlparser"}


def pct(data, p):
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def timeit(fn, iters, collect_between, warmup=3):
    # GC enabled throughout; per-iteration tree freed via `del r` so the
    # generational collector reclaims bs4 cycles on its own. No forced full
    # gc.collect() per iteration (a full-heap scan after each 10MB parse would
    # dominate timing). One pre-timing collect for cyclic parsers clears warmup.
    for _ in range(warmup):
        r = fn()
        del r
    if collect_between:
        gc.collect()
    xs = []
    for _ in range(iters):
        t0 = time.perf_counter()
        r = fn()
        xs.append((time.perf_counter() - t0) * 1000)
        del r
    return xs


def summarize(xs):
    d = {
        "iters": len(xs),
        "p50_ms": round(pct(xs, 50), 4),
        "p90_ms": round(pct(xs, 90), 4),
        "min_ms": round(min(xs), 4),
        "mean_ms": round(statistics.mean(xs), 4),
        "stdev_ms": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0,
    }
    if len(xs) >= 100:
        d["p99_ms"] = round(pct(xs, 99), 4)
    else:
        d["p99_ms"] = None
        d["p99_note"] = f"suppressed: n={len(xs)}<100"
    return d


# ---- parse-only closures ----
def parse_closures():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser
    import lxml.html
    from bs4 import BeautifulSoup
    from parsel import Selector
    return {
        "selectolax_lexbor": lambda h: LexborHTMLParser(h),
        "selectolax_modest": lambda h: HTMLParser(h),
        "lxml": lambda h: lxml.html.fromstring(h),
        "parsel": lambda h: Selector(text=h),
        "bs4_lxml": lambda h: BeautifulSoup(h, "lxml"),
        "bs4_htmlparser": lambda h: BeautifulSoup(h, "html.parser"),
    }


def query_closures():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser
    import lxml.html
    from bs4 import BeautifulSoup
    from parsel import Selector
    return {
        "selectolax_lexbor": (lambda h: LexborHTMLParser(h),
                              lambda t: [n.attributes.get("href") for n in t.css("a")]),
        "selectolax_modest": (lambda h: HTMLParser(h),
                              lambda t: [n.attributes.get("href") for n in t.css("a")]),
        "lxml": (lambda h: lxml.html.fromstring(h),
                 lambda t: [n.get("href") for n in t.cssselect("a")]),
        "parsel": (lambda h: Selector(text=h),
                   lambda t: t.css("a::attr(href)").getall()),
        "bs4_lxml": (lambda h: BeautifulSoup(h, "lxml"),
                     lambda t: [n.get("href") for n in t.select("a")]),
    }


def iters_for(size, name, default):
    if size == "10mb" and name == "bs4_htmlparser":
        return 5
    if size == "10mb" and name == "bs4_lxml":
        return 10
    if size == "1mb" and name == "bs4_htmlparser":
        return 20
    if size == "1mb" and name == "bs4_lxml":
        return 30
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=0)
    args = ap.parse_args()

    out = {"meta": {"run_id": args.run_id, "python": sys.version.split()[0],
                    "gc_policy": "enabled throughout; per-iter tree freed via del; no gc.disable"},
           "parse_only": {}, "throughput_100k": {}}
    ITERS = int(os.environ.get("ITERS", "100"))

    # A) parse-only across sizes
    pc = parse_closures()
    for size in ["10kb", "100kb", "1mb", "10mb"]:
        html = open(os.path.join(FIX, f"page_{size}.html")).read()
        out["parse_only"][size] = {}
        for name, fn in pc.items():
            iters = iters_for(size, name, ITERS)
            collect_between = name in CYCLE_PARSERS
            xs = timeit(lambda: fn(html), iters, collect_between)
            out["parse_only"][size][name] = summarize(xs)
            print(f"[PARSE {size:>5}] {name:<20} p50={pct(xs,50):>9.3f}ms (n={iters})")

    # B) throughput on 100k-node page: query all <a>
    wide = open(os.path.join(FIX, "wide_100k_nodes.html")).read()
    qc = query_closures()
    for name, (build, run) in qc.items():
        tree = build(wide)  # build once, reuse
        collect_between = name in CYCLE_PARSERS
        xs = timeit(lambda: run(tree), 30, collect_between)
        p50 = pct(xs, 50)
        n_nodes = len(run(tree))
        nps = n_nodes / (p50 / 1000.0) if p50 > 0 else 0
        out["throughput_100k"][name] = {
            "query_p50_ms": round(p50, 4), "n_nodes": n_nodes,
            "nodes_per_sec": int(nps), "iters": len(xs),
            "stdev_ms": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0}
        print(f"[QUERY-100k] {name:<20} p50={p50:>9.3f}ms  {n_nodes} nodes  {int(nps):,} nodes/sec")

    outpath = os.path.join(RUNS, f"bench_isolate.run{args.run_id}.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2)
    print("\nwritten", outpath)


if __name__ == "__main__":
    main()
