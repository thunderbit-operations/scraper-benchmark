#!/usr/bin/env python3
"""H4 — resource lifecycle: session/zombie leak + container-memory growth.
   H5 — per-session TIMEOUT enforcement (adversarial lifecycle recycling).

H4: run K sequential /content sessions. Sample operator-visible container memory
    (`docker stats`) at baseline / after each burst / after settle, and enumerate
    chrome-family processes + ZOMBIES inside the container via /proc after the run.
    Question the SERP consensus never quantifies: does a per-request-browser service
    leak processes/memory across many sessions, or does it recycle cleanly? (dumb-init
    is PID 1 -> reaper hypothesis.) Also: /sessions accuracy at idle.

    Instrument calibration (methodology Part 6.3): before trusting "0 zombies" as a
    result, we FIRST confirm the enumerator can SEE chrome at all — by sampling procs
    while a session is mid-flight (expect chrome_procs > 0). A detector that reads 0
    during load is blind and its post-run 0 is meaningless.

H5: set TIMEOUT below the page's server-side hold. A /content to /slow?ms=HOLD with
    HOLD > TIMEOUT must be force-terminated by Browserless at ~TIMEOUT (non-200),
    while HOLD < TIMEOUT succeeds. Proves per-session lifecycle recycling, and
    locates the kill boundary.
"""

from __future__ import annotations

import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))
import bl_common as bl
from fixture_server import start_fixture_server

K_SESSIONS = 30
BURST = 5
ART = os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw",
                   "lifecycle.json")


def h4_resource(fixture_render: str, fixture_slow: str) -> dict:
    name = "bl_life"
    bl.docker_run(name, concurrent=3, queued=10, timeout_ms=60000)
    bl.wait_ready(timeout_s=90)

    baseline_mem = bl.container_mem_bytes(name)
    idle_sessions = None
    try:
        idle_sessions = len(bl.get_json("/sessions", timeout=8))
    except Exception:
        pass

    # --- instrument calibration: can we SEE chrome during a live session? ---
    mid_flight = {"chrome_procs": None, "zombies": None}
    calib_stop = threading.Event()

    def probe_midflight() -> None:
        # while a slow session is in-flight, sample procs once
        time.sleep(1.5)
        if not calib_stop.is_set():
            p = bl.container_procs(name)
            mid_flight["chrome_procs"] = p["chrome_procs"]
            mid_flight["zombies"] = p["zombies"]

    t = threading.Thread(target=probe_midflight, daemon=True)
    t.start()
    bl.post_content(f"{fixture_slow}?ms=3000", timeout=30)  # hold a session ~3s
    calib_stop.set()
    t.join(timeout=2)

    # --- K sequential sessions, sampling memory each BURST ---
    mem_series = [{"after_sessions": 0, "mem_bytes": baseline_mem}]
    ok = 0
    for i in range(1, K_SESSIONS + 1):
        st, body, _ = bl.post_content(fixture_render, timeout=60)
        if st == 200 and b"Runtime Injected Marker 88" in body:
            ok += 1
        if i % BURST == 0:
            mem_series.append({"after_sessions": i,
                               "mem_bytes": bl.container_mem_bytes(name)})

    time.sleep(3)  # settle
    settle_mem = bl.container_mem_bytes(name)
    post = bl.container_procs(name)

    bl.docker_stop(name)

    mems = [m["mem_bytes"] for m in mem_series if m["mem_bytes"]]
    return {
        "k_sessions": K_SESSIONS, "sessions_ok": ok,
        "idle_sessions_endpoint": idle_sessions,
        "instrument_calibration": {
            "chrome_procs_midflight": mid_flight["chrome_procs"],
            "detector_can_see_chrome": (mid_flight["chrome_procs"] or 0) > 0,
        },
        "container_mem_bytes": {
            "baseline": baseline_mem,
            "series": mem_series,
            "settle_after_run": settle_mem,
            "peak": max(mems) if mems else None,
            "growth_baseline_to_settle": (settle_mem - baseline_mem)
            if (settle_mem and baseline_mem) else None,
        },
        "post_run_procs": {"chrome_procs": post["chrome_procs"],
                           "zombies": post["zombies"],
                           "comm_counts": post["comm_counts"]},
    }


def h5_timeout(fixture_slow: str) -> dict:
    name = "bl_timeout"
    timeout_ms = 5000
    bl.docker_run(name, concurrent=2, queued=2, timeout_ms=timeout_ms)
    bl.wait_ready(timeout_s=90)
    try:
        # under-timeout: HOLD < TIMEOUT -> should succeed
        st_under, body_under, el_under = bl.post_content(
            f"{fixture_slow}?ms=2000", timeout=30)
        # over-timeout: HOLD > TIMEOUT -> should be killed (non-200) near TIMEOUT
        st_over, body_over, el_over = bl.post_content(
            f"{fixture_slow}?ms=15000", timeout=40)
        return {
            "timeout_ms": timeout_ms,
            "under_timeout": {"hold_ms": 2000, "status": st_under,
                              "elapsed_s": round(el_under, 3),
                              "ok": st_under == 200},
            "over_timeout": {"hold_ms": 15000, "status": st_over,
                             "elapsed_s": round(el_over, 3),
                             "killed_non_200": st_over != 200,
                             "killed_near_timeout":
                             abs(el_over - timeout_ms / 1000.0) < 3.0},
        }
    finally:
        bl.docker_stop(name)


def main() -> None:
    srv = start_fixture_server()
    render = f"http://host.docker.internal:{srv.port}/render"
    slow = f"http://host.docker.internal:{srv.port}/slow"
    try:
        print("[H4] resource lifecycle: 30 sequential sessions + proc/zombie scan")
        h4 = h4_resource(render, slow)
        print(f"  sessions_ok={h4['sessions_ok']}/{h4['k_sessions']}  "
              f"detector_saw_chrome={h4['instrument_calibration']['detector_can_see_chrome']}  "
              f"post-run chrome={h4['post_run_procs']['chrome_procs']} "
              f"zombies={h4['post_run_procs']['zombies']}")
        mb = h4["container_mem_bytes"]
        if mb["baseline"] and mb["settle_after_run"]:
            print(f"  mem baseline={mb['baseline']//1048576}MiB "
                  f"peak={ (mb['peak'] or 0)//1048576}MiB "
                  f"settle={mb['settle_after_run']//1048576}MiB")

        print("[H5] TIMEOUT enforcement (TIMEOUT=5000ms)")
        h5 = h5_timeout(slow)
        print(f"  under(2s)->status {h5['under_timeout']['status']}  "
              f"over(15s)->status {h5['over_timeout']['status']} "
              f"@ {h5['over_timeout']['elapsed_s']}s "
              f"(killed_near_timeout={h5['over_timeout']['killed_near_timeout']})")
    finally:
        srv.stop()

    out = {"hypothesis": "H4 resource/session/zombie lifecycle + H5 TIMEOUT kill",
           "image": bl.IMAGE, "h4_resource": h4, "h5_timeout": h5}
    bl.write_artifact(ART, out)


if __name__ == "__main__":
    main()
