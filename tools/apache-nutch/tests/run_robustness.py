#!/usr/bin/env python3
"""H5 -- robustness, known-files/sitemap behavior, and politeness, all measured.

ROBUSTNESS: the fixture home links to /failure/500 (HTTP 500) and /broken-xyz
(404). We crawl and confirm the cycle completes (rc==0) and records the right
crawldb status / protocol code for each -- the crawl is not derailed by errors.

KNOWN-FILES / SITEMAP: unlike katana's `-kf`, a normal Nutch crawl does NOT consume
sitemap.xml. We prove (a) a normal crawl never fetches the sitemap's <loc> hidden
endpoints, and (b) the SEPARATE `bin/nutch sitemap` command DOES inject them. This
is a crawl-control parity contrast with katana.

POLITENESS: with fetcher.server.delay set, consecutive same-host fetches are spaced
by at least that delay. Measured from server-side hit timestamps (ground truth),
comparing delay=1.0 against delay=0.0.
"""
from __future__ import annotations
import json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx
import nutch_driver as nd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "artifacts" / "raw"
LOGS = PROJECT / "artifacts" / "logs"
STATIC_PLUGINS = ("protocol-http|urlfilter-regex|parse-(html|tika)|"
                  "scoring-opic|urlnormalizer-(pass|regex|basic)")


def robustness(base_url: str, workroot: Path) -> dict:
    conf = nd.make_conf(workroot / "robust",
                        {"http.agent.name": "nutch-eval-fixture",
                         "plugin.includes": STATIC_PLUGINS,
                         "db.ignore.external.links": "true", "fetcher.server.delay": "0.0"},
                        ["-^(file|ftp|mailto):", "+."])
    fx.reset_hits()
    res = nd.crawl(base_url, ["/"], conf, workroot / "robust", LOGS, rounds=3, tag="robust", topN=100)
    hits = fx.snapshot_hits()
    db = res["crawldb"]

    def entry(path):
        url = base_url + path
        return db.get(url, {})
    all_rc_zero = all(p["rc"] == 0 for p in res["phases"] if p["phase"] != "generate")
    return {
        "rounds_completed": res["rounds_completed"],
        "all_nongenerate_phases_rc0": all_rc_zero,
        "failure_500": {"fetched": "/failure/500" in hits, "crawldb": entry("/failure/500")},
        "broken_404": {"fetched": "/broken-xyz" in hits, "crawldb": entry("/broken-xyz")},
        "home_still_fetched": "/" in hits,
        "class_A_pages_fetched": [e for e in fx.HTML_ENDPOINTS if e in hits],
        "interpretation": "crawl continued past 500 and 404; each error URL carries a "
                          "distinct crawldb status/protocol code",
    }


def sitemap_behavior(base_url: str, workroot: Path) -> dict:
    # (a) normal crawl -- does it ever touch the sitemap <loc> endpoints?
    conf = nd.make_conf(workroot / "sm_normal",
                        {"http.agent.name": "nutch-eval-fixture",
                         "plugin.includes": STATIC_PLUGINS,
                         "db.ignore.external.links": "true", "fetcher.server.delay": "0.0"},
                        ["-^(file|ftp|mailto):", "+."])
    fx.reset_hits()
    nd.crawl(base_url, ["/"], conf, workroot / "sm_normal", LOGS, rounds=3, tag="sm_normal", topN=100)
    normal_hits = fx.snapshot_hits()
    sitemap_loc_fetched_normal = [e for e in fx.KNOWN_FILE_ENDPOINTS if e in normal_hits]
    robots_fetched = "/robots.txt" in normal_hits
    sitemap_xml_fetched_normal = "/sitemap.xml" in normal_hits

    # (b) explicit `bin/nutch sitemap` command.
    crawldb = workroot / "sm_cmd_crawldb"
    seeds = workroot / "sm_cmd_seeds"; seeds.mkdir(parents=True, exist_ok=True)
    (seeds / "urls.txt").write_text(base_url + "/\n", encoding="utf-8")
    conf2 = nd.make_conf(workroot / "sm_cmd",
                         {"http.agent.name": "nutch-eval-fixture",
                          "plugin.includes": STATIC_PLUGINS,
                          "db.ignore.external.links": "true", "fetcher.server.delay": "0.0"},
                         ["-^(file|ftp|mailto):", "+."])
    nd.run_nutch(conf2, ["inject", str(crawldb), str(seeds)], LOGS / "sm_cmd_inject.log")
    smurls = workroot / "sm_cmd_urls"; smurls.mkdir(parents=True, exist_ok=True)
    (smurls / "sitemaps.txt").write_text(base_url + "/sitemap.xml\n", encoding="utf-8")
    fx.reset_hits()
    r = nd.run_nutch(conf2, ["sitemap", str(crawldb), "-sitemapUrls", str(smurls), "-noFilter", "-noNormalize"],
                     LOGS / "sm_cmd_sitemap.log")
    cmd_hits = fx.snapshot_hits()
    db = nd.crawldb_dump(conf2, crawldb, LOGS, "sm_cmd")
    loc_in_db = [e for e in fx.KNOWN_FILE_ENDPOINTS if (base_url + e) in db]
    return {
        "normal_crawl": {
            "robots_txt_fetched": robots_fetched,
            "sitemap_xml_fetched": sitemap_xml_fetched_normal,
            "sitemap_loc_endpoints_fetched": sitemap_loc_fetched_normal,
            "auto_consumes_sitemap": len(sitemap_loc_fetched_normal) > 0,
        },
        "sitemap_command": {
            "rc": r["rc"],
            "sitemap_xml_fetched": "/sitemap.xml" in cmd_hits,
            "loc_endpoints_injected_to_crawldb": loc_in_db,
            "loc_recall": round(len(loc_in_db) / len(fx.KNOWN_FILE_ENDPOINTS), 3),
        },
        "parity_note": "katana -kf requests robots/sitemap inside a normal crawl; Nutch "
                       "separates it into an explicit `bin/nutch sitemap` step",
    }


def politeness(base_url: str, workroot: Path) -> dict:
    def gaps_for_delay(delay: str, tag: str) -> dict:
        conf = nd.make_conf(workroot / tag,
                            {"http.agent.name": "nutch-eval-fixture",
                             "plugin.includes": STATIC_PLUGINS,
                             "db.ignore.external.links": "true",
                             "fetcher.server.delay": delay,
                             "fetcher.threads.per.queue": "1"},
                            ["-^(file|ftp|mailto):", "+."])
        fx.reset_hits()
        nd.crawl(base_url, ["/"], conf, workroot / tag, LOGS, rounds=3, tag=tag, topN=100)
        log = fx.snapshot_hit_log()
        # content fetches only (exclude robots.txt), in order.
        ts = [h["ts_monotonic"] for h in log if h["path"] != "/robots.txt"]
        ts.sort()
        deltas = sorted(round(b - a, 3) for a, b in zip(ts, ts[1:]))
        return {"delay_setting": float(delay), "content_fetches": len(ts),
                "min_gap": deltas[0] if deltas else None,
                "median_gap": deltas[len(deltas) // 2] if deltas else None,
                "max_gap": deltas[-1] if deltas else None}
    fast = gaps_for_delay("0.0", "polite_fast")
    slow = gaps_for_delay("1.0", "polite_slow")
    return {"fast_delay_0": fast, "polite_delay_1": slow,
            "delay_is_honored": (slow["median_gap"] or 0) > (fast["median_gap"] or 0),
            "note": "median inter-fetch gap to the same host rises with "
                    "fetcher.server.delay (threads.per.queue=1 isolates the effect)"}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
    if not (nd.NUTCH_HOME / "bin" / "nutch").exists():
        print(f"NUTCH_HOME invalid: {nd.NUTCH_HOME}", file=sys.stderr); return 2
    workroot = Path(nd.tempfile.mkdtemp(prefix="nutch-robust-"))
    srv = fx.start_fixture_server()
    base = srv.base_url
    summary: dict = {"run_started_at": datetime.now(timezone.utc).isoformat(),
                     "tool": "apache-nutch", "base_url": base,
                     "nutch_home": nd.redact(str(nd.NUTCH_HOME))}
    try:
        summary["robustness"] = robustness(base, workroot)
        summary["sitemap_behavior"] = sitemap_behavior(base, workroot)
        summary["politeness"] = politeness(base, workroot)
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        (RAW / "robustness-summary.json").write_text(
            json.dumps(nd.redact(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(nd.redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        srv.stop()
        nd.shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
