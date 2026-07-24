#!/usr/bin/env python3
"""Heritrix archival-crawl-discipline evidence harness.

Focus: measure *archival crawl discipline + output boundaries* on controlled
ground truth — WARC record fidelity, content-digest dedup boundary, SURT scope
discipline, default politeness cost, and robots.txt obedience — NOT consumer
scraping features.

One Heritrix engine (managed) drives five controlled jobs against a local fixture
whose endpoint set is known, so every claim is measured against ground truth or a
server-side hit counter, never Heritrix's own stdout alone. Each concern writes a
JSON artifact under artifacts/raw/; observation/verdict fields are COMPUTED from
run output (no hardcoded conclusions).

Run:  .venv/bin/python tests/run_all.py         (or plain python3; stdlib only + curl)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixture_server as fx          # noqa: E402
import heritrix_driver as hd         # noqa: E402

PROJECT_DIR = HERE.parent
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
HOME = PROJECT_DIR / "vendor" / "heritrix-3.16.0"
CONTACT = "http://localhost/benchmark-archival-discipline-contact"


# --------------------------------------------------------------------------- #
# dedup-enabled config: add content-digest history loader/storer + bdb store so
# identical-digest content yields a WARC `revisit` record (classes verified to
# exist in heritrix-modules jar: BdbContentDigestHistory / ContentDigestHistory
# Loader / ContentDigestHistoryStorer).
# --------------------------------------------------------------------------- #
def enable_dedup(cxml: str) -> str:
    beans = (
        '<bean id="contentDigestHistory" class="org.archive.modules.recrawl.BdbContentDigestHistory"/>\n'
        ' <bean id="contentDigestHistoryLoader" class="org.archive.modules.recrawl.ContentDigestHistoryLoader"/>\n'
        ' <bean id="contentDigestHistoryStorer" class="org.archive.modules.recrawl.ContentDigestHistoryStorer"/>\n'
    )
    # define beans just before the fetch chain
    cxml = cxml.replace(
        ' <bean id="fetchProcessors" class="org.archive.modules.FetchChain">',
        " " + beans + ' <bean id="fetchProcessors" class="org.archive.modules.FetchChain">')
    # loader at the end of the fetch chain (digest known before disposition writer)
    cxml = cxml.replace(
        '    <!-- <ref bean="browser"/> -->\n   </list>',
        '    <!-- <ref bean="browser"/> -->\n    <ref bean="contentDigestHistoryLoader"/>\n   </list>')
    # storer immediately after the warc writer in the disposition chain
    cxml = cxml.replace(
        '    <ref bean="warcWriter"/>\n',
        '    <ref bean="warcWriter"/>\n    <ref bean="contentDigestHistoryStorer"/>\n', 1)
    return cxml


def _iso(ts: str) -> float:
    # crawl.log timestamps look like 2026-07-24T06:00:10.574Z
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _same_host_gaps(rows: list[dict[str, Any]], host: str) -> list[float]:
    ts = sorted(_iso(r["timestamp"]) for r in rows
                if isinstance(r.get("status"), int) and r["status"] == 200 and host in r["uri"])
    return [round((b - a) * 1000, 1) for a, b in zip(ts, ts[1:])]


# --------------------------------------------------------------------------- #
# Concern 1 — WARC record fidelity (output boundary)
# --------------------------------------------------------------------------- #
def concern_warc_fidelity(eng: hd.Engine, base_cxml: str, seed: str) -> dict[str, Any]:
    cxml = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT)
    d = hd.run_crawl(eng, "warc-fidelity", cxml)
    recs = hd.parse_warc_records(d)
    types = Counter(r["type"] for r in recs)
    responses = [r for r in recs if r["type"] == "response"]
    requests = [r for r in recs if r["type"] == "request"]
    # linkage: every response should be WARC-Concurrent-To a request (or vice-versa)
    resp_ids = {r["record_id"] for r in responses}
    req_concurrent = sum(1 for r in requests if r["concurrent_to"] in resp_ids)
    result = {
        "job": "warc-fidelity", "launch_dir": str(d),
        "record_type_counts": dict(types),
        "warcinfo_present": types.get("warcinfo", 0) >= 1,
        "response_records": len(responses),
        "request_records": len(requests),
        "metadata_records": types.get("metadata", 0),
        "responses_with_payload_digest": sum(1 for r in responses if r["payload_digest"].startswith("sha1:")),
        "responses_with_ip": sum(1 for r in responses if r["ip"]),
        "requests_concurrent_to_a_response": req_concurrent,
        "response_status_lines_sample": sorted({r["http_first_line"] for r in responses})[:6],
        "request_line_style": next((r["http_first_line"] for r in requests), ""),
    }
    result["observation"] = {
        "default_profile_emits_request_and_response": len(requests) > 0 and len(responses) > 0,
        "every_response_has_sha1_payload_digest": result["responses_with_payload_digest"] == len(responses) and len(responses) > 0,
        "every_response_has_ip": result["responses_with_ip"] == len(responses) and len(responses) > 0,
        "request_response_fully_linked": req_concurrent == len(requests) and len(requests) > 0,
    }
    hd.teardown_job(eng, "warc-fidelity")
    hd.write_json(RAW_DIR / "warc-fidelity.json", result)
    return result


# --------------------------------------------------------------------------- #
# Concern 2 — content-digest dedup boundary (adversarial, output boundary)
# --------------------------------------------------------------------------- #
def _dup_stats(recs: list[dict[str, Any]], dup_paths: list[str]) -> dict[str, Any]:
    dup = [r for r in recs if any(p in r["target_uri"] for p in dup_paths)]
    resp = [r for r in dup if r["type"] == "response"]
    revisit = [r for r in dup if r["type"] == "revisit"]
    digests = Counter(r["payload_digest"] for r in resp if r["payload_digest"])
    return {
        "dup_urls_seen": sorted({r["target_uri"] for r in dup}),
        "dup_response_records": len(resp),
        "dup_revisit_records": len(revisit),
        "identical_payload_digest_shared": max(digests.values()) if digests else 0,
        "revisit_profiles": sorted({r["profile"] for r in revisit if r["profile"]}),
    }


def concern_dedup(eng: hd.Engine, base_cxml: str, seed: str) -> dict[str, Any]:
    dup_paths = fx.DUP_ENDPOINTS
    # default profile
    cxml_def = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT)
    d1 = hd.run_crawl(eng, "dedup-default", cxml_def)
    def_stats = _dup_stats(hd.parse_warc_records(d1), dup_paths)
    hd.teardown_job(eng, "dedup-default")
    # dedup-enabled profile
    cxml_dd = enable_dedup(hd.template_cxml(base_cxml, seed=seed, contact=CONTACT))
    d2 = hd.run_crawl(eng, "dedup-enabled", cxml_dd)
    dd_stats = _dup_stats(hd.parse_warc_records(d2), dup_paths)
    hd.teardown_job(eng, "dedup-enabled")
    result = {
        "dup_paths": dup_paths, "default": def_stats, "dedup_enabled": dd_stats,
        "observation": {
            "default_writes_full_duplicate_responses": def_stats["dup_response_records"] >= 2 and def_stats["dup_revisit_records"] == 0,
            "both_dup_urls_share_one_digest": def_stats["identical_payload_digest_shared"] >= 2,
            "enabling_chain_produces_revisit": dd_stats["dup_revisit_records"] >= 1,
            "revisit_reduces_full_responses": dd_stats["dup_response_records"] < def_stats["dup_response_records"],
        },
    }
    hd.write_json(RAW_DIR / "dedup.json", result)
    return result


# --------------------------------------------------------------------------- #
# Concern 3 — SURT scope discipline (parity axis with katana; server-side truth)
# --------------------------------------------------------------------------- #
def concern_scope(eng: hd.Engine, base_cxml: str, primary_base: str, secondary_base: str) -> dict[str, Any]:
    seed = f"{primary_base}/scope-seed"
    # default scope (SURT from seed host)
    fx.reset_hits()
    cxml = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT)
    d = hd.run_crawl(eng, "scope-default", cxml)
    hits = fx.snapshot_hits()
    log = hd.parse_crawl_log(d)
    secondary_fetched = hits.get("/page/out", 0) > 0
    emitted_secondary = any("/page/out" in r["uri"] for r in log)
    hd.teardown_job(eng, "scope-default")
    result = {
        "seed": seed, "primary": primary_base, "secondary": secondary_base,
        "page_out_hits_on_secondary": hits.get("/page/out", 0),
        "in_scope_page_a_hits": hits.get("/page/a", 0),
        "secondary_host_fetched": secondary_fetched,
        "secondary_appeared_in_crawl_log": emitted_secondary,
        "observation": {
            "default_surt_scope_excludes_other_host": not secondary_fetched,
            "in_scope_host_still_crawled": hits.get("/page/a", 0) > 0,
        },
    }
    hd.write_json(RAW_DIR / "scope.json", result)
    return result


# --------------------------------------------------------------------------- #
# Concern 4 — default politeness cost (archival crawl discipline)
# --------------------------------------------------------------------------- #
def _crawl_wall_ms(rows: list[dict[str, Any]]) -> float:
    ts = sorted(_iso(r["timestamp"]) for r in rows)
    return round((ts[-1] - ts[0]) * 1000, 1) if len(ts) >= 2 else 0.0


def concern_politeness(eng: hd.Engine, base_cxml: str, seed: str, host: str, runs: int = 3) -> dict[str, Any]:
    modes = {
        # profile defaults are delayFactor 5.0 / minDelayMs 3000 / maxDelayMs 30000
        "default_politeness": dict(delay_factor=5.0, min_delay_ms=3000, max_delay_ms=30000),
        "zero_politeness": dict(delay_factor=0.0, min_delay_ms=0, max_delay_ms=0),
    }
    out: dict[str, Any] = {"host": host, "runs_per_mode": runs, "modes": {}}
    for mode, pol in modes.items():
        wall, gaps_all = [], []
        for i in range(runs):
            cxml = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT, **pol)
            job = f"polite-{mode}-{i}"
            d = hd.run_crawl(eng, job, cxml, poll_timeout=240)
            rows = hd.parse_crawl_log(d)
            wall.append(_crawl_wall_ms(rows))
            gaps_all.append(_same_host_gaps(rows, host))
            hd.teardown_job(eng, job)
        flat_gaps = sorted(g for run in gaps_all for g in run)
        out["modes"][mode] = {
            "wall_ms_runs": wall,
            "wall_ms_min": min(wall), "wall_ms_max": max(wall),
            "wall_ms_median": sorted(wall)[len(wall) // 2],
            "same_host_gap_ms_median": (flat_gaps[len(flat_gaps) // 2] if flat_gaps else None),
            "same_host_gap_ms_min": (flat_gaps[0] if flat_gaps else None),
            "same_host_gap_ms_max": (flat_gaps[-1] if flat_gaps else None),
            "n_gaps": len(flat_gaps),
        }
    dm = out["modes"]["default_politeness"]["wall_ms_median"]
    zm = out["modes"]["zero_politeness"]["wall_ms_median"] or 1
    out["observation"] = {
        "default_median_gap_near_min_delay_3000ms": (
            out["modes"]["default_politeness"]["same_host_gap_ms_median"] is not None
            and out["modes"]["default_politeness"]["same_host_gap_ms_median"] >= 2500),
        "default_wall_time_multiplier_over_zero": round(dm / zm, 1),
    }
    hd.write_json(RAW_DIR / "politeness.json", out)
    return out


# --------------------------------------------------------------------------- #
# Concern 5 — robots.txt obedience (adversarial; server-side truth)
# --------------------------------------------------------------------------- #
def concern_robots(eng: hd.Engine, base_cxml: str, seed: str) -> dict[str, Any]:
    denied = fx.ROBOTS_DENIED_ENDPOINT
    # obey (default)
    fx.reset_hits()
    cxml_obey = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT)
    d1 = hd.run_crawl(eng, "robots-obey", cxml_obey)
    hits_obey = fx.snapshot_hits()
    log1 = hd.parse_crawl_log(d1)
    hd.teardown_job(eng, "robots-obey")
    # ignore (control): robotsPolicyName=ignore -> should now fetch the denied path
    fx.reset_hits()
    cxml_ignore = hd.template_cxml(base_cxml, seed=seed, contact=CONTACT).replace(
        '<!-- <property name="robotsPolicyName" value="obey"/> -->',
        '<property name="robotsPolicyName" value="ignore"/>')
    d2 = hd.run_crawl(eng, "robots-ignore", cxml_ignore)
    hits_ignore = fx.snapshot_hits()
    hd.teardown_job(eng, "robots-ignore")
    result = {
        "denied_path": denied, "robots_txt_disallow": "/robots-denied/",
        "obey_mode": {
            "denied_path_server_hits": hits_obey.get(denied, 0),
            "robots_txt_fetched": hits_obey.get("/robots.txt", 0) > 0,
            "denied_in_crawl_log_as_blocked": any(
                denied in r["uri"] and isinstance(r.get("status"), int) and r["status"] < 0 for r in log1),
        },
        "ignore_mode": {
            "denied_path_server_hits": hits_ignore.get(denied, 0),
        },
        "observation": {
            "obey_suppresses_disallowed_fetch": hits_obey.get(denied, 0) == 0,
            "ignore_reaches_disallowed_path": hits_ignore.get(denied, 0) > 0,
            "robots_txt_actually_requested": hits_obey.get("/robots.txt", 0) > 0,
        },
    }
    hd.write_json(RAW_DIR / "robots.json", result)
    return result


# --------------------------------------------------------------------------- #
def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not (HOME / "bin" / "heritrix").exists():
        print(f"Heritrix not found at {HOME}; see README to download into vendor/.", file=sys.stderr)
        return 2

    primary = fx.start_fixture_server()
    secondary = fx.start_fixture_server()
    secondary_base = f"http://localhost:{secondary.base_url.rsplit(':', 1)[1]}"
    os.environ["SCOPE_SECONDARY_URL"] = secondary_base
    seed = f"{primary.base_url}/"
    host = primary.base_url.split("//", 1)[1]  # 127.0.0.1:<port>

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "heritrix", "primary": primary.base_url, "secondary": secondary_base,
    }
    try:
        with hd.managed_engine(HOME) as eng:
            summary["heritrix_version"] = eng.version
            base_cxml = hd.get_baseline_cxml(eng)
            hd.write_json(RAW_DIR / "ground_truth.json", fx.ground_truth(primary.base_url))
            summary["warc_fidelity"] = concern_warc_fidelity(eng, base_cxml, seed)["observation"]
            summary["dedup"] = concern_dedup(eng, base_cxml, seed)["observation"]
            summary["scope"] = concern_scope(eng, base_cxml, primary.base_url, secondary_base)["observation"]
            summary["politeness"] = concern_politeness(eng, base_cxml, seed, host)["observation"]
            summary["robots"] = concern_robots(eng, base_cxml, seed)["observation"]
        hd.write_json(RAW_DIR / "summary.json", summary)
        print(json.dumps(hd.redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        primary.stop()
        secondary.stop()


if __name__ == "__main__":
    raise SystemExit(main())
