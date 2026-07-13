#!/usr/bin/env python3
"""Production-relevance dimensions Fable 5 flagged as missing (methodology v3
acceptance list): GIL release / thread scaling, long-loop memory growth, and
parser/node object lifecycle. Measured, not asserted.

Three experiments (all numbers computed at runtime):

  A) THREAD SCALING / GIL RELEASE
     Parse the 1MB fixture M times, single-threaded, then across T threads with
     a ThreadPoolExecutor. If the C parse loop releases the GIL, wall-clock with
     T threads should drop well below single-thread wall-clock (speedup > 1).
     If it holds the GIL, threads serialize and speedup ~= 1. We report the
     measured speedup per parser -- an empirical GIL-release signal, labelled a
     signal (not a claim about the C source).

  B) LONG-LOOP MEMORY GROWTH (leak check)
     Parse + extract + DROP the tree in a tight loop for K iterations, sampling
     process RSS at intervals. A healthy parser's RSS plateaus; a leak shows
     monotonic growth. We report first/last/max RSS and a simple slope so the
     doc can state "no growth beyond X MB over K iterations" from data.

  C) NODE LIFECYCLE (use-after-free / dangling handle safety)
     Hold a Node handle, then let its owning tree go out of scope / be reparsed,
     and try to use the stale handle. Record whether it (a) still works, (b)
     raises cleanly, or (c) segfaults the process. Run in a SUBPROCESS so a
     hard crash is caught as a nonzero exit, not a killed test run.
"""
import argparse
import gc
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(HERE, "..", "artifacts", "raw")
FIX = os.environ.get("SLX_SYNTH_DIR") or os.path.join(HERE, "..", "artifacts", "fixtures", "synthetic")
os.makedirs(RAW, exist_ok=True)
PY = sys.executable


def rss_mb():
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return (r / 1024.0 / 1024.0) if sys.platform == "darwin" else (r / 1024.0)


# ---------------- A) thread scaling ----------------
def parse_fns():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser
    import lxml.html
    from bs4 import BeautifulSoup

    def sl_lexbor(h):
        t = LexborHTMLParser(h); return len(t.css("a"))

    def sl_modest(h):
        t = HTMLParser(h); return len(t.css("a"))

    def do_lxml(h):
        t = lxml.html.fromstring(h); return len(t.cssselect("a"))

    def do_bs4(h):
        t = BeautifulSoup(h, "lxml"); return len(t.select("a"))

    return {"selectolax_lexbor": sl_lexbor, "selectolax_modest": sl_modest,
            "lxml": do_lxml, "bs4_lxml": do_bs4}


def thread_scaling(html, n_tasks=48, threads=4, repeat=3):
    fns = parse_fns()
    res = {}
    for name, fn in fns.items():
        # warm
        fn(html)
        # single-threaded wall time for n_tasks
        single_best = None
        for _ in range(repeat):
            gc.collect()
            t0 = time.perf_counter()
            for _ in range(n_tasks):
                fn(html)
            dt = time.perf_counter() - t0
            single_best = dt if single_best is None else min(single_best, dt)
        # threaded wall time for the same n_tasks
        multi_best = None
        for _ in range(repeat):
            gc.collect()
            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=threads) as ex:
                list(ex.map(lambda _: fn(html), range(n_tasks)))
            dt = time.perf_counter() - t0
            multi_best = dt if multi_best is None else min(multi_best, dt)
        speedup = round(single_best / multi_best, 3) if multi_best > 0 else None
        res[name] = {
            "n_tasks": n_tasks, "threads": threads,
            "single_thread_s": round(single_best, 4),
            "threaded_s": round(multi_best, 4),
            "speedup": speedup,
            "gil_release_signal": ("likely-releases-GIL" if speedup and speedup >= 1.5
                                   else "likely-holds-GIL" if speedup and speedup <= 1.15
                                   else "inconclusive"),
        }
        print(f"[THREAD] {name:<20} single={single_best:.3f}s threaded(x{threads})={multi_best:.3f}s "
              f"speedup={speedup} -> {res[name]['gil_release_signal']}")
    return res


# ---------------- B) long-loop memory growth ----------------
def mem_growth(html, iters=2000, sample_every=200):
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser
    import lxml.html

    def sl_lexbor():
        t = LexborHTMLParser(html)
        _ = [n.attributes.get("href") for n in t.css("a")]

    def sl_modest():
        t = HTMLParser(html)
        _ = [n.attributes.get("href") for n in t.css("a")]

    def do_lxml():
        t = lxml.html.fromstring(html)
        _ = [n.get("href") for n in t.cssselect("a")]

    loops = {"selectolax_lexbor": sl_lexbor, "selectolax_modest": sl_modest, "lxml": do_lxml}
    res = {}
    for name, fn in loops.items():
        gc.collect()
        samples = []
        base = rss_mb()
        for i in range(1, iters + 1):
            fn()
            if i % sample_every == 0:
                samples.append(round(rss_mb() - base, 3))
        res[name] = {
            "iters": iters,
            "rss_base_mb": round(base, 2),
            "rss_delta_samples_mb": samples,
            "rss_delta_first_sample_mb": samples[0] if samples else None,
            "rss_delta_last_sample_mb": samples[-1] if samples else None,
            "rss_delta_max_mb": max(samples) if samples else None,
            "growth_first_to_last_mb": round(samples[-1] - samples[0], 3) if len(samples) >= 2 else None,
        }
        print(f"[MEMLOOP] {name:<20} iters={iters} rss_delta first={samples[0]}MB "
              f"last={samples[-1]}MB max={max(samples)}MB growth={res[name]['growth_first_to_last_mb']}MB")
    return res


# ---------------- C) node lifecycle (subprocess, crash-safe) ----------------
LIFECYCLE_CHILD = r'''
import sys, json, gc
scenario = sys.argv[1]
out = {"scenario": scenario}
try:
    if scenario == "stale_node_after_tree_gc":
        # keep a node, drop the only ref to its tree, force GC, then use node
        from selectolax.lexbor import LexborHTMLParser
        def get_node():
            t = LexborHTMLParser("<div><p id=x>hello <b>w</b></p></div>")
            return t.css_first("p")  # tree ref goes away when function returns
        node = get_node()
        gc.collect()
        out["text_after_tree_gc"] = node.text()
        out["html_after_tree_gc"] = node.html
        out["result"] = "usable"
    elif scenario == "stale_node_after_reparse":
        from selectolax.lexbor import LexborHTMLParser
        t = LexborHTMLParser("<p id=x>first</p>")
        n = t.css_first("p")
        first = n.text()
        # decompose the node, then touch it again
        n.decompose()
        try:
            after = n.text()
            out["text_after_decompose"] = after
            out["result"] = "usable_after_decompose"
        except Exception as e:
            out["decompose_use_error"] = f"{type(e).__name__}: {str(e)[:80]}"
            out["result"] = "raises_cleanly_after_decompose"
        out["first_text"] = first
    else:
        out["result"] = "unknown_scenario"
    print(json.dumps(out))
except Exception as e:
    out["result"] = "raised"
    out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    print(json.dumps(out))
'''


def node_lifecycle():
    res = {}
    for scenario in ["stale_node_after_tree_gc", "stale_node_after_reparse"]:
        p = subprocess.run([PY, "-c", LIFECYCLE_CHILD, scenario],
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            # nonzero exit with no JSON == likely a hard crash (segfault)
            res[scenario] = {"result": "HARD_CRASH_or_nonzero_exit",
                             "returncode": p.returncode,
                             "stderr": p.stderr[-200:]}
        else:
            try:
                res[scenario] = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:
                res[scenario] = {"result": "PARSE_ERR", "stdout": p.stdout[-200:]}
        print(f"[LIFECYCLE] {scenario:<30} -> {res[scenario].get('result')}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=0)
    args = ap.parse_args()

    html_1mb = open(os.path.join(FIX, "page_1mb.html")).read()

    print("=== A) thread scaling / GIL release ===")
    a = thread_scaling(html_1mb)
    print("\n=== B) long-loop memory growth ===")
    b = mem_growth(html_1mb)
    print("\n=== C) node lifecycle ===")
    c = node_lifecycle()

    out = {"meta": {"run_id": args.run_id, "python": sys.version.split()[0],
                    "note": "GIL signal is empirical wall-clock speedup, not a source claim"},
           "thread_scaling": a, "mem_growth": b, "node_lifecycle": c}
    with open(os.path.join(RAW, "production_dims.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\nwritten", os.path.join(RAW, "production_dims.json"))


if __name__ == "__main__":
    main()
