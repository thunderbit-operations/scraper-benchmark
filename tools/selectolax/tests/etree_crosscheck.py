#!/usr/bin/env python3
"""FINDING-03 cross-check: is "lxml parses faster than selectolax-Lexbor" an
artifact of the specific lxml API (`lxml.html.fromstring`), or does the lower-level
`lxml.etree` HTMLParser show the same direction?

FINDING-03 (parse-only, this machine) reports lxml's tree construction is faster
than selectolax-Lexbor's. Because that reverses most published benchmarks, this
script re-times parse-only with TWO separate lxml entry points and selectolax
for reference, so the claim rests on committed data, not an unverified sentence:

  1. lxml.html.fromstring        (the high-level API used in bench_isolate.py)
  2. lxml.etree.fromstring + HTMLParser   (the lower-level etree API)
  3. selectolax LexborHTMLParser (reference)

If both lxml APIs land within a small margin of each other and both beat
selectolax-Lexbor, an "lxml-API artifact" is ruled out. Output ->
results/etree_crosscheck.json. Single platform (macOS arm64 / Python 3.14); run
it on yours.
"""
import json
import os
import statistics
import sys
import time

FIX = os.environ.get("SLX_SYNTH_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "fixtures", "synthetic")
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)


def pct(data, p):
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def timeit(fn, iters=50, warmup=3):
    for _ in range(warmup):
        del_ = fn()
        del del_
    xs = []
    for _ in range(iters):
        t0 = time.perf_counter()
        r = fn()
        xs.append((time.perf_counter() - t0) * 1000)
        del r
    return {"iters": len(xs), "p50_ms": round(pct(xs, 50), 4),
            "p90_ms": round(pct(xs, 90), 4), "min_ms": round(min(xs), 4),
            "mean_ms": round(statistics.mean(xs), 4)}


def build_fns(html_bytes, html_str):
    import lxml.html
    import lxml.etree as ET
    from selectolax.lexbor import LexborHTMLParser
    hp = ET.HTMLParser()
    return {
        "lxml_html_fromstring": lambda: lxml.html.fromstring(html_str),
        "lxml_etree_HTMLParser": lambda: ET.fromstring(html_bytes, hp),
        "selectolax_lexbor": lambda: LexborHTMLParser(html_str),
    }


def main():
    sizes = ["100kb", "1mb", "10mb"]
    out = {"meta": {"python": sys.version.split()[0], "platform": sys.platform,
                    "task": "parse-only tree construction, two lxml APIs vs selectolax-Lexbor",
                    "note": "ratio_vs_lexbor > 1 means that engine is SLOWER than lxml.html"},
           "results": {}}
    for size in sizes:
        html_str = open(os.path.join(FIX, f"page_{size}.html")).read()
        html_bytes = html_str.encode("utf-8")
        fns = build_fns(html_bytes, html_str)
        cell = {name: timeit(fn) for name, fn in fns.items()}
        base = cell["lxml_html_fromstring"]["p50_ms"]
        for name in cell:
            cell[name]["ratio_vs_lxml_html"] = round(cell[name]["p50_ms"] / base, 3) if base else None
        # cross-check verdicts computed from the data (no hardcoded conclusions)
        h1 = cell["lxml_html_fromstring"]["p50_ms"]
        h2 = cell["lxml_etree_HTMLParser"]["p50_ms"]
        lx = cell["selectolax_lexbor"]["p50_ms"]
        api_margin_pp = round(abs(h1 - h2) / min(h1, h2) * 100, 2)
        cell["_crosscheck"] = {
            "both_lxml_apis_beat_selectolax_lexbor": bool(h1 < lx and h2 < lx),
            "two_api_margin_pct": api_margin_pp,
            "lexbor_slower_than_lxml_html_by_pct": round((lx - h1) / h1 * 100, 1),
        }
        out["results"][size] = cell
        print(f"[{size}] lxml.html={h1}ms  lxml.etree={h2}ms  lexbor={lx}ms  "
              f"| both lxml < lexbor: {cell['_crosscheck']['both_lxml_apis_beat_selectolax_lexbor']}  "
              f"two-API margin {api_margin_pp}pp")

    path = os.path.join(RAW, "etree_crosscheck.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("written", path)


if __name__ == "__main__":
    main()
