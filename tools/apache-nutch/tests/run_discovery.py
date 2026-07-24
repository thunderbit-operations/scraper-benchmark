#!/usr/bin/env python3
"""H1 + H2 -- what a local-mode Nutch crawl discovers, per endpoint class, on the
SAME same-fixture ground truth used by the katana pack.

Scenarios (each a full inject -> [generate,fetch,parse,updatedb] x rounds cycle):
  - default   : shipped-style plugin set (parse-html/tika; NO parse-js)
  - parsejs   : same + parse-js plugin enabled in nutch-site.xml
  - htmlunit  : swap protocol-http -> protocol-htmlunit (a JS-executing protocol),
                a bounded probe of whether the runtime-DOM class is reachable and
                at what cost. Reported honestly whether it loads / works / fails.

Recall per class is measured from SERVER-SIDE hits (did Nutch actually FETCH the
endpoint) -- the same fetch-truth katana used -- plus Nutch's own crawldb status.
Nothing is hardcoded; every count is computed from the run. The matrix is run
REPEAT times to show the coverage result is deterministic across processes.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx
import nutch_driver as nd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "artifacts" / "raw"
LOGS = PROJECT / "artifacts" / "logs"
REPEAT = 3
ROUNDS = 4

BASE_PLUGINS = "protocol-http|urlfilter-regex|parse-(html|tika)|scoring-opic|urlnormalizer-(pass|regex|basic)"
JS_PLUGINS = "protocol-http|urlfilter-regex|parse-(html|tika|js)|scoring-opic|urlnormalizer-(pass|regex|basic)"
HTMLUNIT_PLUGINS = "protocol-htmlunit|urlfilter-regex|parse-(html|tika|js)|scoring-opic|urlnormalizer-(pass|regex|basic)"
URLFILTER = ["-^(file|ftp|mailto):", "-\\.(gif|jpg|png|css|ico)$", "+."]


def class_recall(hits: dict[str, int]) -> dict:
    def rec(expected):
        found = [e for e in expected if e in hits]
        return {"found": len(found), "expected": len(expected),
                "recall": round(len(found) / len(expected), 3) if expected else None,
                "missing": [e for e in expected if e not in hits]}
    return {
        "A_html": rec(fx.HTML_ENDPOINTS),
        "A_depth_chain": rec(fx.HTML_DEPTH_CHAIN),
        "B_js_literal": rec(fx.JS_LITERAL_ENDPOINTS),
        "C_runtime_dom_only": {"found": fx.RUNTIME_DOM_ENDPOINT in hits,
                               "path": fx.RUNTIME_DOM_ENDPOINT},
    }


def one_scenario(base_url: str, tag: str, plugins: str, workroot: Path,
                 timeout_note: str = "") -> dict:
    props = {"http.agent.name": "nutch-eval-fixture", "plugin.includes": plugins,
             "db.ignore.external.links": "true", "fetcher.server.delay": "0.0",
             "http.timeout": "8000"}
    conf = nd.make_conf(workroot / tag, props, URLFILTER)
    res = nd.crawl(base_url, ["/"], conf, workroot / tag, LOGS, rounds=ROUNDS, tag=tag, topN=100)
    hits = fx.snapshot_hits()
    return {"tag": tag, "plugin_includes": plugins,
            "rounds_completed": res["rounds_completed"],
            "total_crawl_seconds": res["total_crawl_seconds"],
            "phase_returncodes": [{"phase": p["phase"], "round": p["round"], "rc": p["rc"]} for p in res["phases"]],
            "server_side_hits": hits,
            "class_recall": class_recall(hits),
            "crawldb_size": len(res["crawldb"]),
            "note": timeout_note}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
    if not (nd.NUTCH_HOME / "bin" / "nutch").exists():
        print(f"NUTCH_HOME invalid: {nd.NUTCH_HOME}", file=sys.stderr); return 2
    workroot = Path(nd.tempfile.mkdtemp(prefix="nutch-discovery-"))

    summary: dict = {"run_started_at": datetime.now(timezone.utc).isoformat(),
                     "tool": "apache-nutch", "nutch_home": nd.redact(str(nd.NUTCH_HOME)),
                     "java_home": nd.redact(nd.NUTCH_JAVA_HOME), "rounds_per_crawl": ROUNDS,
                     "repeats": REPEAT, "repeat_runs": [], "coverage_deterministic": None}

    per_repeat = []
    srv = fx.start_fixture_server()
    base = srv.base_url
    summary["base_url"] = base
    summary["ground_truth"] = fx.ground_truth(base)
    try:
        for i in range(1, REPEAT + 1):
            default = one_scenario(base, f"default_r{i}", BASE_PLUGINS, workroot)
            parsejs = one_scenario(base, f"parsejs_r{i}", JS_PLUGINS, workroot)
            per_repeat.append({"repeat": i,
                               "default_B_recall": default["class_recall"]["B_js_literal"]["recall"],
                               "parsejs_B_recall": parsejs["class_recall"]["B_js_literal"]["recall"],
                               "default_A_recall": default["class_recall"]["A_html"]["recall"],
                               "default_C_found": default["class_recall"]["C_runtime_dom_only"]["found"],
                               "parsejs_C_found": parsejs["class_recall"]["C_runtime_dom_only"]["found"]})
            if i == 1:
                summary["scenario_default"] = default
                summary["scenario_parsejs"] = parsejs
        summary["repeat_runs"] = per_repeat
        # Determinism: are the class recalls identical across all repeats?
        keys = ["default_A_recall", "default_B_recall", "parsejs_B_recall", "default_C_found", "parsejs_C_found"]
        summary["coverage_deterministic"] = all(
            len({r[k] for r in per_repeat}) == 1 for k in keys)

        # Bounded class-C probe via a JS-executing protocol plugin (protocol-htmlunit).
        htmlunit = {"attempted": True}
        try:
            hu = one_scenario(base, "htmlunit", HTMLUNIT_PLUGINS, workroot,
                              timeout_note="protocol-htmlunit swap-in probe for class C")
            htmlunit.update({
                "loaded_and_ran": hu["rounds_completed"] > 0,
                "rounds_completed": hu["rounds_completed"],
                "A_html_recall": hu["class_recall"]["A_html"]["recall"],
                "B_js_literal_recall": hu["class_recall"]["B_js_literal"]["recall"],
                "C_runtime_dom_found": hu["class_recall"]["C_runtime_dom_only"]["found"],
                "total_crawl_seconds": hu["total_crawl_seconds"],
                "server_side_hits": hu["server_side_hits"]})
        except Exception as e:  # noqa: BLE001
            htmlunit.update({"loaded_and_ran": False, "error": nd.redact(repr(e))})
        summary["scenario_htmlunit_probe"] = htmlunit

        # Coverage contrast (computed, not asserted).
        d = summary["scenario_default"]["class_recall"]
        j = summary["scenario_parsejs"]["class_recall"]
        summary["coverage_contrast"] = {
            "default_covers": {"A": d["A_html"]["recall"], "B": d["B_js_literal"]["recall"],
                               "C": d["C_runtime_dom_only"]["found"]},
            "parsejs_covers": {"A": j["A_html"]["recall"], "B": j["B_js_literal"]["recall"],
                               "C": j["C_runtime_dom_only"]["found"]},
            "parsejs_recovers_B_without_browser": j["B_js_literal"]["recall"] == 1.0
                and d["B_js_literal"]["recall"] < 1.0,
            "no_static_plugin_reaches_C": (not d["C_runtime_dom_only"]["found"])
                and (not j["C_runtime_dom_only"]["found"]),
            "katana_parity_note": "default == katana standard (A only); parsejs == katana "
                "standard -jc (A+B, browserless JS-literal recovery); class C needs a "
                "JS-executing protocol (htmlunit/selenium) just as katana needs -headless",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        (RAW / "discovery-summary.json").write_text(
            json.dumps(nd.redact(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(nd.redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        srv.stop()
        nd.shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
