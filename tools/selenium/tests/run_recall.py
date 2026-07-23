#!/usr/bin/env python3
"""H1 — the selenium-idiom x injection-timing recall matrix.

Selenium's `driver.get()` blocks until the load event (default pageLoadStrategy=normal),
so the DEFAULT read `driver.page_source` is an AT-LOAD snapshot — it misses content injected
after load, exactly like chromedp's naive read and rod's `WaitLoad`+`HTML`. Recovering
post-load content is where Selenium's WAIT idioms come in. This runner measures, on the same
fixture the CDP packs used, which content classes (A static / B sync-injected / C
delayed-injected) each selenium idiom recovers, and how the boundary moves with the class-C
delay. The idioms:

  pagesource -> get() (blocks to load) + page_source                    [default read]
  implicit   -> implicitly_wait(20) + get() + find_element(C) + page_source
  explicit   -> get() + WebDriverWait(20).until(presence_of C) + page_source  [idiomatic]
  poll       -> get() + poll page_source until the class-C marker appears

Parity claim under test: Selenium's default `page_source` reads at the load event and misses
class C — same footgun as chromedp's naive read and rod's WaitLoad+HTML. Recovery needs an
EXPLICIT WebDriverWait (parity: chromedp's explicit WaitVisible), where rod's ergonomic
default `Element()` auto-waits with no explicit call. Does implicit_wait recover class C?
(implicit wait only affects element FINDS, not page_source freshness — measured, not
assumed.) Recall is computed HERE (Python) from ground-truth markers vs the rendered
page_source the probe returns — nothing is hardcoded in the probe.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ground_truth, reset_hits, snapshot_hits, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
PROBE = PROJECT_DIR / "tests" / "harness" / "selenium_probe.py"
PY_BIN = os.environ.get("SEL_PY", str(PROJECT_DIR / ".venv" / "bin" / "python"))
DRIVER_PATH = os.environ.get("SEL_DRIVER_PATH", "")  # explicit driver skips Selenium Manager
HOME = str(Path.home())


def _redact(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace(HOME, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_probe(url: str, strategy: str, udd: str, timeout: int = 90) -> dict[str, Any]:
    cmd = [PY_BIN, str(PROBE), "recall", "--url", url, "--strategy", strategy, "--user-data-dir", udd]
    if DRIVER_PATH:
        cmd += ["--driver-path", DRIVER_PATH]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        return {"error": True, "rc": p.returncode, "stderr": p.stderr[-500:], "stdout": p.stdout[-500:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def cleanup(udd: str) -> None:
    subprocess.run(["pkill", "-f", os.path.basename(udd)], capture_output=True)
    shutil.rmtree(udd, ignore_errors=True)


def classify(rendered_html: str, hrefs: list[str], gt: dict[str, Any]) -> dict[str, Any]:
    def found(marker: str) -> bool:
        return marker in rendered_html
    return {
        "A_static": found(gt["A_static_marker"]) and gt["A_static_href"] in hrefs,
        "B_sync_injected": found(gt["B_sync_marker"]) and gt["B_sync_href"] in hrefs,
        "C_delayed_injected": found(gt["C_delayed_marker"]) and gt["C_delayed_href"] in hrefs,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists():
        print(f"probe missing: {PROBE}", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    gt = ground_truth(base)
    write_json(RAW_DIR / "ground_truth.json", gt)

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "selenium",
        "base_url": base,
        "ground_truth": gt,
    }
    tmpdirs: list[str] = []
    try:
        DELAY = 800
        url = f"{base}/classes?delay={DELAY}"
        strategies = ["pagesource", "implicit", "explicit", "poll"]
        matrix: dict[str, Any] = {}
        det: dict[str, list[str]] = {s: [] for s in strategies}
        for rep in range(3):
            for s in strategies:
                udd = tempfile.mkdtemp(prefix="sel_recall_")
                tmpdirs.append(udd)
                reset_hits()
                r = run_probe(url, s, udd)
                cleanup(udd)
                if r.get("error"):
                    matrix.setdefault(s, {"error": r})
                    det[s].append("ERROR")
                    continue
                cls = classify(r.get("outer_html", ""), r.get("hrefs", []), gt)
                sig = ",".join(k for k, v in cls.items() if v)
                det[s].append(sig)
                if rep == 0:
                    matrix[s] = {
                        "delay_ms": DELAY,
                        "elapsed_ms": r.get("elapsed_ms"),
                        "classes_found": cls,
                        "hrefs": r.get("hrefs"),
                        "server_side_hits": snapshot_hits(),
                    }
        summary["recall_matrix_delay800"] = matrix
        summary["determinism_found_sets"] = {
            s: {"runs": det[s], "stable": len(set(det[s])) == 1} for s in strategies
        }

        # Injection-timing gradient: pagesource vs explicit-wait across class-C delay.
        # 'explicit' elapsed should TRACK the delay (proof it truly waited).
        gradient = []
        for delay in [0, 100, 400, 800, 1500]:
            gurl = f"{base}/classes?delay={delay}"
            row: dict[str, Any] = {"delay_ms": delay}
            for s in ["pagesource", "explicit"]:
                udd = tempfile.mkdtemp(prefix="sel_grad_")
                tmpdirs.append(udd)
                r = run_probe(gurl, s, udd)
                cleanup(udd)
                if r.get("error"):
                    row[s] = {"error": r}
                    continue
                cls = classify(r.get("outer_html", ""), r.get("hrefs", []), gt)
                row[s] = {"C_found": cls["C_delayed_injected"], "elapsed_ms": r.get("elapsed_ms")}
            gradient.append(row)
        summary["injection_timing_gradient"] = gradient

        def c_found(s: str) -> bool:
            return bool(matrix.get(s, {}).get("classes_found", {}).get("C_delayed_injected"))
        summary["contrast"] = {
            "C_delayed_found_by": [s for s in strategies if c_found(s)],
            "pagesource_misses_C": not c_found("pagesource"),
            "implicit_wait_finds_C": c_found("implicit"),
            "explicit_wait_finds_C": c_found("explicit"),
            "poll_finds_C": c_found("poll"),
            "note": "Selenium's default page_source reads at the load event and misses class C; "
                    "an explicit WebDriverWait (presence_of) recovers it (idiomatic). Whether "
                    "implicit_wait recovers it is measured here, not assumed — implicit wait "
                    "governs element finds, and page_source is read after the find returns. "
                    "Same at-load footgun as chromedp's naive read / rod's WaitLoad+HTML; the "
                    "recovery idiom (explicit wait) parallels chromedp's explicit WaitVisible.",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "recall-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        for d in tmpdirs:
            cleanup(d)


if __name__ == "__main__":
    raise SystemExit(main())
