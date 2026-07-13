#!/usr/bin/env python3
"""Peak memory per parser (RSS and tracemalloc measured in SEPARATE processes),
plus cold-import timing.

Methodology v3 Part 2 item 6 (instrument separation): tracemalloc's per-block
bookkeeping inflates process RSS in proportion to the NUMBER of Python
allocations -- which penalises exactly the parsers that allocate the most Python
objects (BeautifulSoup, and the Lexbor binding). v2 measured RSS delta WHILE
tracemalloc was running, so the RSS ranking was contaminated by the very
instrument whose distortion the pack set out to warn about. v3 fixes this:

  mode=rss         : tracemalloc is NEVER started. Only resource.getrusage RSS
                     delta is measured. This is the clean process-memory number.
  mode=tracemalloc : ONLY tracemalloc peak is measured (no RSS claim). This is
                     kept purely to demonstrate how badly tracemalloc mis-ranks
                     C-backed parsers -- it is a methodology exhibit, not a
                     memory verdict.

Each (parser, page, mode) runs in its own fresh subprocess so nothing
cross-contaminates. Import cold-start is timed in fresh `python -c` processes.

Multiple runs orchestrated by run_all.py. --run-id N -> runs/bench_memory_import.run{N}.json
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(HERE, "..", "artifacts", "raw")
RUNS = os.path.join(RAW, "runs")
FIX = os.environ.get("SLX_SYNTH_DIR") or os.path.join(HERE, "..", "artifacts", "fixtures", "synthetic")
os.makedirs(RUNS, exist_ok=True)

PY = sys.executable

# ---------- memory child program ----------
# Runs in mode 'rss' (tracemalloc OFF) or 'tracemalloc' (RSS not reported).
MEM_CHILD = r'''
import sys, os, gc, json
mode = sys.argv[1]        # "rss" | "tracemalloc"
parser = sys.argv[2]
path = sys.argv[3]
html = open(path, encoding="utf-8").read()

def rss_kb():
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux reports KB
    return r/1024.0 if sys.platform=="darwin" else r

def run():
    if parser=="selectolax_lexbor":
        from selectolax.lexbor import LexborHTMLParser
        t=LexborHTMLParser(html)
        titles=[n.text() for n in t.css("h3.title")]
        links=[n.attributes.get("href") for n in t.css("a")]
        return t,(len(titles),len(links))
    if parser=="selectolax_modest":
        from selectolax.parser import HTMLParser
        t=HTMLParser(html)
        titles=[n.text() for n in t.css("h3.title")]
        links=[n.attributes.get("href") for n in t.css("a")]
        return t,(len(titles),len(links))
    if parser=="lxml":
        import lxml.html
        t=lxml.html.fromstring(html)
        titles=[n.text_content() for n in t.cssselect("h3.title")]
        links=[n.get("href") for n in t.cssselect("a")]
        return t,(len(titles),len(links))
    if parser=="bs4_lxml":
        from bs4 import BeautifulSoup
        t=BeautifulSoup(html,"lxml")
        titles=[n.get_text() for n in t.select("h3.title")]
        links=[n.get("href") for n in t.select("a")]
        return t,(len(titles),len(links))
    if parser=="bs4_htmlparser":
        from bs4 import BeautifulSoup
        t=BeautifulSoup(html,"html.parser")
        titles=[n.get_text() for n in t.select("h3.title")]
        links=[n.get("href") for n in t.select("a")]
        return t,(len(titles),len(links))
    if parser=="parsel":
        from parsel import Selector
        t=Selector(text=html)
        titles=t.css("h3.title::text").getall()
        links=t.css("a::attr(href)").getall()
        return t,(len(titles),len(links))
    raise SystemExit("unknown parser")

out = {"parser": parser, "mode": mode}

if mode == "rss":
    gc.collect()
    rss_before = rss_kb()
    tree, counts = run()   # keep tree alive; tracemalloc NEVER started here
    rss_after = rss_kb()
    out["rss_delta_mb"] = round((rss_after-rss_before)/1024, 3)
    out["rss_peak_mb"] = round(rss_after/1024, 3)
    out["counts"] = counts
elif mode == "tracemalloc":
    import tracemalloc
    gc.collect()
    tracemalloc.start()
    tree, counts = run()   # keep tree alive
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    out["tracemalloc_peak_mb"] = round(peak/1024/1024, 3)
    out["tracemalloc_current_mb"] = round(cur/1024/1024, 3)
    out["counts"] = counts
else:
    raise SystemExit("unknown mode")

print(json.dumps(out))
'''

# ---------- import child program ----------
IMPORT_CHILD = r'''
import time, importlib, sys
mod = sys.argv[1]
t0=time.perf_counter()
importlib.import_module(mod)
t1=time.perf_counter()
print(round((t1-t0)*1000,3))
'''

MEM_PARSERS = ["selectolax_lexbor", "selectolax_modest", "lxml", "parsel", "bs4_lxml", "bs4_htmlparser"]
IMPORT_MODS = {
    "selectolax.lexbor": "selectolax.lexbor",
    "selectolax.parser": "selectolax.parser",
    "lxml.html": "lxml.html",
    "bs4": "bs4",
    "parsel": "parsel",
}


def run_mem(mode, parser, page):
    path = os.path.join(FIX, page)
    out = subprocess.run([PY, "-c", MEM_CHILD, mode, parser, path],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return {"parser": parser, "mode": mode, "error": out.stderr.strip()[-500:]}
    return json.loads(out.stdout.strip().splitlines()[-1])


def run_import(mod, repeats=7):
    times = []
    for _ in range(repeats):
        out = subprocess.run([PY, "-c", IMPORT_CHILD, mod], capture_output=True, text=True)
        if out.returncode == 0:
            times.append(float(out.stdout.strip()))
    times.sort()
    return {"module": mod, "repeats": len(times), "min_ms": times[0],
            "median_ms": times[len(times)//2], "max_ms": times[-1], "all_ms": times}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=0)
    args = ap.parse_args()

    result = {"meta": {"run_id": args.run_id, "python": sys.version.split()[0],
                       "note": "RSS and tracemalloc measured in SEPARATE processes"},
              "memory_rss": {}, "memory_tracemalloc": {}, "import_cold": {}}

    for page in ["page_1mb.html", "page_10mb.html"]:
        result["memory_rss"][page] = {}
        result["memory_tracemalloc"][page] = {}
        for p in MEM_PARSERS:
            r_rss = run_mem("rss", p, page)
            result["memory_rss"][page][p] = r_rss
            r_tm = run_mem("tracemalloc", p, page)
            result["memory_tracemalloc"][page][p] = r_tm
            if "error" in r_rss:
                print(f"[RSS {page}] {p:<20} ERROR: {r_rss['error'][:100]}")
            else:
                tm = r_tm.get("tracemalloc_peak_mb", "?")
                print(f"[{page}] {p:<20} RSS_delta={r_rss['rss_delta_mb']:>8.2f}MB  "
                      f"(sep) tracemalloc_peak={tm}MB  {r_rss.get('counts')}")

    print()
    for name, mod in IMPORT_MODS.items():
        r = run_import(mod)
        result["import_cold"][name] = r
        print(f"[IMPORT] {name:<22} median={r['median_ms']:>8.2f}ms  min={r['min_ms']:>8.2f}ms")

    outpath = os.path.join(RUNS, f"bench_memory_import.run{args.run_id}.json")
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2)
    print("\nwritten", outpath)


if __name__ == "__main__":
    main()
