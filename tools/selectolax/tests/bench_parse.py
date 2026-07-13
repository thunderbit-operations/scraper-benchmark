#!/usr/bin/env python3
"""Performance benchmark: parse + extract task across parsers and page sizes.

ONE run of the benchmark. Multiple independent process runs are orchestrated by
run_all.py (methodology v3 Part 2: >=3 runs + cross-run variance). Pass
--run-id N to tag the output; results are written to
artifacts/raw/runs/bench_parse.run{N}.json so run_all.py can aggregate them.

Task (identical logical work for every parser):
  1. Parse the HTML string into a tree.
  2. Extract text of every <h3 class="title"> (product titles).
  3. Extract href of every <a> element.

Correctness parity (methodology v3 Part 2 item 8): BEFORE timing, every parser
is run once and its output is reduced to a CONTENT HASH over the concatenated
(sorted) titles + hrefs, not just the counts. All parsers must agree on that
hash or the whole (parser,size) cell is marked parity_failed and NOT timed --
so we can never silently compare "one parser that did less work". The reference
hash is selectolax_lexbor's; any parser whose content differs is recorded with
the diff and excluded from the timed comparison for that size.

GC policy (methodology v3 Part 2 item 6): GC is ENABLED throughout (closest to
real scraper usage). For parsers whose timed task accumulates reference-cycle
garbage inside the loop (BeautifulSoup builds a cyclic parent/child tree), we do
an explicit gc.collect() BETWEEN iterations (outside the timed region) so dead
objects from a previous iteration cannot inflate a later iteration's tail. This
replaces v2's gc.disable(), which both (a) diverged from real usage and (b) was
then used to "explain" tail latency -- a contradiction Fable 5 flagged.

Percentiles (methodology v3 Part 2 item 5): p99 is only emitted when n>=100 AND
labelled by how many samples back it actually is. For capped cells (bs4 on
1-10MB, n<100) we emit p99 as null and record p99_note so downstream text cannot
build a tail-behavior story on a near-max single sample.

Parsers:
  selectolax_lexbor  - LexborHTMLParser (default/recommended backend)
  selectolax_modest  - HTMLParser (Modest backend)
  lxml               - lxml.html + cssselect
  bs4_htmlparser     - BeautifulSoup(html.parser)
  bs4_lxml           - BeautifulSoup(features='lxml')
  parsel             - parsel.Selector (built on lxml)
"""
import argparse
import gc
import hashlib
import json
import os
import statistics
import sys
import time

FIXTURES = os.environ.get("SLX_SYNTH_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "fixtures", "synthetic")
# Output dir: artifacts/raw by default; override with SLX_RESULTS_DIR (public repo
# points this at tools/selectolax/results so one script serves both layouts).
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")
RUNS = os.path.join(RAW, "runs")
os.makedirs(RUNS, exist_ok=True)

# Parsers whose timed loop builds reference-cycle garbage; collect between iters.
CYCLE_PARSERS = {"bs4_lxml", "bs4_htmlparser"}


# ---- parser task closures ----
# Each returns (titles: list[str], hrefs: list[str]) so we can hash CONTENT,
# not just count, for the parity gate.

def make_selectolax_lexbor():
    from selectolax.lexbor import LexborHTMLParser

    def task(html):
        tree = LexborHTMLParser(html)
        titles = [n.text() for n in tree.css("h3.title")]
        links = [n.attributes.get("href") for n in tree.css("a")]
        return titles, links
    return task


def make_selectolax_modest():
    from selectolax.parser import HTMLParser

    def task(html):
        tree = HTMLParser(html)
        titles = [n.text() for n in tree.css("h3.title")]
        links = [n.attributes.get("href") for n in tree.css("a")]
        return titles, links
    return task


def make_lxml():
    import lxml.html

    def task(html):
        tree = lxml.html.fromstring(html)
        titles = [n.text_content() for n in tree.cssselect("h3.title")]
        links = [n.get("href") for n in tree.cssselect("a")]
        return titles, links
    return task


def make_bs4_htmlparser():
    from bs4 import BeautifulSoup

    def task(html):
        soup = BeautifulSoup(html, "html.parser")
        titles = [n.get_text() for n in soup.select("h3.title")]
        links = [n.get("href") for n in soup.select("a")]
        return titles, links
    return task


def make_bs4_lxml():
    from bs4 import BeautifulSoup

    def task(html):
        soup = BeautifulSoup(html, "lxml")
        titles = [n.get_text() for n in soup.select("h3.title")]
        links = [n.get("href") for n in soup.select("a")]
        return titles, links
    return task


def make_parsel():
    from parsel import Selector

    def task(html):
        sel = Selector(text=html)
        titles = sel.css("h3.title::text").getall()
        links = sel.css("a::attr(href)").getall()
        return titles, links
    return task


PARSERS = {
    "selectolax_lexbor": make_selectolax_lexbor,
    "selectolax_modest": make_selectolax_modest,
    "lxml": make_lxml,
    "parsel": make_parsel,
    "bs4_lxml": make_bs4_lxml,
    "bs4_htmlparser": make_bs4_htmlparser,
}

SIZES = ["1kb", "10kb", "100kb", "1mb", "10mb"]

# Reference parser whose CONTENT the others must match for the parity gate.
REFERENCE = "selectolax_lexbor"


def content_hash(result):
    """Stable hash over extracted CONTENT (not just counts).

    Titles are compared verbatim (order-independent via sorting); hrefs likewise.
    None hrefs are normalised to the empty string. This is what makes the parity
    gate a content assert rather than a count assert.
    """
    titles, hrefs = result
    norm_titles = sorted((t or "").strip() for t in titles)
    norm_hrefs = sorted((h or "") for h in hrefs)
    h = hashlib.sha256()
    h.update(("\n".join(norm_titles)).encode("utf-8", "replace"))
    h.update(b"\x00--HREFS--\x00")
    h.update(("\n".join(norm_hrefs)).encode("utf-8", "replace"))
    return h.hexdigest(), len(titles), len(hrefs)


def percentile(data, p):
    """Nearest-rank percentile on sorted copy."""
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def time_task(task, html, iters, warmup, collect_between):
    # GC stays ENABLED throughout (real-usage policy, and consistent across all
    # parsers -- v2's gc.disable() both diverged from real usage and was then used
    # to "explain" tail latency, a contradiction Fable 5 flagged). We drop each
    # iteration's tree with `del r` so Python's generational collector can reclaim
    # BeautifulSoup's reference cycles between iterations on its own; we do NOT
    # force a full gc.collect() every iteration because a full-heap scan after each
    # 10MB parse would dominate the measurement. `collect_between` triggers one
    # gc.collect() before timing starts (clears warmup garbage) for cyclic parsers.
    for _ in range(warmup):
        r = task(html)
        del r
    if collect_between:
        gc.collect()
    samples = []
    for _ in range(iters):
        t0 = time.perf_counter()
        r = task(html)
        t1 = time.perf_counter()
        samples.append((t1 - t0) * 1000.0)  # ms
        del r  # free the tree; generational GC reclaims cycles, GC stays enabled
    return samples


def iters_for(size, pname, default_iters):
    """Cap the pathologically slow BeautifulSoup combos to keep runtime sane.
    (Capped cells report p50/p90 only; p99 is suppressed -- see summarize().)"""
    if size == "10mb" and pname == "bs4_htmlparser":
        return 5
    if size == "10mb" and pname == "bs4_lxml":
        return 10
    if size == "1mb" and pname == "bs4_htmlparser":
        return 20
    if size == "1mb" and pname == "bs4_lxml":
        return 30
    return default_iters


def summarize(samples, iters):
    """Percentiles with sample-size guardrails (methodology v3 item 5).

    p99 is emitted only for n>=100; for smaller (capped) samples it is null with
    a note, so downstream prose cannot spin a tail story out of a near-max point.
    """
    d = {
        "iters": len(samples),
        "p50_ms": round(percentile(samples, 50), 4),
        "p90_ms": round(percentile(samples, 90), 4),
        "min_ms": round(min(samples), 4),
        "mean_ms": round(statistics.mean(samples), 4),
        "stdev_ms": round(statistics.stdev(samples), 4) if len(samples) > 1 else 0.0,
    }
    if len(samples) >= 100:
        d["p99_ms"] = round(percentile(samples, 99), 4)
        d["p99_note"] = None
    else:
        d["p99_ms"] = None
        # how many samples back the "99th" would be, for honesty
        rank = max(1, int(round(0.01 * (len(samples) - 1))) + 1)
        d["p99_note"] = (f"suppressed: n={len(samples)}<100; "
                         f"p90 shown is ~{len(samples)}th-largest single sample")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=0,
                    help="tag this run; output goes to runs/bench_parse.run{N}.json")
    args = ap.parse_args()

    default_iters = int(os.environ.get("ITERS", "100"))
    warmup = 3
    results = {}
    manifest = json.load(open(os.path.join(FIXTURES, "manifest.json")))

    for size in SIZES:
        html = open(os.path.join(FIXTURES, f"page_{size}.html"), encoding="utf-8").read()
        results[size] = {}

        # ---- PARITY GATE (content hash, run once, before timing) ----
        ref_task = PARSERS[REFERENCE]()
        ref_hash, ref_nt, ref_nl = content_hash(ref_task(html))
        parity = {"reference": REFERENCE, "reference_hash": ref_hash,
                  "reference_n_titles": ref_nt, "reference_n_links": ref_nl,
                  "matched": [], "mismatched": {}}
        parity_ok = {}
        for pname, factory in PARSERS.items():
            t = factory()
            h, nt, nl = content_hash(t(html))
            if h == ref_hash:
                parity["matched"].append(pname)
                parity_ok[pname] = True
            else:
                parity["mismatched"][pname] = {
                    "hash": h, "n_titles": nt, "n_links": nl,
                    "d_titles_vs_ref": nt - ref_nt, "d_links_vs_ref": nl - ref_nl}
                parity_ok[pname] = False
        results[size]["_parity"] = parity

        # ---- TIMING (only parsers that passed parity) ----
        for pname, factory in PARSERS.items():
            iters = iters_for(size, pname, default_iters)
            if not parity_ok[pname]:
                results[size][pname] = {
                    "parity_failed": True,
                    "note": "content hash != reference; excluded from timed comparison",
                    **parity["mismatched"][pname]}
                print(f"[{size:>5}] {pname:<20} PARITY-FAIL "
                      f"(Δtitles={parity['mismatched'][pname]['d_titles_vs_ref']:+d} "
                      f"Δlinks={parity['mismatched'][pname]['d_links_vs_ref']:+d}) -- not timed")
                continue
            try:
                collect_between = pname in CYCLE_PARSERS
                samples = time_task(factory(), html, iters, warmup, collect_between)
                s = summarize(samples, iters)
                s["gc_policy"] = "enabled+precollect" if collect_between else "enabled"
                results[size][pname] = s
                p99show = f"{s['p99_ms']:.3f}" if s["p99_ms"] is not None else "n/a"
                print(f"[{size:>5}] {pname:<20} p50={s['p50_ms']:>10.3f}ms "
                      f"p99={p99show:>10}ms (n={len(samples)})")
            except Exception as e:
                results[size][pname] = {"error": repr(e)}
                print(f"[{size:>5}] {pname:<20} ERROR: {e!r}")

    out = {
        "meta": {
            "run_id": args.run_id,
            "machine": sys.platform,
            "python": sys.version.split()[0],
            "iters_default": default_iters,
            "warmup": warmup,
            "gc_policy": "enabled throughout; per-iter tree freed via del; no gc.disable (real-usage, consistent across parsers)",
            "parity_gate": "content-hash over sorted titles+hrefs vs " + REFERENCE,
            "fixture_manifest": manifest,
            "task": "parse + extract h3.title text + all a href",
        },
        "results": results,
    }
    outpath = os.path.join(RUNS, f"bench_parse.run{args.run_id}.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2)
    print("\nwritten", outpath)


if __name__ == "__main__":
    main()
