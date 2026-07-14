#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总生成器 —— 从 artifacts/raw/*.json 计算 summary JSON，**不手写任何数字**（闸门3）。
所有字段读自各测试的运行产物；计时相关字段读自复用的 selectolax artifacts。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
SEL_RAW = os.path.join(HERE, "..", "..", "selectolax", "artifacts", "raw")


def load(p):
    return json.load(open(p))


def main():
    xpath = load(os.path.join(RAW, "xpath_matrix.json"))
    two_api = load(os.path.join(RAW, "two_api_behavior.json"))
    iterp = load(os.path.join(RAW, "iterparse_streaming.json"))
    ns = load(os.path.join(RAW, "namespaces.json"))
    xvc = load(os.path.join(RAW, "xpath_vs_css.json"))
    rw = load(os.path.join(RAW, "real_world_lxml.json"))
    api = load(os.path.join(RAW, "api_capabilities.json"))
    depth = load(os.path.join(RAW, "depth_limit.json"))

    # 复用的 selectolax 计时数据（只读引用）
    sel_isolate = load(os.path.join(SEL_RAW, "bench_isolate.json"))
    sel_cross = load(os.path.join(SEL_RAW, "etree_crosscheck.json"))
    sel_prod = load(os.path.join(SEL_RAW, "production_dims.json"))

    # 从复用数据里抽 lxml 关键数（计算，不手写）
    parse_only_lxml = {sz: sel_isolate["parse_only"][sz]["lxml"]["p50_ms"]["median_across_runs"]
                       for sz in sel_isolate["parse_only"]}
    parse_only_lexbor = {sz: sel_isolate["parse_only"][sz]["selectolax_lexbor"]["p50_ms"]["median_across_runs"]
                         for sz in sel_isolate["parse_only"]}
    lxml_faster_parse_pct = {sz: round((parse_only_lexbor[sz] / parse_only_lxml[sz] - 1) * 100, 1)
                             for sz in parse_only_lxml}

    summary = {
        "meta": {
            "tool": "lxml",
            "lxml_version": xpath["meta"]["lxml"],
            "libxml2_version": xpath["meta"]["libxml2_version"],
            "python": xpath["meta"]["python"],
            "generated_by": "build_summary.py (all fields computed from raw run artifacts; no hand-written numbers)",
            "timing_provenance": "reused from selectolax pack (as-of 2026-07-13); this pack produced NO timing numbers",
        },
        "capability_tests_this_pack_ran": {
            "xpath_matrix": {
                "functional_pass": xpath["computed"]["functional_pass"],
                "functional_total": xpath["computed"]["functional_total"],
                "fault_finding_pass": xpath["computed"]["fault_pass"],
                "fault_finding_total": xpath["computed"]["fault_total"],
                "all_pass_after_fault": xpath["computed"]["all_pass_after_fault_finding"],
            },
            "two_api_behavior": {
                "cases_matching_prereg": two_api["computed"]["cases_matching_prereg"],
                "cases_total": two_api["computed"]["cases_total"],
            },
            "iterparse_streaming": {
                "bounded_peak_rss_delta_mb": iterp["computed"]["bounded_peak_rss_delta_mb"],
                "full_load_peak_rss_delta_mb": iterp["computed"]["full_load_peak_rss_delta_mb"],
                "bounded_is_fraction_of_full": iterp["computed"]["bounded_is_fraction_of_full"],
                "yields_before_eof": iterp["computed"]["iterparse_yields_before_eof"],
                "n_records": iterp["meta"]["fixture"]["n_records"],
            },
            "namespaces": {
                "pass": ns["computed"]["pass"], "total": ns["computed"]["total"],
                "default_ns_requires_prefix_binding": ns["computed"]["default_ns_requires_prefix_binding"],
            },
            "xpath_vs_css": {
                "xpath_pass": xvc["computed"]["xpath_pass"], "total": xvc["computed"]["total"],
                "css_inexpressible_count": xvc["computed"]["css_inexpressible_count"],
            },
            "real_world_lxml": {
                "n_fixtures": rw["computed"]["n_fixtures"],
                "n_strict_xml_raised": rw["computed"]["n_strict_xml_raised"],
                "crosscheck_count_match": rw["computed"]["n_crosscheck_count_match"],
                "crosscheck_compared": rw["computed"]["n_crosscheck_compared"],
                "all_crosscheck_match": rw["computed"]["all_crosscheck_match"],
            },
            "api_capabilities": {
                "readwrite_dom_all_pass": all(v for v in api["readwrite_dom"].values() if isinstance(v, bool)),
                "serialization_all_pass": all(v for v in api["serialization"].values() if isinstance(v, bool)),
                "lxml_recovers_latin1_accents": api["encoding_bytes"].get("lxml_html_recovers_accents"),
                "node_lifecycle_hard_crash": api["node_lifecycle"]["hard_crash"],
                "iso88591_canonical_works_latin1_alias_fails": (
                    api["encoding_bytes"].get("xml_declared_iso88591_correct") is True
                    and api["encoding_bytes"].get("xml_declared_latin1_alias_raises") is True),
            },
            "depth_limit": {
                "default_caps_around_256": depth["computed"]["default_caps_around_256"],
                "huge_tree_recovers_depth_300": depth["computed"]["huge_tree_recovers_depth_300"],
                "huge_tree_still_capped_at_5000": depth["computed"]["huge_tree_still_capped_at_5000"],
                "huge_tree_depth_at_5000": depth["computed"]["huge_tree_depth_at_5000"],
            },
        },
        "reused_selectolax_timing_for_lxml": {
            "parse_only_p50_ms_lxml": parse_only_lxml,
            "parse_only_lxml_faster_than_lexbor_pct": lxml_faster_parse_pct,
            "throughput_100k_nodes_per_sec_lxml": sel_isolate["throughput_100k"]["lxml"]["nodes_per_sec"]["median_across_runs"],
            "two_lxml_apis_crosscheck": {
                sz: sel_cross["results"][sz]["_crosscheck"]
                for sz in sel_cross["results"]
            },
            "thread_scaling_lxml": sel_prod["thread_scaling"]["lxml"],
            "mem_growth_lxml_verdict": sel_prod["mem_growth"]["lxml"]["leak_verdict"],
        },
    }

    dst = os.path.join(RAW, "lxml-test-summary.json")
    with open(dst, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(json.dumps(summary["capability_tests_this_pack_ran"], indent=1, ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
