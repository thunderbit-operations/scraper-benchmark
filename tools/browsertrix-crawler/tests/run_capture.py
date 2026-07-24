#!/usr/bin/env python3
"""Browsertrix Crawler capture matrix + archival-cost accounting.

Drives the browsertrix-crawler Docker container to crawl the local fixture, then
computes, PER ENDPOINT CLASS, what the real-browser archiver actually captured
into the WARC/WACZ — using three independent instruments so no single one is
taken on faith:
  1. WARC response records  (archive contents = capture truth)
  2. Server-side hit counter (the fixture logs every GET it served)
  3. Archived app.js body    (are class-B literals present in the archive even
     though the endpoints were never fetched?)

Then it accounts for archival artifact cost: on-disk WARC.gz and WACZ size,
WARC record-type composition (how much of the archive is response payload vs
request/metadata/index overhead), and cost per page / per captured response.

Container networking: the fixture binds 0.0.0.0 on the host; the container
reaches it via `host.docker.internal` (added with --add-host=...:host-gateway,
which colima honours). The out-of-scope hostname alias is a second --add-host
pointing at the same gateway, so a Host-header hit proves an out-of-scope fetch
without any real internet traffic.
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
from fixture_server import (  # noqa: E402
    HTML_ENDPOINTS, HTML_DEPTH_CHAIN, JS_LITERAL_ENDPOINTS, RUNTIME_DOM_ENDPOINT,
    RUNTIME_FETCH_ENDPOINT, ground_truth, reset_hits, snapshot_hits, hit_paths,
    start_fixture_server,
)
from warc_utils import (  # noqa: E402
    inventory_from_wacz, inventory_from_warcs, read_warc_gz, iter_warc_records,
    redact,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"
CRAWLS_DIR = PROJECT_DIR / "artifacts" / "crawls"   # gitignored (large binaries)
COLLECTIONS_DIR = CRAWLS_DIR / "collections"        # browsertrix writes here

IMAGE = os.environ.get("BTRIX_IMAGE", "webrecorder/browsertrix-crawler:latest")
HOST_ALIAS = "host.docker.internal"
OUT_ALIAS = "outofscope.test"

HOME = str(Path.home())
TMP_PREFIXES = (os.environ.get("TMPDIR", "").rstrip("/"), "/var/folders", "/private/var/folders")


def write_json(path: Path, payload: Any) -> None:
    red = redact(payload, HOME, TMP_PREFIXES)
    path.write_text(json.dumps(red, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def recall(found_paths, expected) -> dict[str, Any]:
    fs = set(found_paths)
    missing = [e for e in expected if e not in fs]
    return {"found": len(expected) - len(missing), "expected": len(expected),
            "recall": round((len(expected) - len(missing)) / len(expected), 3) if expected else None,
            "missing": missing}


def image_digest() -> str:
    p = subprocess.run(["docker", "image", "inspect", IMAGE, "--format",
                        "{{index .RepoDigests 0}}"], capture_output=True, text=True)
    return (p.stdout or "").strip() or "unknown"


def run_crawl(seed: str, port: int, collection: str, extra: list[str],
              behaviors: str | None) -> dict[str, Any]:
    """Run one browsertrix crawl in a container; return metadata (no secrets)."""
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
        "--scopeType", "prefix",
        "--depth", "4",
        "--workers", "1",
        "--generateWACZ",
        "--collection", collection,
        "--logging", "stats",
    ] + extra
    if behaviors is not None:
        cmd += ["--behaviors", behaviors]

    started = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    elapsed = round(time.monotonic() - started, 2)
    (LOGS_DIR / f"{collection}.stdout").write_text(p.stdout, encoding="utf-8")
    (LOGS_DIR / f"{collection}.stderr").write_text(p.stderr, encoding="utf-8")
    return {"cmd": cmd, "returncode": p.returncode, "elapsed_seconds": elapsed,
            "coll_dir": str(coll_dir)}


def find_archives(collection: str) -> dict[str, Any]:
    coll = COLLECTIONS_DIR / collection
    warcs = sorted((coll / "archive").glob("*.warc.gz")) if (coll / "archive").exists() else []
    waczs = sorted(coll.glob("*.wacz"))
    return {"warcs": warcs, "waczs": waczs}


def archived_appjs_contains_class_b(warc_paths: list[Path]) -> dict[str, Any]:
    """Is /static/app.js archived, and do the class-B literals live in its body?"""
    present_js = False
    literals_found = []
    for wp in warc_paths:
        data = read_warc_gz(wp)
        for rec in iter_warc_records(data):
            if rec.warc_type == "response" and rec.target_uri.endswith("/static/app.js"):
                present_js = True
                body = rec.content
                for lit in JS_LITERAL_ENDPOINTS:
                    if lit.encode() in body and lit not in literals_found:
                        literals_found.append(lit)
    return {"app_js_archived": present_js,
            "class_b_literals_in_archived_js": sorted(literals_found)}


def replay_fidelity(warc_paths: list[Path]) -> dict[str, Any]:
    """Replay-fidelity check: for the dynamically-produced endpoints (C runtime
    DOM link, D runtime fetch), extract the ARCHIVED HTTP response body from the
    WARC and confirm it holds the JSON content the fixture served — i.e. the
    archive stores replayable content, not just an index entry. (Full pywb replay
    rendering is not run here; PARKED — this verifies the bytes exist in-archive.)"""
    targets = {RUNTIME_DOM_ENDPOINT: False, RUNTIME_FETCH_ENDPOINT: False}
    bodies = {}
    for wp in warc_paths:
        for rec in iter_warc_records(read_warc_gz(wp)):
            if rec.warc_type != "response":
                continue
            path = ""
            if rec.target_uri:
                from urllib.parse import urlparse as _up
                path = _up(rec.target_uri).path
            if path in targets:
                body = rec.content
                # archived HTTP response = status line + headers + body; the
                # fixture serves JSON echoing the endpoint path.
                marker = f'"endpoint": "{path}"'.encode()
                targets[path] = marker in body or path.encode() in body.split(b"\r\n\r\n", 1)[-1]
                bodies[path] = len(body)
    return {"class_C_body_in_archive": targets[RUNTIME_DOM_ENDPOINT],
            "class_D_body_in_archive": targets[RUNTIME_FETCH_ENDPOINT],
            "archived_response_bytes": bodies,
            "note": "response body (with JSON payload) present in WARC => replayable content; "
                    "pywb replay-server rendering PARKED"}


def class_capture(response_paths: list[str], server_hits: set[str]) -> dict[str, Any]:
    """Per-class capture: WARC response record present AND server-side fetch."""
    rp = set(response_paths)
    return {
        "A_html": {
            "in_archive": recall(rp, HTML_ENDPOINTS),
            "server_fetched": recall(server_hits, HTML_ENDPOINTS),
        },
        "A_depth_chain": {
            "in_archive": recall(rp, HTML_DEPTH_CHAIN),
            "server_fetched": recall(server_hits, HTML_DEPTH_CHAIN),
        },
        "B_js_literal_never_called": {
            "in_archive": recall(rp, JS_LITERAL_ENDPOINTS),
            "server_fetched": recall(server_hits, JS_LITERAL_ENDPOINTS),
        },
        "C_runtime_dom_link": {
            "in_archive": RUNTIME_DOM_ENDPOINT in rp,
            "server_fetched": RUNTIME_DOM_ENDPOINT in server_hits,
            "path": RUNTIME_DOM_ENDPOINT,
        },
        "D_runtime_fetch": {
            "in_archive": RUNTIME_FETCH_ENDPOINT in rp,
            "server_fetched": RUNTIME_FETCH_ENDPOINT in server_hits,
            "path": RUNTIME_FETCH_ENDPOINT,
        },
    }


def cost_block(inv) -> dict[str, Any]:
    d = inv.to_dict()
    resp_bytes = d["response_bytes_total"] or 0
    pages = d["pages_count"] or 0
    wacz = d["wacz_bytes"] or 0
    warc = d["warc_gz_bytes"] or 0
    def ratio(a, b):
        return round(a / b, 3) if b else None
    d["cost_ratios"] = {
        "wacz_bytes_per_response_byte": ratio(wacz, resp_bytes),
        "warc_gz_bytes_per_response_byte": ratio(warc, resp_bytes),
        "wacz_bytes_per_page": ratio(wacz, pages),
        "warc_gz_bytes_per_page": ratio(warc, pages),
        "response_payload_share_of_warc_content": ratio(
            resp_bytes, sum(d["record_type_content_bytes"].values())),
    }
    return d


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CRAWLS_DIR.mkdir(parents=True, exist_ok=True)

    server = start_fixture_server()
    port = server.port
    seed = f"http://{HOST_ALIAS}:{port}/"
    gt = ground_truth(server.base_url)
    write_json(RAW_DIR / "ground_truth.json", gt)

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "browsertrix-crawler",
        "image": IMAGE,
        "image_digest": image_digest(),
        "seed": seed,
        "fixture_port": port,
        "ground_truth": gt,
        "container_network": {
            "method": "host.docker.internal via --add-host=host.docker.internal:host-gateway (colima)",
            "fixture_bind": "0.0.0.0",
        },
    }

    try:
        reset_hits()
        collection = "capture_default"
        # default behaviors (autoplay,autofetch,autoscroll,siteSpecific) — let the
        # tool run as shipped; we record exactly what it did.
        run = run_crawl(seed, port, collection, extra=[], behaviors=None)
        summary["crawl"] = {k: run[k] for k in ("returncode", "elapsed_seconds")}

        hits = snapshot_hits()
        hpaths = hit_paths()
        (LOGS_DIR / "server_hits.json").write_text(
            json.dumps(hits, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        arch = find_archives(collection)
        warc_paths = arch["warcs"]
        wacz_paths = arch["waczs"]
        summary["archives_found"] = {
            "warc_count": len(warc_paths),
            "warc_names": [p.name for p in warc_paths],
            "wacz_count": len(wacz_paths),
            "wacz_names": [p.name for p in wacz_paths],
        }

        if not warc_paths and not wacz_paths:
            summary["error"] = "no archive produced; see artifacts/logs"
            write_json(RAW_DIR / "capture-summary.json", summary)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 3

        # Inventory: prefer the WACZ (it embeds the WARC + indexes); also account
        # the raw warc for cross-check.
        warc_inv = inventory_from_warcs(warc_paths) if warc_paths else None
        wacz_inv = inventory_from_wacz(wacz_paths[0]) if wacz_paths else None
        # response paths for capture recall: from the WARC inventory (raw) if
        # present, else from the WACZ-embedded WARC.
        inv_for_paths = warc_inv or wacz_inv
        response_paths = inv_for_paths.response_paths

        summary["capture_matrix"] = class_capture(response_paths, hpaths)
        summary["class_b_boundary"] = archived_appjs_contains_class_b(
            warc_paths if warc_paths else [])
        summary["replay_fidelity"] = replay_fidelity(warc_paths if warc_paths else [])
        summary["archival_cost"] = {
            "warc_inventory": cost_block(warc_inv) if warc_inv else None,
            "wacz_inventory": cost_block(wacz_inv) if wacz_inv else None,
        }
        # Scope sanity from this run: no out-of-scope host alias should be fetched
        # (the home page did not link it in this run; the dedicated scope test is
        # run_scope.py).
        summary["server_side_hit_paths"] = sorted(hpaths)

        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "capture-summary.json", summary)
        print(json.dumps(redact(summary, HOME, TMP_PREFIXES), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
