#!/usr/bin/env python3
"""H2 (adversarial) — concurrency-ceiling behavior: run vs queue vs 429.

The documented contract: total allowed connections = CONCURRENT (running) + QUEUED
(pending); anything beyond is rejected with HTTP 429. This runner PROVES it on two
axes of truth simultaneously:

  * CLIENT truth: fire (CONCURRENT + QUEUED + OVER) simultaneous /content requests,
    each navigating to /slow?ms=HOLD so it occupies a session for a controlled time.
    Count the exact 200 / 429 split and measure per-request wall time (running vs
    queued cohorts separate visibly by ~HOLD).
  * SERVER truth: sample /pressure at mid-load -> running / queued / recentlyRejected
    / isAvailable, independent of the client's own view.

Run at several (CONCURRENT, QUEUED) configs so the ceiling = C+Q is shown to MOVE
with configuration, not a fixed constant. Adversarial: we intentionally overshoot.

RUN ALONE (saturates the container by design).
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))
import bl_common as bl
from fixture_server import start_fixture_server

HOLD_MS = 5000           # each session occupied ~5s (server-side sleep)
CONFIGS = [(2, 2), (3, 5), (5, 5)]   # (CONCURRENT, QUEUED)
OVER = 4                 # requests beyond the C+Q ceiling
ART = os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw",
                   "concurrency.json")


def run_config(concurrent: int, queued: int, fixture_url: str) -> dict:
    name = f"bl_conc_{concurrent}_{queued}"
    bl.docker_run(name, concurrent=concurrent, queued=queued, timeout_ms=60000)
    bl.wait_ready(timeout_s=90)
    total = concurrent + queued + OVER
    slow_url = f"{fixture_url}?ms={HOLD_MS}"

    results: list[dict] = []
    pressure_samples: list[dict] = []
    stop_sampler = threading.Event()

    def sample_pressure() -> None:
        while not stop_sampler.is_set():
            try:
                p = bl.pressure()
                pressure_samples.append({
                    "t": round(time.monotonic(), 3),
                    "running": p["running"], "queued": p["queued"],
                    "recentlyRejected": p["recentlyRejected"],
                    "isAvailable": p["isAvailable"]})
            except Exception:
                pass
            time.sleep(0.25)

    sampler = threading.Thread(target=sample_pressure, daemon=True)
    sampler.start()

    def fire(_i: int) -> dict:
        st, body, el = bl.post_content(slow_url, timeout=90)
        return {"status": st, "elapsed_s": round(el, 3)}

    with cf.ThreadPoolExecutor(max_workers=total) as ex:
        futs = [ex.submit(fire, i) for i in range(total)]
        results = [f.result() for f in futs]

    stop_sampler.set()
    sampler.join(timeout=2)
    bl.docker_stop(name)

    n200 = sum(1 for r in results if r["status"] == 200)
    n429 = sum(1 for r in results if r["status"] == 429)
    other = [r["status"] for r in results if r["status"] not in (200, 429)]
    # peak observed running/queued from server truth
    peak_running = max((s["running"] for s in pressure_samples), default=None)
    peak_queued = max((s["queued"] for s in pressure_samples), default=None)
    peak_rejected = max((s["recentlyRejected"] for s in pressure_samples), default=None)
    ok_elapsed = sorted(r["elapsed_s"] for r in results if r["status"] == 200)

    return {
        "config": {"CONCURRENT": concurrent, "QUEUED": queued,
                   "ceiling_CplusQ": concurrent + queued},
        "fired": total,
        "client": {"http_200": n200, "http_429": n429, "other_status": other},
        "server_peak": {"running": peak_running, "queued": peak_queued,
                        "recentlyRejected": peak_rejected},
        "ceiling_matches_C_plus_Q": n200 == (concurrent + queued),
        "rejected_matches_over": n429 == OVER,
        "ok_elapsed_s": {
            "min": ok_elapsed[0] if ok_elapsed else None,
            "median": round(statistics.median(ok_elapsed), 3) if ok_elapsed else None,
            "max": ok_elapsed[-1] if ok_elapsed else None},
        "pressure_samples": pressure_samples,
    }


def main() -> None:
    srv = start_fixture_server()
    fixture_url = f"http://host.docker.internal:{srv.port}/slow"
    print(f"fixture on 0.0.0.0:{srv.port}; HOLD={HOLD_MS}ms, OVER={OVER}")
    configs_out = []
    try:
        for c, q in CONFIGS:
            print(f"[config CONCURRENT={c} QUEUED={q}] firing {c+q+OVER} concurrent")
            res = run_config(c, q, fixture_url)
            cl = res["client"]
            sp = res["server_peak"]
            print(f"  client: 200={cl['http_200']} 429={cl['http_429']}  "
                  f"server peak: running={sp['running']} queued={sp['queued']} "
                  f"rejected={sp['recentlyRejected']}  "
                  f"ceiling_ok={res['ceiling_matches_C_plus_Q']}")
            configs_out.append(res)
    finally:
        srv.stop()

    out = {
        "hypothesis": "H2 concurrency ceiling: running=CONCURRENT, queued<=QUEUED, "
                      "beyond C+Q -> HTTP 429 (client + server truth)",
        "image": bl.IMAGE,
        "hold_ms": HOLD_MS, "over": OVER,
        "configs": configs_out,
    }
    bl.write_artifact(ART, out)


if __name__ == "__main__":
    main()
