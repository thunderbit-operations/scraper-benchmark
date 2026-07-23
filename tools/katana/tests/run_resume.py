#!/usr/bin/env python3
"""Katana resume test: interrupt a crawl, resume it, measure what state is recovered.

Ground truth from katana source (v1.6.1):
  - The resume checkpoint is written to ~/.config/katana/resume-<xid>.cfg (NOT a
    resume.cfg in cwd), created by the SIGINT/SIGTERM handler in cmd/katana/main.go.
  - The persisted RunnerState contains ONLY InFlightUrls, and at the runner level
    those are the INPUT SEED urls (internal/runner/executer.go: Set on start,
    Delete when that seed's whole Crawl() returns). On resume, options.URLs is set
    to those seeds and each is crawled again from scratch. The in-memory per-page
    UniqueFilter is never persisted.

So the honest question this measures: does `-resume` skip already-fetched PAGES
within a seed (fine-grained), or does it restart the whole seed (coarse-grained)?

Method (server-side hit truth, not stdout):
  1. Full uninterrupted baseline crawl -> the complete fetched-path set.
  2. Interrupted run: snapshot ~/.config/katana before; start katana; SIGINT partway;
     wait; find the NEW resume-*.cfg and read its contents.
  3. Resume run: katana -resume <file> against the SAME live fixture (same port, so
     the saved seed URL still resolves); snapshot the resume-run hits.
  4. Computed claims: (a) resume file written; (b) what it stores; (c) whether the
     resume run re-fetches the full baseline set (per-seed restart) or only pending
     pages (per-page skip); (d) union reaches the baseline set.
Everything is computed from run output; nothing is hardcoded.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ground_truth, reset_hits, snapshot_hits, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
KATANA = os.path.expanduser("~/go/bin/katana")
KATANA_CONFIG_DIR = Path(os.path.expanduser("~/.config/katana"))


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


def resume_files() -> set[Path]:
    if not KATANA_CONFIG_DIR.exists():
        return set()
    return set(KATANA_CONFIG_DIR.glob("resume-*.cfg"))


def full_baseline(base_url: str) -> dict[str, int]:
    reset_hits()
    subprocess.run([KATANA, "-u", base_url, "-silent", "-nc", "-duc", "-d", "4"],
                   capture_output=True, text=True, timeout=180)
    return snapshot_hits()


def interrupted_then_resume(base_url: str, interrupt_after: float) -> dict[str, Any]:
    before = resume_files()

    # Phase 1: start a crawl, SIGINT partway so the seed is still in flight.
    reset_hits()
    proc = subprocess.Popen([KATANA, "-u", base_url, "-silent", "-nc", "-duc", "-d", "4"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(interrupt_after)
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    interrupted_hits = snapshot_hits()

    # Discover the resume file katana wrote (new resume-*.cfg in the config dir).
    new_files = sorted(resume_files() - before, key=lambda p: p.stat().st_mtime)
    resume_file = new_files[-1] if new_files else None
    resume_contents = None
    if resume_file is not None:
        try:
            resume_contents = json.loads(resume_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            resume_contents = {"parse_error": str(exc)}

    # Phase 2: resume from the written file (same fixture is still live).
    resume_hits: dict[str, int] = {}
    resume_rc = None
    resume_emitted: list[str] = []
    if resume_file is not None:
        reset_hits()
        r = subprocess.run([KATANA, "-resume", str(resume_file), "-silent", "-nc", "-duc"],
                           capture_output=True, text=True, timeout=180)
        resume_rc = r.returncode
        resume_hits = snapshot_hits()
        resume_emitted = sorted({ln.strip() for ln in r.stdout.splitlines() if ln.strip().startswith("http")})
        # katana removes the resume file on successful completion; clean up if left.
        if resume_file.exists():
            resume_file.unlink()

    return {
        "interrupt_after_seconds": interrupt_after,
        "resume_cfg_written": resume_file is not None,
        "resume_file_name": resume_file.name if resume_file else None,
        "resume_file_contents": resume_contents,
        "interrupted_fetched_paths": sorted(interrupted_hits.keys()),
        "interrupted_fetch_count": sum(interrupted_hits.values()),
        "resume_returncode": resume_rc,
        "resume_fetched_paths": sorted(resume_hits.keys()),
        "resume_fetch_count": sum(resume_hits.values()),
        "resume_emitted_urls": resume_emitted,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(KATANA):
        print("katana missing", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "katana", "base_url": base, "ground_truth": ground_truth(base),
        "resume_file_location": str(KATANA_CONFIG_DIR / "resume-<xid>.cfg"),
    }
    try:
        baseline = full_baseline(base)
        result["full_baseline"] = {
            "distinct_paths": sorted(baseline.keys()),
            "distinct_path_count": len(baseline),
            "total_fetches": sum(baseline.values()),
        }
        rr = interrupted_then_resume(base, interrupt_after=3.0)
        result["interrupt_resume"] = rr

        baseline_paths = set(baseline.keys())
        interrupted_paths = set(rr["interrupted_fetched_paths"])
        resume_paths = set(rr["resume_fetched_paths"])
        union = interrupted_paths | resume_paths
        # Pages that were already fetched before the interrupt and got fetched AGAIN
        # by the resume run == evidence the resume does NOT skip completed pages.
        refetched_completed = sorted(resume_paths & interrupted_paths)
        result["analysis"] = {
            "resume_file_stores_only_inflight_seeds": (
                isinstance(rr["resume_file_contents"], dict)
                and "InFlightUrls" in (rr["resume_file_contents"] or {})
            ),
            "union_covers_baseline": baseline_paths.issubset(union),
            "baseline_minus_union": sorted(baseline_paths - union),
            # If resume re-fetched the full baseline set, it restarted the seed.
            "resume_covers_full_baseline": baseline_paths.issubset(resume_paths),
            "resume_refetched_already_completed_pages": refetched_completed,
            "resume_refetched_count": len(refetched_completed),
            # Granularity verdict, computed from the above.
            "checkpoint_granularity": (
                "per-input-seed (resume re-crawls the whole seed; completed pages are re-fetched)"
                if baseline_paths.issubset(resume_paths) and len(refetched_completed) > 0
                else "per-page-skip (resume avoided re-fetching completed pages)"
                if resume_paths and not (resume_paths & interrupted_paths)
                else "indeterminate"
            ),
        }
        write_json(RAW_DIR / "resume-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
