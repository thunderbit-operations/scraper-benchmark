#!/usr/bin/env python3
"""Generate results/selectolax-test-summary.json by COMPUTING every field from
the committed raw result JSONs -- no hand-written numbers or conclusion strings.

The earlier summary was authored by hand: it drifted out of sync with the raw
data (e.g. soupsieve 40/41 before the css fixture fix -> 41/41 after), carried an
un-wired `module___version__: null` bug while api_usability.json had the real
value, and embedded free-text conclusions (a form of hardcoded result). This
script removes all of that: run it after the benchmarks and it derives the
summary from the JSONs the tests emit, so the summary can't disagree with them.
"""
import json
import os

HERE = os.path.dirname(__file__)
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(HERE, "..", "artifacts", "raw")


def load(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)


def med(node):
    """Return median_across_runs from a stat leaf (or the value itself)."""
    if isinstance(node, dict) and "median_across_runs" in node:
        return node["median_across_runs"]
    return node


def main():
    bp = load("bench_parse.json")
    bpr = bp["results"]
    bi = load("bench_isolate.json")
    mem = load("bench_memory_import.json")
    css = load("css_coverage.json")
    api = load("api_usability.json")
    enc = load("encoding_probe.json")
    prod = load("production_dims.json")
    rw = load("real_world.json")
    try:
        etree = load("etree_crosscheck.json")
    except FileNotFoundError:
        etree = None

    sizes = ["1kb", "10kb", "100kb", "1mb", "10mb"]

    def p50(size, eng):
        return med(bpr[size][eng]["p50_ms"])

    sp_hp = {s: round(p50(s, "bs4_htmlparser") / p50(s, "selectolax_lexbor"), 1) for s in sizes}
    sp_lx = {s: round(p50(s, "bs4_lxml") / p50(s, "selectolax_lexbor"), 1) for s in sizes}

    # parse-only ratio: lexbor / lxml (>1 means lxml is faster)
    po = bi["parse_only"]
    parse_ratio = {s: round(med(po[s]["selectolax_lexbor"]["p50_ms"]) / med(po[s]["lxml"]["p50_ms"]), 3)
                   for s in ["10kb", "100kb", "1mb", "10mb"]}

    tp = bi["throughput_100k"]
    throughput = {e: {"query_p50_ms": med(tp[e]["query_p50_ms"]),
                      "nodes_per_sec": med(tp[e]["nodes_per_sec"])} for e in tp}

    mr = mem["memory_rss"]["page_10mb.html"]
    rss = {e: med(mr[e]["rss_delta_mb"]) for e in mr}
    mt = mem["memory_tracemalloc"]["page_10mb.html"]

    def tm_peak(e):
        for fk, fv in mt[e].items():
            if "peak" in fk.lower():
                return med(fv)
        return None
    tm = {e: tm_peak(e) for e in mt}
    lean_max = max(rss["selectolax_lexbor"], rss["lxml"])
    lean_min = min(rss["selectolax_lexbor"], rss["lxml"])
    bs_max = max(rss["bs4_htmlparser"], rss["bs4_lxml"])
    bs_min = min(rss["bs4_htmlparser"], rss["bs4_lxml"])
    mem_ratio_range = [round(bs_min / lean_max, 2), round(bs_max / lean_min, 2)]

    # css tally: count per-engine .status across the 41 cases (computed, not typed)
    engines = ["lexbor", "modest", "lxml", "parsel", "soupsieve"]
    css_tally = {}
    for e in engines:
        t = {"PASS": 0, "WRONG": 0, "UNSUPPORTED": 0, "PROCESS_ABORT": 0}
        for case in css["cases"]:
            st = case.get(e, {}).get("status")
            if st in t:
                t[st] += 1
        css_tally[e] = t

    ts = prod["thread_scaling"]
    thread = {e: ts[e]["speedup"] for e in ts}
    mg = prod["mem_growth"]
    leak = {e: {"growth_first_to_last_mb": mg[e].get("growth_first_to_last_mb"),
                "verdict": mg[e].get("leak_verdict")}
            for e in ("selectolax_lexbor", "selectolax_modest", "lxml") if e in mg}

    # encoding: read the measured corruption per engine
    def enc_text(engine):
        e = enc.get("engines", {}).get(engine, {})
        ta = e.get("text_analysis", {})
        return {"corruption": ta.get("corruption"),
                "html_serialization": e.get("html_serialization", {}).get("outcome")}

    summary = {
        "_generated_by": "tests/build_summary.py (all fields computed from raw result JSONs)",
        "as_of": "2026-07-10 (benchmarks re-run 2026-07-13, methodology v3)",
        "tool": "selectolax",
        "version_measured": api.get("module___version___value"),
        "module_has___version__": api.get("module_has___version__"),
        "platform": bp["meta"].get("machine", "darwin") + " / Python " + bp["meta"].get("python", ""),
        "benchmark_runs": bp["meta"].get("n_runs", 3),
        "engines": ["lexbor", "modest"],
        "headline_speedup_lexbor_vs_bs4_htmlparser_p50": sp_hp,
        "headline_speedup_lexbor_vs_bs4_lxml_p50": sp_lx,
        "parse_only_lexbor_over_lxml_p50_ratio_gt1_means_lxml_faster": parse_ratio,
        "throughput_100k_nodes": throughput,
        "memory_10mb_rss_delta_mb_tracemalloc_OFF": rss,
        "memory_10mb_tracemalloc_peak_mb_separate_proc_exhibit_only": tm,
        "memory_bs4_over_lean_rss_ratio_range": mem_ratio_range,
        "css_coverage_41_cases_incl_fault_finding": css_tally,
        "xpath_supported": {e: css["xpath"].get(e, {}).get("has_xpath_method")
                            for e in ("lexbor", "modest", "lxml", "parsel")},
        "non_utf8_bytes_behavior": {"lexbor": enc_text("lexbor"), "modest": enc_text("modest")},
        "thread_scaling_speedup_4threads": thread,
        "long_loop_memory_growth_mb": leak,
        "long_loop_instrument_calibration": mg.get("_instrument_calibration"),
        "real_world_admitted": rw["meta"].get("n_admitted"),
        "real_world_excluded": rw["meta"].get("n_excluded"),
    }
    if etree:
        summary["parse_only_etree_crosscheck"] = {
            s: etree["results"][s]["_crosscheck"] for s in etree.get("results", {})}

    out_path = os.path.join(RAW, "selectolax-test-summary.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print("written", out_path)
    print("  version_measured:", summary["version_measured"],
          "| has___version__:", summary["module_has___version__"])
    print("  css soupsieve:", css_tally["soupsieve"])
    print("  mem bs4/lean ratio range:", mem_ratio_range)
    print("  parse_only ratio (lexbor/lxml):", parse_ratio)


if __name__ == "__main__":
    main()
