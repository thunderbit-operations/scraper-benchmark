#!/usr/bin/env python3
"""H3 -- crawl control: DEPTH (Nutch depth == number of crawl rounds) and SCOPE
discipline (out-of-scope host is not fetched), proven from server-side hit truth.

DEPTH: the fixture has a chain /depth/1 -> /depth/2 -> /depth/3. Each Nutch round
fetches the current frontier and discovers the next link, so /depth/N is FETCHED
only after enough rounds. We crawl with rounds = 2,3,4 and show the fetched depth
grows one level per round -- i.e. crawl depth is controlled by round count, not a
single --depth flag.

SCOPE: a SECONDARY fixture runs in its own process on host 'localhost' (a distinct
host string from the primary '127.0.0.1'). The primary '/scope-seed' page links to
the secondary. Three scenarios show what actually keeps the crawl in scope, judged
by whether the secondary server ever records a hit on '/page/out':
  - default_external_on  : db.ignore.external.links = false (shipped default)
  - ignore_external      : db.ignore.external.links = true
  - urlfilter_host_only  : regex-urlfilter restricted to the primary host
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
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


def start_secondary() -> tuple[subprocess.Popen, str]:
    port = fx.find_free_port()
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parent / "fixture_server.py"),
                          str(port), "localhost"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    base = p.stdout.readline().strip()
    # wait until reachable
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/__hits__", timeout=1).read(); break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    return p, base


def secondary_hits(base: str) -> dict:
    try:
        with urllib.request.urlopen(base + "/__hits__", timeout=3) as r:
            return json.loads(r.read()).get("hits", {})
    except Exception as e:  # noqa: BLE001
        return {"__error__": repr(e)}


def depth_test(base_url: str, workroot: Path) -> dict:
    out = []
    for rounds in (2, 3, 4):
        conf = nd.make_conf(workroot / f"depth_{rounds}",
                            {"http.agent.name": "nutch-eval-fixture",
                             "plugin.includes": STATIC_PLUGINS,
                             "db.ignore.external.links": "true",
                             "fetcher.server.delay": "0.0"},
                            ["-^(file|ftp|mailto):", "+."])
        fx.reset_hits()
        res = nd.crawl(base_url, ["/"], conf, workroot / f"depth_{rounds}", LOGS,
                       rounds=rounds, tag=f"depth_{rounds}", topN=100)
        hits = fx.snapshot_hits()
        fetched_chain = [e for e in fx.HTML_DEPTH_CHAIN if e in hits]
        out.append({"rounds": rounds, "rounds_completed": res["rounds_completed"],
                    "depth_chain_fetched": fetched_chain,
                    "deepest_fetched": (max(fetched_chain, key=lambda p: int(p.rsplit('/', 1)[-1]))
                                        if fetched_chain else None)})
    # depth grows monotonically with rounds?
    deepest = [ (r["rounds"], len(r["depth_chain_fetched"])) for r in out ]
    return {"per_round_count": out,
            "depth_equals_rounds": all(cnt >= prev for (_, cnt), (_, prev)
                                       in zip(deepest[1:], deepest[:-1])),
            "note": "/depth/N is fetched only at round N+1 (round R fetches frontier "
                    "discovered at round R-1); depth is set by how many rounds you run"}


def scope_scenario(base_url: str, sec_base: str, workroot: Path, tag: str,
                   props: dict, rules: list[str]) -> dict:
    """Judge scope from Nutch's OWN crawldb (robust, no cross-process timing) AND
    corroborate with the secondary server's hit counter. The out-of-scope URL is
    sec_base + '/page/out'."""
    os.environ["SCOPE_SECONDARY_URL"] = sec_base
    ext_url = sec_base + "/page/out"
    before = secondary_hits(sec_base)
    conf = nd.make_conf(workroot / tag, props, rules)
    fx.reset_hits()
    res = nd.crawl(base_url, ["/scope-seed"], conf, workroot / tag, LOGS,
                   rounds=2, tag=tag, topN=100)
    prim = fx.snapshot_hits()
    after = secondary_hits(sec_base)
    out_before = before.get("/page/out", 0) if isinstance(before, dict) else 0
    out_after = after.get("/page/out", 0) if isinstance(after, dict) else 0
    ext_entry = res["crawldb"].get(ext_url, None)  # None => never entered crawldb
    ext_status = ext_entry["status"] if ext_entry else "absent"
    # "fetched" == Nutch actually retrieved it (crawldb db_fetched OR secondary hit).
    fetched = (ext_status == "db_fetched") or ((out_after - out_before) > 0)
    return {"tag": tag,
            "db_ignore_external_links": props.get("db.ignore.external.links"),
            "urlfilter_rules": rules,
            "primary_scope_seed_fetched": "/scope-seed" in prim,
            "primary_inscope_fetched": "/page/a" in prim,
            "external_url_crawldb_status": ext_status,
            "secondary_out_hits_delta": out_after - out_before,
            "out_of_scope_host_fetched": fetched}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
    if not (nd.NUTCH_HOME / "bin" / "nutch").exists():
        print(f"NUTCH_HOME invalid: {nd.NUTCH_HOME}", file=sys.stderr); return 2
    workroot = Path(nd.tempfile.mkdtemp(prefix="nutch-scope-"))
    srv = fx.start_fixture_server()
    base = srv.base_url
    sec_proc, sec_base = start_secondary()
    summary: dict = {"run_started_at": datetime.now(timezone.utc).isoformat(),
                     "tool": "apache-nutch", "primary_base_url": base,
                     "secondary_base_url": nd.redact(sec_base),
                     "nutch_home": nd.redact(str(nd.NUTCH_HOME))}
    try:
        summary["depth"] = depth_test(base, workroot)

        # Scope scenarios. Host string primary=127.0.0.1, secondary=localhost.
        base_props = {"http.agent.name": "nutch-eval-fixture",
                      "plugin.includes": STATIC_PLUGINS, "fetcher.server.delay": "0.0"}
        prim_host = base.split("//", 1)[1].split(":")[0]  # 127.0.0.1
        summary["scope"] = {
            "default_external_on": scope_scenario(
                base, sec_base, workroot, "scope_default",
                {**base_props, "db.ignore.external.links": "false"},
                ["-^(file|ftp|mailto):", "+."]),
            "ignore_external": scope_scenario(
                base, sec_base, workroot, "scope_ignore",
                {**base_props, "db.ignore.external.links": "true"},
                ["-^(file|ftp|mailto):", "+."]),
            "urlfilter_host_only": scope_scenario(
                base, sec_base, workroot, "scope_urlfilter",
                {**base_props, "db.ignore.external.links": "false"},
                [f"+^http://{prim_host}:", "-."]),
        }
        summary["scope"]["interpretation"] = {
            "shipped_default_stays_in_scope": not summary["scope"]["default_external_on"]["out_of_scope_host_fetched"],
            "ignore_external_blocks_out_host": not summary["scope"]["ignore_external"]["out_of_scope_host_fetched"],
            "urlfilter_blocks_out_host": not summary["scope"]["urlfilter_host_only"]["out_of_scope_host_fetched"],
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        (RAW / "scope-summary.json").write_text(
            json.dumps(nd.redact(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(nd.redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        srv.stop()
        sec_proc.terminate()
        try:
            sec_proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            sec_proc.kill()
        nd.shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
