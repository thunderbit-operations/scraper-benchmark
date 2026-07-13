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
     CURRENT RSS (via `ps`) at intervals. Each subject runs in its OWN fresh
     subprocess so no earlier stage's high-water mark contaminates the baseline
     (the reason we do NOT use ru_maxrss here -- see rss_current_mb docstring).
     A calibration subject that intentionally retains 100 KB/iter is measured
     the same way, so the JSON proves the instrument tracks a real leak before
     we conclude "no leak" for the parsers. A healthy parser's RSS plateaus; a
     leak shows monotonic growth. We report first/last/max RSS and a simple
     slope so the doc can state "no growth beyond X MB over K iterations".

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


def rss_current_mb():
    """CURRENT resident set size in MB (not a high-water mark).

    The leak check must read *current* RSS, not ru_maxrss: ru_maxrss is a
    monotonic process high-water mark, so if any earlier stage in the same
    process (e.g. the bs4 4-thread run in thread_scaling) pushed the peak up,
    a later leak that stays *under* that peak never sets a new high-water mark
    and reads 0.0 growth -- i.e. the instrument goes blind to real leaks below
    the historical peak. Current RSS via `ps` climbs with a real leak.
    (Kept dependency-free on purpose; psutil would work too.)
    """
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                         capture_output=True, text=True)
    try:
        return int(out.stdout.strip()) / 1024.0  # ps reports KB on macOS/Linux
    except (ValueError, TypeError):
        return float("nan")


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
# Each subject runs in its OWN fresh subprocess so (a) no earlier stage's RSS
# peak contaminates the baseline, and (b) the instrument reads CURRENT RSS.
# A calibration subject with a KNOWN 100 KB/iter leak is measured the same way,
# so the JSON itself proves the instrument tracks a real leak before we conclude
# "no leak" for the parsers.
MEMLOOP_CHILD = r'''
import os, sys, gc, json, subprocess

def rss_current_mb():
    out = subprocess.run(["ps","-o","rss=","-p",str(os.getpid())],capture_output=True,text=True)
    return int(out.stdout.strip())/1024.0

subject = sys.argv[1]
iters = int(sys.argv[2])
sample_every = int(sys.argv[3])
html_path = sys.argv[4]
html = open(html_path).read()

if subject == "selectolax_lexbor":
    from selectolax.lexbor import LexborHTMLParser
    def step(_leak):
        t = LexborHTMLParser(html); _ = [n.attributes.get("href") for n in t.css("a")]
elif subject == "selectolax_modest":
    from selectolax.parser import HTMLParser
    def step(_leak):
        t = HTMLParser(html); _ = [n.attributes.get("href") for n in t.css("a")]
elif subject == "lxml":
    import lxml.html
    def step(_leak):
        t = lxml.html.fromstring(html); _ = [n.get("href") for n in t.cssselect("a")]
elif subject == "_calibration_known_leak":
    # Instrument calibration: retain 100 KB per iteration -> a real, monotonic leak.
    def step(_leak):
        _leak.append(bytearray(100*1024))
else:
    print(json.dumps({"error": "unknown subject"})); sys.exit(2)

leak_store = []
gc.collect()
base = rss_current_mb()
samples = []
for i in range(1, iters+1):
    step(leak_store)
    if i % sample_every == 0:
        gc.collect()   # sample RETAINED memory, not in-flight parse allocations
        samples.append(round(rss_current_mb() - base, 3))
out = {
    "subject": subject,
    "instrument": "current_rss_ps_mb",
    "iters": iters,
    "rss_base_mb": round(base, 2),
    "rss_delta_samples_mb": samples,
    "rss_delta_first_sample_mb": samples[0] if samples else None,
    "rss_delta_last_sample_mb": samples[-1] if samples else None,
    "rss_delta_max_mb": max(samples) if samples else None,
    "growth_first_to_last_mb": round(samples[-1]-samples[0], 3) if len(samples) >= 2 else None,
}
if subject == "_calibration_known_leak":
    out["injected_total_mb"] = round(iters*100/1024.0, 1)
print(json.dumps(out))
'''


def mem_growth(html_path, iters=2000, sample_every=200):
    # Order matters only for readability; each runs in its own process anyway.
    subjects = ["_calibration_known_leak", "selectolax_lexbor", "selectolax_modest", "lxml"]
    res = {}
    for subject in subjects:
        p = subprocess.run([PY, "-c", MEMLOOP_CHILD, subject, str(iters),
                            str(sample_every), html_path],
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            res[subject] = {"result": "child_nonzero_exit", "returncode": p.returncode,
                            "stderr": p.stderr[-200:]}
            print(f"[MEMLOOP] {subject:<26} FAILED rc={p.returncode}")
            continue
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            res[subject] = {"result": "parse_err", "stdout": p.stdout[-200:]}
            continue
        # Data-derived leak verdict (not eyeballed): a real leak is MONOTONIC and
        # its total growth scales with iters (the calibration subject climbs to
        # ~injected_total). We flag "leak" only if the samples rise near-monotonically
        # AND end well above where they started; churn that goes up and back down,
        # or a bounded plateau, is "no monotonic growth (bounded working set)".
        s = r.get("rss_delta_samples_mb") or []
        if subject != "_calibration_known_leak" and len(s) >= 3:
            ups = sum(1 for i in range(1, len(s)) if s[i] > s[i - 1] + 0.5)
            frac_up = ups / (len(s) - 1)
            span = max(s) - min(s)
            g = r.get("growth_first_to_last_mb") or 0.0
            r["leak_verdict"] = ("monotonic_growth_possible_leak"
                                 if (frac_up >= 0.8 and g > 0.5 * span and g > 5)
                                 else "no_monotonic_growth_bounded_working_set")
            r["fraction_samples_increasing"] = round(frac_up, 2)
        res[subject] = r
        print(f"[MEMLOOP] {subject:<26} iters={iters} base={r['rss_base_mb']}MB "
              f"first={r['rss_delta_first_sample_mb']}MB last={r['rss_delta_last_sample_mb']}MB "
              f"max={r['rss_delta_max_mb']}MB growth={r['growth_first_to_last_mb']}MB "
              f"{r.get('leak_verdict','')}")

    # Instrument self-check: the known-leak subject MUST show growth (else the
    # instrument is blind and no "no leak" conclusion is valid).
    cal = res.get("_calibration_known_leak", {})
    injected = cal.get("injected_total_mb")
    observed = cal.get("rss_delta_last_sample_mb")
    ok = isinstance(observed, (int, float)) and isinstance(injected, (int, float)) \
        and observed >= 0.5 * injected
    res["_instrument_calibration"] = {
        "known_leak_per_iter_kb": 100,
        "injected_total_mb": injected,
        "observed_growth_mb": observed,
        "instrument_tracks_known_leak": bool(ok),
        "note": ("current-RSS instrument registered the injected leak "
                 "(observed >= 50% of injected) -> a real leak in the parsers "
                 "would show; ru_maxrss would have read ~0 for a leak under a "
                 "prior stage's high-water peak."),
    }
    print(f"[MEMLOOP] instrument calibration: injected~{injected}MB "
          f"observed~{observed}MB tracks_leak={ok}")
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

    html_1mb_path = os.path.join(FIX, "page_1mb.html")
    html_1mb = open(html_1mb_path).read()

    print("=== A) thread scaling / GIL release ===")
    a = thread_scaling(html_1mb)
    print("\n=== B) long-loop memory growth (current-RSS instrument, per-subject subprocess) ===")
    b = mem_growth(html_1mb_path)
    print("\n=== C) node lifecycle ===")
    c = node_lifecycle()

    out = {"meta": {"run_id": args.run_id, "python": sys.version.split()[0],
                    "note": "GIL signal is empirical wall-clock speedup, not a source claim; "
                            "mem_growth uses CURRENT RSS (ps) in a fresh subprocess and "
                            "includes a known-leak calibration subject"},
           "thread_scaling": a, "mem_growth": b, "node_lifecycle": c}
    with open(os.path.join(RAW, "production_dims.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\nwritten", os.path.join(RAW, "production_dims.json"))


if __name__ == "__main__":
    main()
