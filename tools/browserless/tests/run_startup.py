#!/usr/bin/env python3
"""H1 — container startup + first-usable-session latency (cold vs warm vs PREBOOT).

Decomposes the deployment cost that a browser-LIBRARY benchmark never sees:
  A. container boot: `docker run` -> /pressure answers 200 (service ready)
  B. first /content: cold browser launch inside a ready container
  C. warm /content: subsequent requests (browser already exercised)
  D. PREBOOT=true: does a kept-warm browser cut the first-request cost?

>=3 fresh boots so the startup number is a distribution with variance, not a
single lucky run (methodology Part 2). Every /content hits the SAME local fixture
/render page; nothing is hardcoded — all numbers come from measured elapsed.
"""

from __future__ import annotations

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bl_common as bl
from fixture_server import start_fixture_server

N_BOOTS = 3
WARM_CALLS = 5
ART = os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw",
                   "startup.json")


LAST_ARGV: list[str] = []


def one_boot(name: str, fixture_url: str, preboot: bool) -> dict:
    global LAST_ARGV
    LAST_ARGV = bl.docker_run(name, preboot=preboot)
    ready_s = bl.wait_ready(timeout_s=90)
    # first (cold) /content
    st, body, cold_s = bl.post_content(fixture_url, timeout=90)
    cold_ok = st == 200 and b"Runtime Injected Marker 88" in body
    # warm /content x WARM_CALLS
    warm = []
    for _ in range(WARM_CALLS):
        st2, body2, e2 = bl.post_content(fixture_url, timeout=60)
        warm.append({"status": st2, "elapsed_s": round(e2, 4),
                     "ok": st2 == 200 and b"Runtime Injected Marker 88" in body2})
    bl.docker_stop(name)
    return {
        "preboot": preboot,
        "container_ready_s": round(ready_s, 4),
        "first_content_cold_s": round(cold_s, 4),
        "first_content_cold_ok": cold_ok,
        "warm_calls": warm,
        "warm_median_s": round(statistics.median(w["elapsed_s"] for w in warm), 4),
    }


def summarize(runs: list[dict], label: str) -> dict:
    ready = [r["container_ready_s"] for r in runs]
    cold = [r["first_content_cold_s"] for r in runs]
    warm = [r["warm_median_s"] for r in runs]
    return {
        "label": label,
        "n_boots": len(runs),
        "container_ready_s": {"median": round(statistics.median(ready), 4),
                              "min": round(min(ready), 4),
                              "max": round(max(ready), 4)},
        "first_content_cold_s": {"median": round(statistics.median(cold), 4),
                                 "min": round(min(cold), 4),
                                 "max": round(max(cold), 4)},
        "warm_content_s": {"median": round(statistics.median(warm), 4),
                           "min": round(min(warm), 4),
                           "max": round(max(warm), 4)},
    }


def main() -> None:
    srv = start_fixture_server()
    fixture_url = f"http://host.docker.internal:{srv.port}/render"
    print(f"fixture on host 0.0.0.0:{srv.port}; container reaches it via "
          f"host.docker.internal:{srv.port}")
    try:
        cold_runs = []
        for i in range(N_BOOTS):
            print(f"[cold boot {i+1}/{N_BOOTS}] PREBOOT=off")
            cold_runs.append(one_boot(f"bl_start_cold_{i}", fixture_url, False))
        preboot_runs = []
        for i in range(N_BOOTS):
            print(f"[preboot boot {i+1}/{N_BOOTS}] PREBOOT=on")
            preboot_runs.append(one_boot(f"bl_start_pre_{i}", fixture_url, True))
    finally:
        srv.stop()

    out = {
        "hypothesis": "H1 startup + first-usable-session latency (cold/warm/preboot)",
        "image": bl.IMAGE,
        "n_boots_each": N_BOOTS,
        "warm_calls_each_boot": WARM_CALLS,
        "runs_default": cold_runs,
        "runs_preboot": preboot_runs,
        "summary_default": summarize(cold_runs, "PREBOOT=off"),
        "summary_preboot": summarize(preboot_runs, "PREBOOT=on"),
        "docker_run_argv_example": bl.redact(" ".join(LAST_ARGV)),
    }
    bl.write_artifact(ART, out)
    d, p = out["summary_default"], out["summary_preboot"]
    print(f"\ncontainer_ready median: default {d['container_ready_s']['median']}s  "
          f"preboot {p['container_ready_s']['median']}s")
    print(f"first /content (cold) median: default "
          f"{d['first_content_cold_s']['median']}s  preboot "
          f"{p['first_content_cold_s']['median']}s")
    print(f"warm /content median: default {d['warm_content_s']['median']}s  "
          f"preboot {p['warm_content_s']['median']}s")


if __name__ == "__main__":
    main()
