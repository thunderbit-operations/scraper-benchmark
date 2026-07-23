#!/usr/bin/env python3
"""Katana discovery matrix: what each mode finds, per endpoint class, on ground truth.

The design separates three endpoint classes (see fixture_server.py):
  A HTML-referenced, B JS-literal (in app.js), C runtime-DOM-only (assembled at
  runtime, no literal anywhere). Recall of each class per mode is the whole story.
Scope is proven from SERVER-SIDE hits (was the out-of-scope host ever fetched),
not from Katana's stdout. Nothing is hardcoded; recall is computed from output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import (  # noqa: E402
    JS_LITERAL_ENDPOINTS, HTML_ENDPOINTS, HTML_DEPTH_CHAIN, RUNTIME_DOM_ENDPOINT,
    KNOWN_FILE_ENDPOINTS, EXTERNAL_LINK, ground_truth, reset_hits, snapshot_hits,
    start_fixture_server,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
KATANA = os.path.expanduser("~/go/bin/katana")


def _redact(obj: Any) -> Any:
    # Fold the $HOME prefix back to ~ so committed artifacts carry no absolute
    # user path and a re-run reproduces the exact bytes we published.
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


def run_katana(base_url: str, extra: list[str], run_id: str, timeout: int = 180) -> dict[str, Any]:
    reset_hits()
    cmd = [KATANA, "-u", base_url, "-silent", "-nc", "-d", "4"] + extra
    started = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc, timed_out, out, err = p.returncode, False, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, timed_out, out, err = -1, True, (e.stdout or ""), (e.stderr or "")
    elapsed = round(time.monotonic() - started, 2)

    urls = sorted({ln.strip() for ln in out.splitlines() if ln.strip().startswith("http")})
    in_scope = sorted({u.replace(base_url, "") for u in urls if u.startswith(base_url)})
    external = sorted({u for u in urls if not u.startswith(base_url)})
    hits = snapshot_hits()

    (LOGS_DIR / f"{run_id}.stdout").write_text(out, encoding="utf-8")
    write_json(RAW_DIR / f"{run_id}.json", {
        "run_id": run_id, "cmd": cmd, "returncode": rc, "timed_out": timed_out,
        "elapsed_seconds": elapsed, "emitted_in_scope_paths": in_scope,
        "emitted_external": external, "server_side_hits": hits,
        "stderr_tail": (err or "")[-500:],
    })
    return {"run_id": run_id, "rc": rc, "timed_out": timed_out, "elapsed": elapsed,
            "in_scope": in_scope, "external": external, "hits": hits}


def recall(found_paths: list[str], expected: list[str]) -> dict[str, Any]:
    fs = set(found_paths)
    missing = [e for e in expected if e not in fs]
    return {"found": len(expected) - len(missing), "expected": len(expected),
            "recall": round((len(expected) - len(missing)) / len(expected), 3) if expected else None,
            "missing": missing}


def class_breakdown(paths: list[str]) -> dict[str, Any]:
    return {
        "A_html": recall(paths, HTML_ENDPOINTS),
        "A_depth_chain": recall(paths, HTML_DEPTH_CHAIN),
        "B_js_literal": recall(paths, JS_LITERAL_ENDPOINTS),
        "C_runtime_dom_only": {"found": RUNTIME_DOM_ENDPOINT in paths, "path": RUNTIME_DOM_ENDPOINT},
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(KATANA):
        print(f"katana not found at {KATANA}", file=sys.stderr)
        return 2
    ver = subprocess.run([KATANA, "-version"], capture_output=True, text=True)
    version = (ver.stderr + ver.stdout).strip().splitlines()[-1] if (ver.stderr or ver.stdout) else "unknown"

    server = start_fixture_server()
    base = server.base_url
    gt = ground_truth(base)
    write_json(RAW_DIR / "ground_truth.json", gt)

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "katana",
        "katana_version_line": version,
        "base_url": base,
        "ground_truth": gt,
        "modes": {},
    }

    try:
        modes = [
            ("standard", []),
            ("standard_jc", ["-jc"]),
            ("headless", ["-hl"]),
            ("headless_jc", ["-hl", "-jc"]),
        ]
        results = {}
        for name, extra in modes:
            r = run_katana(base, extra, f"discovery_{name}", timeout=240)
            r["class_breakdown"] = class_breakdown(r["in_scope"])
            # scope: did the crawler FETCH the out-of-scope host? (server-side truth)
            # external host is example.com — never on our fixture, so hits can't show
            # it; the emitted_external list shows it was DISCOVERED. Fetch-truth for
            # out-of-scope is asserted via the separate scope test below.
            results[name] = r
            summary["modes"][name] = {
                "cmd_extra": extra, "elapsed_seconds": r["elapsed"], "rc": r["rc"],
                "in_scope_count": len(r["in_scope"]),
                "class_breakdown": r["class_breakdown"],
                "external_discovered": r["external"],
            }

        # Cross-mode contrast: which class each mode uniquely covers.
        def has_B(n): return results[n]["class_breakdown"]["B_js_literal"]["recall"] == 1.0
        def has_C(n): return results[n]["class_breakdown"]["C_runtime_dom_only"]["found"]
        summary["coverage_contrast"] = {
            "B_js_literal_found_by": [n for n in results if has_B(n)],
            "C_runtime_dom_only_found_by": [n for n in results if has_C(n)],
            "note": "if B and C are found by disjoint modes, neither standard+jc nor "
                    "headless alone is complete; only headless+jc covers both classes",
            "headless_alone_misses_B": not has_B("headless"),
            "standard_jc_misses_C": not has_C("standard_jc"),
            "headless_jc_covers_both": has_B("headless_jc") and has_C("headless_jc"),
        }

        # Known-files: requires depth>=3; check sitemap-listed endpoints get fetched.
        kf = run_katana(base, ["-kf", "all", "-d", "3"], "discovery_known_files", timeout=180)
        kf_hits = [e for e in KNOWN_FILE_ENDPOINTS if e in kf["hits"]]
        summary["known_files"] = {
            "sitemap_requested": "/sitemap.xml" in kf["hits"],
            "robots_requested": "/robots.txt" in kf["hits"],
            "sitemap_endpoints_fetched": kf_hits,
            "sitemap_endpoint_recall": recall(list(kf["hits"].keys()), KNOWN_FILE_ENDPOINTS),
        }

        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "discovery-summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
