#!/usr/bin/env python3
"""H1 — the wait-strategy x injection-timing recall matrix.

A chromedp live browser surfaces runtime-injected DOM content that a static crawler
misses, BUT only with the correct wait action. This runner measures, on the same
fixture page, which content classes (A static / B sync-injected / C delayed-injected)
each wait strategy recovers, and how the boundary moves with the class-C injection
delay. Recall is computed HERE (Python) from the fixture's ground-truth markers vs the
rendered outerHTML the Go probe returns — nothing is hardcoded in the probe.

Server-side hit-truth records which leaf paths Chrome actually fetched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ground_truth, reset_hits, snapshot_hits, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
PROBE = PROJECT_DIR / "tests" / "harness" / "chromedp_probe"
CHROME = os.environ.get(
    "CHROMEDP_CHROME",
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-1232/"
        "chrome-headless-shell-mac-arm64/chrome-headless-shell"
    ),
)


def _redact(obj: Any) -> Any:
    home = str(Path.home())
    if isinstance(obj, str):
        return obj.replace(home, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_probe(sub: str, url: str, strategy: str, udd: str, timeout: int = 60) -> dict[str, Any]:
    cmd = [str(PROBE), sub, "--url", url, "--chrome", CHROME, "--strategy", strategy, "--user-data-dir", udd]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        return {"error": True, "rc": p.returncode, "stderr": p.stderr[-500:], "stdout": p.stdout[-500:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def classify(rendered_html: str, hrefs: list[str], gt: dict[str, Any]) -> dict[str, Any]:
    # Recall computed from ground-truth markers + hrefs against the rendered DOM.
    def found(marker: str) -> bool:
        return marker in rendered_html
    return {
        "A_static": found(gt["A_static_marker"]) and gt["A_static_href"] in hrefs,
        "B_sync_injected": found(gt["B_sync_marker"]) and gt["B_sync_href"] in hrefs,
        "C_delayed_injected": found(gt["C_delayed_marker"]) and gt["C_delayed_href"] in hrefs,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists():
        print(f"probe binary missing: {PROBE}\nbuild it: (cd tests/harness && go build -o chromedp_probe .)", file=sys.stderr)
        return 2
    if not os.path.exists(CHROME):
        print(f"chrome not found at {CHROME}", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    gt = ground_truth(base)
    write_json(RAW_DIR / "ground_truth.json", gt)

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "chromedp",
        "chrome": CHROME,
        "base_url": base,
        "ground_truth": gt,
    }
    tmpdirs: list[str] = []
    try:
        # --- Core recall matrix at a fixed, reliably-delayed class C (delay=800) ---
        DELAY = 800
        url = f"{base}/classes?delay={DELAY}"
        strategies = ["none", "waitready", "waitvisible", "poll"]
        matrix: dict[str, Any] = {}
        # determinism: run the matrix 3x, assert identical found-sets per strategy
        det: dict[str, list[str]] = {s: [] for s in strategies}
        for rep in range(3):
            for s in strategies:
                udd = tempfile.mkdtemp(prefix="chromedp_recall_")
                tmpdirs.append(udd)
                reset_hits()
                r = run_probe("recall", url, s, udd)
                if r.get("error"):
                    matrix[s] = {"error": r}
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

        # --- Injection-timing gradient: how the boundary moves with class-C delay ---
        gradient = []
        for delay in [0, 100, 400, 800, 1500]:
            gurl = f"{base}/classes?delay={delay}"
            row: dict[str, Any] = {"delay_ms": delay}
            for s in ["none", "waitvisible"]:
                udd = tempfile.mkdtemp(prefix="chromedp_grad_")
                tmpdirs.append(udd)
                r = run_probe("recall", gurl, s, udd)
                if r.get("error"):
                    row[s] = {"error": r}
                    continue
                cls = classify(r.get("outer_html", ""), r.get("hrefs", []), gt)
                row[s] = {"C_found": cls["C_delayed_injected"], "elapsed_ms": r.get("elapsed_ms")}
            gradient.append(row)
        summary["injection_timing_gradient"] = gradient

        # --- Cross-strategy contrast (computed, not asserted) ---
        def c_found(s: str) -> bool:
            return bool(matrix.get(s, {}).get("classes_found", {}).get("C_delayed_injected"))
        summary["contrast"] = {
            "C_delayed_found_by": [s for s in strategies if c_found(s)],
            "naive_navigate_misses_C": not c_found("none"),
            "waitready_body_misses_C": not c_found("waitready"),
            "waitvisible_node_finds_C": c_found("waitvisible"),
            "poll_finds_C": c_found("poll"),
            "note": "A live browser sees the runtime-injected node only with a wait keyed "
                    "to that node; Navigate (returns on load) and WaitReady(body) both miss it.",
        }

        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "recall-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        for d in tmpdirs:
            subprocess.run(["pkill", "-f", d], capture_output=True)
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
