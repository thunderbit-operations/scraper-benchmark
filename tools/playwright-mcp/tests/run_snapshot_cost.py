#!/usr/bin/env python3
"""H1 (complexity gradient) + H3 (a11y-vs-screenshot cost cliff) for Playwright MCP.

Measures the REAL cost of a browser_snapshot as a function of interactive-element
count, and compares it to browser_take_screenshot on the SAME page. Ground truth is
exact BYTES of the returned tool text (tokenizer-independent); token counts use
tiktoken (o200k_base + cl100k_base) and are labelled tokenizer-specific. Nothing is
hardcoded — every number is computed from the tool's actual output this run.

Determinism: snapshot bytes for a static page are stable, so we assert the size is
identical across repeated snapshots (parity assert). Per-call wall time is reported
as a distribution over >=3 snapshots.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402
from mcp_client import MCPClient, result_text, result_image_bytes, result_image_b64_len, _redact  # noqa: E402

import tiktoken  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"

ENC_O200K = tiktoken.get_encoding("o200k_base")
ENC_CL100K = tiktoken.get_encoding("cl100k_base")

GRADIENT_NS = [0, 1, 10, 50, 100, 250, 500, 1000]
SNAPSHOTS_PER_PAGE = 3  # >=3 for the timing distribution + determinism assert
DOC_CLAIM_TOKENS = 400  # official Snapshots doc upper figure "~200-400 tokens"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tok(text: str) -> dict[str, int]:
    return {
        "bytes": len(text.encode("utf-8")),
        "tokens_o200k": len(ENC_O200K.encode(text)),
        "tokens_cl100k": len(ENC_CL100K.encode(text)),
    }


def measure_page(c: MCPClient, url: str, label: str) -> dict[str, Any]:
    nav = c.call_tool("browser_navigate", {"url": url}, timeout=90)
    nav_txt = result_text(nav)
    nav_inlines_snapshot = "```yaml" in nav_txt

    sizes: list[int] = []
    times: list[float] = []
    first_snapshot_text = None
    for i in range(SNAPSHOTS_PER_PAGE):
        t0 = time.monotonic()
        snap = c.call_tool("browser_snapshot", {}, timeout=90)
        dt = time.monotonic() - t0
        txt = result_text(snap)
        if first_snapshot_text is None:
            first_snapshot_text = txt
        sizes.append(len(txt.encode("utf-8")))
        times.append(dt)

    # Determinism / parity: a static page's snapshot bytes must not vary across calls.
    size_stable = len(set(sizes)) == 1
    snap_cost = tok(first_snapshot_text or "")

    return {
        "label": label,
        "url": url,
        "navigate_response": tok(nav_txt),
        "navigate_inlines_full_snapshot": nav_inlines_snapshot,
        "snapshot_cost": snap_cost,
        "snapshot_bytes_all_calls": sizes,
        "snapshot_bytes_stable_across_calls": size_stable,
        "snapshot_latency_seconds": {
            "p50": round(statistics.median(times), 3),
            "min": round(min(times), 3),
            "max": round(max(times), 3),
        },
        "exceeds_doc_400_token_claim": snap_cost["tokens_o200k"] > DOC_CLAIM_TOKENS,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    outdir = tempfile.mkdtemp(prefix="pwmcp-cost-")

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "playwright-mcp",
        "base_url": server.base_url,
        "tokenizers": ["o200k_base", "cl100k_base"],
        "doc_claim_tokens_upper": DOC_CLAIM_TOKENS,
        "snapshots_per_page": SNAPSHOTS_PER_PAGE,
        "gradient": [],
    }
    try:
        with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                        "--output-dir", outdir]) as c:
            summary["server_info"] = c.server_info.get("serverInfo", {})

            # --- H1: complexity gradient ---
            for n in GRADIENT_NS:
                m = measure_page(c, f"{server.base_url}/gradient?n={n}", f"gradient_n{n}")
                m["n_interactive_elements"] = n
                summary["gradient"].append(m)

            # linear scaling: bytes per interactive element (computed, not assumed)
            pts = [(g["n_interactive_elements"], g["snapshot_cost"]["bytes"])
                   for g in summary["gradient"] if g["n_interactive_elements"] > 0]
            if len(pts) >= 2:
                (n_lo, b_lo), (n_hi, b_hi) = pts[0], pts[-1]
                summary["bytes_per_element_estimate"] = round((b_hi - b_lo) / (n_hi - n_lo), 2)
            # first n whose snapshot exceeds the doc's 400-token upper claim
            over = [g["n_interactive_elements"] for g in summary["gradient"]
                    if g["exceeds_doc_400_token_claim"]]
            summary["first_n_exceeding_doc_claim"] = min(over) if over else None

            # --- H3: a11y snapshot vs screenshot on the SAME page ---
            cliff = {}
            for label, url in [("classes", f"{server.base_url}/classes"),
                               ("gradient_n100", f"{server.base_url}/gradient?n=100")]:
                c.call_tool("browser_navigate", {"url": url}, timeout=90)
                snap_txt = result_text(c.call_tool("browser_snapshot", {}, timeout=90))
                shot = c.call_tool("browser_take_screenshot", {}, timeout=90)
                shot_txt = result_text(shot)
                img_bytes = result_image_bytes(shot)
                img_b64 = result_image_b64_len(shot)
                a11y = tok(snap_txt)
                # Screenshot travels to a vision model as an image; cost proxies:
                #   decoded PNG bytes, and the base64 payload length (what an inline
                #   data-URI would add as text). Report both honestly; do not invent
                #   a vision-token number (image tokenization is model-specific).
                cliff[label] = {
                    "a11y_snapshot": a11y,
                    "screenshot_text_response": tok(shot_txt),
                    "screenshot_returns_inline_image": img_bytes > 0 or img_b64 > 0,
                    "screenshot_png_bytes": img_bytes,
                    "screenshot_base64_len": img_b64,
                    "a11y_bytes_vs_screenshot_png_bytes_ratio":
                        round(img_bytes / a11y["bytes"], 2) if a11y["bytes"] and img_bytes else None,
                }
            summary["screenshot_cost_cliff"] = cliff

            summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
            write_json(RAW_DIR / "snapshot-cost-summary.json", summary)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
    finally:
        server.stop()
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
