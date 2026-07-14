#!/usr/bin/env python3
"""Real-article extraction fidelity DEMO for the trafilatura pack (non-timed).

This is a CAPABILITY DEMONSTRATION with a reproducible artifact, NOT a scored
benchmark: there is no gold-standard corpus here, so no F1 / precision / recall
is computed or claimed. It runs trafilatura's core job -- HTML -> clean article
text + metadata, with site boilerplate (nav / sidebar / footer) removed -- on
two REAL, saved article pages (offline fixtures) and records:

  - extracted body text (.txt) and extracted metadata (.json) per fixture
  - raw HTML bytes vs extracted body bytes (boilerplate compression ratio)
  - which known real-boilerplate markers were dropped vs leaked (drop-check)
  - which metadata fields (title / author / date / sitename / hostname) were hit
  - trafilatura version

NO TIMING is performed anywhere (the machine runs concurrent workloads; timing
would be meaningless). Fixtures are read from disk -- the network is NOT touched
by this script, so the demo is deterministic and re-runnable offline.

Fixtures were fetched once each (see artifacts/logs/fidelity-fetch.log and the
FIXTURES table below for source URL + fetch date + SHA-256). Research material,
not final blog copy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import trafilatura

PROJECT_DIR = Path(__file__).resolve().parents[1]


def _first_existing(*candidates: Path) -> Path:
    """Return the first existing path, else the first candidate (to be created)."""
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


# Layout-portable: works in the working-copy layout (artifacts/fixtures + artifacts/raw)
# and the published-repo layout (fixtures/real + results). Fixtures are read-only inputs;
# results/raw are outputs. Override any of them with env vars if needed.
import os

FIXTURES_DIR = Path(os.environ.get("TRAF_FIXTURES_DIR") or _first_existing(
    PROJECT_DIR / "artifacts" / "fixtures",
    PROJECT_DIR / "fixtures" / "real",
    PROJECT_DIR / "fixtures",
))
RAW = Path(os.environ.get("TRAF_RAW_DIR") or _first_existing(
    PROJECT_DIR / "artifacts" / "raw",
    PROJECT_DIR / "results",
))
RESULTS = Path(os.environ.get("TRAF_RESULTS_DIR") or _first_existing(
    PROJECT_DIR / "artifacts" / "results",
    PROJECT_DIR / "results",
))
RAW.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

# Fixtures: real article pages saved once. source_url + fetched date recorded for
# provenance; sha256 is recomputed at runtime and cross-checked against expected.
FIXTURES = [
    {
        "name": "news_wikipedia_web_scraping",
        "kind": "encyclopedic article",
        "source_url": "https://en.wikipedia.org/wiki/Web_scraping",
        "fetched": "2026-07-14",
        "sha256": "b0d7e4117f4f1d365bc88bc7c09f2a1d8b748a06b47cb734096a77c1741c92cd",
        # Real chrome/boilerplate that should NOT appear in extracted body text.
        # (Substrings chosen to be unique to site chrome, not article prose.)
        "boilerplate_markers": [
            "Jump to content",
            "Privacy policy",
            "Powered by MediaWiki",
            "This page was last edited",
        ],
        # A few article-body phrases that SHOULD survive extraction.
        "body_markers": [
            "Web scraping",
            "HTML",
        ],
    },
    {
        "name": "news_wikinews_7th_heaven",
        "kind": "news article (archived)",
        "source_url": 'https://en.wikinews.org/wiki/"7th_Heaven"_television_series_comes_to_an_end',
        "fetched": "2026-07-14",
        "sha256": "074c414c411f6d7a9f599ae0df7a70c616c5dbb90c124c92b0cd84ab8918ce7c",
        "boilerplate_markers": [
            "Jump to content",
            "Privacy policy",
            "Powered by MediaWiki",
            "This page was last edited",
            "free news source",
        ],
        "body_markers": [
            "7th Heaven",
        ],
    },
]

# Metadata fields we report a hit/miss for. Absence is reported honestly (null),
# never invented.
META_FIELDS = ["title", "author", "date", "sitename", "hostname", "categories", "tags"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_fixture(spec: dict) -> dict:
    html_path = FIXTURES_DIR / f"{spec['name']}.html"
    raw_bytes = html_path.read_bytes()
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    html = raw_bytes.decode("utf-8", errors="replace")

    # Core capability: clean body text (boilerplate removed) + markdown + metadata.
    txt = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
    md = trafilatura.extract(html, output_format="markdown", include_comments=False) or ""
    js = trafilatura.extract(html, output_format="json", with_metadata=True, include_comments=False)
    meta = json.loads(js) if js else {}

    # Persist extraction artifacts.
    (RAW / f"fidelity_{spec['name']}.txt").write_text(txt, encoding="utf-8")
    (RAW / f"fidelity_{spec['name']}.md").write_text(md, encoding="utf-8")
    (RAW / f"fidelity_{spec['name']}.json").write_text(js or "{}", encoding="utf-8")

    raw_len = len(raw_bytes)
    body_len = len(txt.encode("utf-8"))

    # Boilerplate drop-check: which known chrome markers leaked into body text.
    boiler_leaked = [m for m in spec["boilerplate_markers"] if m in txt]
    boiler_dropped = [m for m in spec["boilerplate_markers"] if m not in txt]
    # Body-survival check: article prose markers that should remain.
    body_kept = [m for m in spec["body_markers"] if m in txt]
    body_missing = [m for m in spec["body_markers"] if m not in txt]

    # Metadata field hits (value present + non-empty) reported honestly.
    meta_hits = {}
    for f in META_FIELDS:
        v = meta.get(f)
        meta_hits[f] = bool(v) if not isinstance(v, (int, float)) else True

    return {
        "name": spec["name"],
        "kind": spec["kind"],
        "source_url": spec["source_url"],
        "fetched": spec["fetched"],
        "sha256_expected": spec["sha256"],
        "sha256_actual": actual_sha,
        "sha256_match": actual_sha == spec["sha256"],
        "extraction_succeeded": bool(txt),
        "raw_html_bytes": raw_len,
        "extracted_body_bytes": body_len,
        # ratio of extracted body to raw HTML; smaller = more boilerplate removed.
        "extracted_over_raw_ratio": round(body_len / raw_len, 4) if raw_len else None,
        "boilerplate_markers_checked": spec["boilerplate_markers"],
        "boilerplate_dropped": boiler_dropped,
        "boilerplate_leaked": boiler_leaked,
        "boilerplate_all_dropped": len(boiler_leaked) == 0,
        "body_markers_checked": spec["body_markers"],
        "body_markers_kept": body_kept,
        "body_markers_missing": body_missing,
        "metadata_field_hits": meta_hits,
        "metadata_title": meta.get("title"),
        "metadata_author": meta.get("author"),
        "metadata_date": meta.get("date"),
        "metadata_sitename": meta.get("sitename"),
        "metadata_hostname": meta.get("hostname"),
        "outputs": [
            str((RAW / f"fidelity_{spec['name']}.txt").relative_to(PROJECT_DIR)),
            str((RAW / f"fidelity_{spec['name']}.md").relative_to(PROJECT_DIR)),
            str((RAW / f"fidelity_{spec['name']}.json").relative_to(PROJECT_DIR)),
        ],
    }


def main() -> int:
    summary = {
        "run_started_at": now(),
        "tool": "trafilatura",
        "trafilatura_version": trafilatura.__version__,
        "demo_kind": "real-article extraction fidelity DEMO (non-timed, offline fixtures)",
        "not_a_benchmark": (
            "No gold standard, no F1/precision/recall. This is a reproducible "
            "capability demonstration, not a scored benchmark."
        ),
        "timing_performed": False,
        "network_used_at_runtime": False,
        "fixtures": [],
    }
    for spec in FIXTURES:
        summary["fixtures"].append(run_fixture(spec))
    summary["run_completed_at"] = now()

    out = RESULTS / "trafilatura-fidelity-summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
