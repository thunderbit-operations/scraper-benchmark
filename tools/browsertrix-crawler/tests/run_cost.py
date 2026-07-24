#!/usr/bin/env python3
"""Archival-cost + wall-time distribution over >=3 isolated browsertrix crawls.

Same fixture, same command, N independent container runs. Reports the
distribution (min/median/max) of: crawl wall time, on-disk WARC.gz bytes, WACZ
bytes, captured response payload bytes, and the derived cost ratios — so the
archival-cost headline is a distribution, not a single number. Ranges that
overlap are called a tie by the reader; we do not bold a winner (there is no
comparison here, just spread).
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import reset_hits, start_fixture_server  # noqa: E402
from warc_utils import inventory_from_wacz, inventory_from_warcs, redact  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
CRAWLS_DIR = PROJECT_DIR / "artifacts" / "crawls"
COLLECTIONS_DIR = CRAWLS_DIR / "collections"
IMAGE = os.environ.get("BTRIX_IMAGE", "webrecorder/browsertrix-crawler:latest")
HOST_ALIAS = "host.docker.internal"
RUNS = int(os.environ.get("BTRIX_COST_RUNS", "3"))
HOME = str(Path.home())
TMP_PREFIXES = (os.environ.get("TMPDIR", "").rstrip("/"), "/var/folders", "/private/var/folders")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(redact(payload, HOME, TMP_PREFIXES), indent=2,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def one_run(seed: str, collection: str) -> dict[str, Any]:
    coll_dir = COLLECTIONS_DIR / collection
    if coll_dir.exists():
        shutil.rmtree(coll_dir)
    cmd = [
        "docker", "run", "--rm",
        "--add-host", f"{HOST_ALIAS}:host-gateway",
        "--shm-size", "1g",
        "-v", f"{CRAWLS_DIR}:/crawls",
        IMAGE, "crawl",
        "--url", seed, "--scopeType", "prefix", "--depth", "4",
        "--workers", "1", "--generateWACZ", "--collection", collection,
        "--logging", "stats",
    ]
    t0 = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    elapsed = round(time.monotonic() - t0, 2)
    warcs = sorted((coll_dir / "archive").glob("*.warc.gz"))
    waczs = sorted(coll_dir.glob("*.wacz"))
    winv = inventory_from_warcs(warcs).to_dict() if warcs else {}
    zinv = inventory_from_wacz(waczs[0]).to_dict() if waczs else {}
    return {
        "collection": collection, "returncode": p.returncode, "elapsed_seconds": elapsed,
        "warc_gz_bytes": winv.get("warc_gz_bytes", 0),
        "wacz_bytes": zinv.get("wacz_bytes", 0),
        "response_bytes_total": winv.get("response_bytes_total", 0),
        "response_record_count": winv.get("response_record_count", 0),
        "pages_count": zinv.get("pages_count"),
        "record_type_content_bytes": winv.get("record_type_content_bytes", {}),
    }


def dist(vals: list[float]) -> dict[str, Any]:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {}
    return {"min": min(vals), "median": statistics.median(vals), "max": max(vals),
            "n": len(vals)}


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CRAWLS_DIR.mkdir(parents=True, exist_ok=True)

    server = start_fixture_server()
    seed = f"http://{HOST_ALIAS}:{server.port}/"
    runs = []
    try:
        for i in range(RUNS):
            reset_hits()
            runs.append(one_run(seed, f"cost_run_{i}"))
    finally:
        server.stop()

    summary = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "browsertrix-crawler", "image": IMAGE, "seed": seed,
        "runs": RUNS, "per_run": runs,
        "distributions": {
            "elapsed_seconds": dist([r["elapsed_seconds"] for r in runs]),
            "warc_gz_bytes": dist([r["warc_gz_bytes"] for r in runs]),
            "wacz_bytes": dist([r["wacz_bytes"] for r in runs]),
            "response_bytes_total": dist([r["response_bytes_total"] for r in runs]),
        },
    }
    # median-based cost ratios (reported as ratio of medians; per-run spread above)
    med_resp = summary["distributions"]["response_bytes_total"].get("median") or 0
    med_warc = summary["distributions"]["warc_gz_bytes"].get("median") or 0
    med_wacz = summary["distributions"]["wacz_bytes"].get("median") or 0
    med_pages = statistics.median([r["pages_count"] for r in runs if r["pages_count"]]) \
        if any(r["pages_count"] for r in runs) else 0

    def ratio(a, b):
        return round(a / b, 3) if b else None
    summary["cost_ratios_of_medians"] = {
        "warc_gz_bytes_per_response_byte": ratio(med_warc, med_resp),
        "wacz_bytes_per_response_byte": ratio(med_wacz, med_resp),
        "warc_gz_bytes_per_page": ratio(med_warc, med_pages),
        "wacz_bytes_per_page": ratio(med_wacz, med_pages),
    }
    summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(RAW_DIR / "cost-summary.json", summary)
    print(json.dumps(redact(summary, HOME, TMP_PREFIXES), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
