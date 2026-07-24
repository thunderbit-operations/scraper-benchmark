#!/usr/bin/env python3
"""Scope discipline (adversarial): does browsertrix archive an out-of-scope host?

The fixture home page links `http://outofscope.test:<port>/page/out`, a path on
a DIFFERENT hostname alias that resolves (via docker --add-host) to the SAME
fixture. So a server-side hit whose Host header is `outofscope.test` proves the
out-of-scope host was actually fetched — independent of the archive or logs, and
without any real-internet traffic.

  config 1: --scopeType prefix (default seed-host scope)  -> out-of-scope NOT fetched
  config 2: --scopeType any                               -> out-of-scope IS fetched

config 2 proves the negative in config 1 is real scope discipline (the link is
present and reachable), not merely a link browsertrix failed to discover.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx  # noqa: E402
from fixture_server import reset_hits, snapshot_hits, start_fixture_server  # noqa: E402
from warc_utils import redact  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
CRAWLS_DIR = PROJECT_DIR / "artifacts" / "crawls"
COLLECTIONS_DIR = CRAWLS_DIR / "collections"
IMAGE = os.environ.get("BTRIX_IMAGE", "webrecorder/browsertrix-crawler:latest")
HOST_ALIAS = "host.docker.internal"
OUT_ALIAS = "outofscope.test"
HOME = str(Path.home())
TMP_PREFIXES = (os.environ.get("TMPDIR", "").rstrip("/"), "/var/folders", "/private/var/folders")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(redact(payload, HOME, TMP_PREFIXES), indent=2,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def run_crawl(seed: str, collection: str, scope_type: str) -> dict[str, Any]:
    coll_dir = COLLECTIONS_DIR / collection
    if coll_dir.exists():
        shutil.rmtree(coll_dir)
    cmd = [
        "docker", "run", "--rm",
        "--add-host", f"{HOST_ALIAS}:host-gateway",
        "--add-host", f"{OUT_ALIAS}:host-gateway",
        "--shm-size", "1g",
        "-v", f"{CRAWLS_DIR}:/crawls",
        IMAGE, "crawl",
        "--url", seed,
        "--scopeType", scope_type,
        "--depth", "2",
        "--workers", "1",
        "--collection", collection,
        "--logging", "stats",
    ]
    started = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = round(time.monotonic() - started, 2)
    (LOGS_DIR / f"{collection}.stdout").write_text(p.stdout, encoding="utf-8")
    (LOGS_DIR / f"{collection}.stderr").write_text(p.stderr, encoding="utf-8")
    return {"returncode": p.returncode, "elapsed_seconds": elapsed}


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CRAWLS_DIR.mkdir(parents=True, exist_ok=True)

    # Start fixture with the out-of-scope link enabled (SCOPE_OUT_PORT set to our port).
    server = start_fixture_server()
    port = server.port
    # Re-point the module constants so the home page emits the out-of-scope link.
    fx.EXTERNAL_PORT = str(port)
    seed = f"http://{HOST_ALIAS}:{port}/"

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "browsertrix-crawler",
        "image": IMAGE,
        "seed": seed,
        "out_of_scope_link": f"http://{OUT_ALIAS}:{port}/page/out",
        "configs": {},
    }
    try:
        for cfg, scope_type in [("prefix", "prefix"), ("any", "any")]:
            reset_hits()
            run = run_crawl(seed, f"scope_{cfg}", scope_type)
            hits = snapshot_hits()
            # out-of-scope proof: any hit key "outofscope.test||/page/out"
            out_hit = sum(v for k, v in hits.items()
                          if k.startswith(f"{OUT_ALIAS}||/page/out"))
            in_hits = {k: v for k, v in hits.items() if k.startswith(HOST_ALIAS + "||")}
            summary["configs"][cfg] = {
                "scopeType": scope_type,
                "returncode": run["returncode"],
                "out_of_scope_host_fetched": out_hit > 0,
                "out_of_scope_page_out_hits": out_hit,
                "in_scope_paths_fetched": sorted(p.split("||", 1)[1] for p in in_hits),
            }
        summary["reading"] = (
            "prefix scope must not fetch outofscope.test; any scope must fetch it "
            "(proving the link is reachable and the negative is real discipline)")
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "scope-summary.json", summary)
        print(json.dumps(redact(summary, HOME, TMP_PREFIXES), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
