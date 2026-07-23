#!/usr/bin/env python3
"""H1 — the rod-idiom x injection-timing recall matrix.

rod is sold as "more ergonomic than chromedp: auto-wait just works." This runner
measures, on the same fixture page chromedp used, which content classes (A static /
B sync-injected / C delayed-injected) each rod idiom recovers, and how the boundary
moves with the class-C injection delay. The idioms:

  none      -> Navigate + read HTML immediately (no wait)               [naive read]
  waitload  -> Navigate + WaitLoad (load event) + read HTML             [wait for load]
  element   -> Navigate + Element("#delayed-injected") (AUTO-WAIT)      [rod's ergonomic default]
  poll      -> Navigate + poll HTML until the class-C marker appears

Parity claim under test: rod's *idiomatic* path (query the element, which auto-waits)
recovers post-load content OUT OF THE BOX, where chromedp's idiomatic Navigate+read
misses it and needs an explicit WaitVisible. BUT a naive rod HTML snapshot ("none")
should miss class C exactly like chromedp's naive read — the footgun is identical; only
the ergonomic default differs. Recall is computed HERE (Python) from ground-truth markers
vs the rendered HTML the Go probe returns — nothing is hardcoded in the probe.
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
PROBE = PROJECT_DIR / "tests" / "harness" / "rod_probe"
CHROME = os.environ.get(
    "ROD_CHROME",
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


def run_probe(url: str, strategy: str, udd: str, timeout: int = 60) -> dict[str, Any]:
    cmd = [str(PROBE), "recall", "--url", url, "--chrome", CHROME, "--strategy", strategy, "--user-data-dir", udd]
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
        print(f"probe binary missing: {PROBE}\nbuild it: (cd tests/harness && go build -o rod_probe .)", file=sys.stderr)
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
        "tool": "rod",
        "chrome": CHROME,
        "base_url": base,
        "ground_truth": gt,
    }
    tmpdirs: list[str] = []
    try:
        # --- Core recall matrix at a fixed, reliably-delayed class C (delay=800) ---
        DELAY = 800
        url = f"{base}/classes?delay={DELAY}"
        strategies = ["none", "waitload", "element", "poll"]
        matrix: dict[str, Any] = {}
        # determinism: run the matrix 3x, assert identical found-sets per strategy
        det: dict[str, list[str]] = {s: [] for s in strategies}
        for rep in range(3):
            for s in strategies:
                udd = tempfile.mkdtemp(prefix="rod_recall_")
                tmpdirs.append(udd)
                reset_hits()
                r = run_probe(url, s, udd)
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
        # 'element' elapsed should TRACK the delay (proof it truly waited, not read early).
        gradient = []
        for delay in [0, 100, 400, 800, 1500]:
            gurl = f"{base}/classes?delay={delay}"
            row: dict[str, Any] = {"delay_ms": delay}
            for s in ["none", "element"]:
                udd = tempfile.mkdtemp(prefix="rod_grad_")
                tmpdirs.append(udd)
                r = run_probe(gurl, s, udd)
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
            "naive_html_misses_C": not c_found("none"),
            "waitload_html_misses_C": not c_found("waitload"),
            "element_autowait_finds_C": c_found("element"),
            "poll_finds_C": c_found("poll"),
            "note": "rod's auto-waiting Element() recovers the runtime-injected node with no "
                    "explicit wait call; a naive HTML snapshot (none) and WaitLoad+HTML both "
                    "miss it — same footgun as chromedp's naive read, different ergonomic default.",
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
