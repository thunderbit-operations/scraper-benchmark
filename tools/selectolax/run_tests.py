#!/usr/bin/env python3
"""One-command reproduction for the selectolax pack.

selectolax is a Python binding to the Modest and Lexbor C engines: a fast HTML5
parser with CSS selectors. Unlike the other packs in this repo, it is a *parsing
library* (no crawl / no JS), so this pack does NOT use the shared catalog
fixtures. Instead it reproduces a parser benchmark: performance distributions vs
lxml / BeautifulSoup / parsel across page sizes, a CSS-selector coverage matrix
(with soupsieve and a fault-finding pass), an adversarial-input sweep, a real
dirty-HTML accuracy comparison, memory/import profiling, a non-UTF-8 encoding
probe, and production-dimension checks (thread scaling / memory growth / node
lifecycle).

Steps:
  1. generate synthetic fixtures (gen_fixtures.py)
  2. CSS coverage matrix          (tests/css_coverage.py)
  3. adversarial inputs           (tests/adversarial.py)
  4. non-UTF-8 encoding probe     (tests/encoding_probe.py)
  5. API / claim verification     (tests/api_usability.py)
  6. production dimensions        (tests/production_dims.py)
  7. real-world dirty HTML        (tests/real_world.py)  [uses committed fixtures]
  8. performance benchmarks       (tests/run_all.py)     [N independent runs]

Every result lands in results/. Set RUNS_N to change the benchmark run count
(default 3, matching the published numbers). Set QUICK=1 for a fast smoke run
(fewer iterations) if you only want to confirm it executes.

Note: fetching fresh real-world fixtures is a separate manual step
(tests/fetch_real_sites.sh); the committed HTML captures let you reproduce the
accuracy numbers without hitting live sites.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
TESTS = HERE / "tests"

# Point the shared test scripts at this repo's layout (results/ + fixtures/).
# The scripts default to an ../artifacts/... layout used in the private research
# tree; these overrides make the exact same scripts write and read here.
RESULTS = HERE / "results"
FIX_SYNTH = HERE / "fixtures" / "synthetic"
FIX_REAL = HERE / "fixtures" / "real"
RESULTS.mkdir(exist_ok=True)
FIX_SYNTH.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("SLX_RESULTS_DIR", str(RESULTS))
os.environ.setdefault("SLX_SYNTH_DIR", str(FIX_SYNTH))
os.environ.setdefault("SLX_REAL_DIR", str(FIX_REAL))


def run(script, *args):
    print(f"\n{'='*70}\n# {script} {' '.join(args)}\n{'='*70}", flush=True)
    p = subprocess.run([PY, str(TESTS / script), *args])
    if p.returncode != 0:
        print(f"!! {script} exited {p.returncode}", flush=True)
    return p.returncode


def main():
    quick = os.environ.get("QUICK") == "1"
    env_iters = "20" if quick else os.environ.get("ITERS", "100")
    runs_n = "1" if quick else os.environ.get("RUNS_N", "3")
    os.environ["ITERS"] = env_iters

    run("gen_fixtures.py")
    run("css_coverage.py")
    run("adversarial.py")
    run("encoding_probe.py")
    run("api_usability.py")
    run("production_dims.py")
    run("real_world.py")
    # performance: N independent process runs + cross-run variance
    run("run_all.py", "--runs", runs_n)

    print("\nAll done. Raw results are in results/ (see README.md).", flush=True)


if __name__ == "__main__":
    main()
