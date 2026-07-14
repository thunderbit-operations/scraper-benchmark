#!/usr/bin/env python3
"""从各 raw JSON 计算汇总 —— 无手写数字 (方法论 v3 闸门 3 / Part 6 §2)。

读 tools/beautifulsoup/artifacts/raw/*.json (本 pack 实跑) + 只读引用
tools/selectolax/artifacts/raw/*.json (复用的计时/内存分布数据), 计算所有汇总数字。
本脚本不写死任何测量结论 —— 全部字段由输入 JSON 派生。

输出: artifacts/raw/beautifulsoup-test-summary.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
SELECTOLAX_RAW = os.path.join(HERE, "..", "..", "selectolax", "artifacts", "raw")
OUT = os.path.join(RAW, "beautifulsoup-test-summary.json")


def load(base, name):
    with open(os.path.join(base, name)) as f:
        return json.load(f)


def median_across(d):
    return d.get("median_across_runs")


def main():
    summary = {"generated_by": "build_summary.py (no hand-written numbers)", "sections": {}}

    # --- 复用: selectolax bench_parse -> bs4 backends 计时 (as-of 2026-07-13) ---
    bp = load(SELECTOLAX_RAW, "bench_parse.json")["results"]
    reuse_speed = {}
    for size in ["1kb", "10kb", "100kb", "1mb", "10mb"]:
        r = bp[size]
        row = {}
        for p in ["bs4_htmlparser", "bs4_lxml", "selectolax_lexbor", "lxml"]:
            row[p] = median_across(r[p]["p50_ms"])
        # 派生倍数 (bs4 相对 C 解析器慢多少)
        row["bs4_htmlparser_vs_lexbor_slowdown"] = round(row["bs4_htmlparser"] / row["selectolax_lexbor"], 1)
        row["bs4_lxml_vs_lexbor_slowdown"] = round(row["bs4_lxml"] / row["selectolax_lexbor"], 1)
        row["bs4_htmlparser_vs_lxml_slowdown"] = round(row["bs4_htmlparser"] / row["lxml"], 1)
        reuse_speed[size] = row
    summary["sections"]["reused_parse_extract_p50_ms"] = {
        "source": "tools/selectolax/artifacts/raw/bench_parse.json (median_across_runs, 3 runs, as-of 2026-07-13)",
        "data": reuse_speed,
    }

    # --- 复用: selectolax bench_memory_import -> bs4 RSS + import ---
    bm = load(SELECTOLAX_RAW, "bench_memory_import.json")
    rss10 = bm["memory_rss"]["page_10mb.html"]
    mem = {p: rss10[p]["rss_delta_mb"]["median_across_runs"] for p in rss10}
    mem_derived = {
        "bs4_lxml_over_selectolax_lexbor": round(mem["bs4_lxml"] / mem["selectolax_lexbor"], 2),
        "bs4_htmlparser_over_lxml": round(mem["bs4_htmlparser"] / mem["lxml"], 2),
        "bs4_htmlparser_over_selectolax_lexbor": round(mem["bs4_htmlparser"] / mem["selectolax_lexbor"], 2),
    }
    imp = bm["import_cold"]
    imp_ms = {m: imp[m]["median_ms"]["median_across_runs"] for m in imp}
    summary["sections"]["reused_memory_import"] = {
        "source": "tools/selectolax/artifacts/raw/bench_memory_import.json (10MB page, tracemalloc OFF, as-of 2026-07-13)",
        "rss_delta_mb_10mb": mem,
        "rss_ratios": mem_derived,
        "import_cold_ms": imp_ms,
        "bs4_import_over_lxml": round(imp_ms["bs4"] / imp_ms["lxml.html"], 2),
    }

    # --- 复用: selectolax production_dims -> bs4 GIL 信号 ---
    pd = load(SELECTOLAX_RAW, "production_dims.json")
    ts = pd["thread_scaling"]
    summary["sections"]["reused_gil_signal"] = {
        "source": "tools/selectolax/artifacts/raw/production_dims.json (as-of 2026-07-13, single-observation)",
        "bs4_lxml": ts.get("bs4_lxml"),
        "lxml": ts.get("lxml"),
        "selectolax_lexbor": ts.get("selectolax_lexbor"),
    }

    # --- 复用: selectolax css_coverage -> soupsieve 基础 41 例 ---
    cc = load(SELECTOLAX_RAW, "css_coverage.json")
    cases = cc["cases"]
    soup_pass = sum(1 for c in cases if (c.get("soupsieve", {}) or {}).get("status") == "PASS")
    summary["sections"]["reused_soupsieve_base_matrix"] = {
        "source": "tools/selectolax/artifacts/raw/css_coverage.json (41-case matrix, as-of 2026-07-13)",
        "soupsieve_pass": soup_pass,
        "soupsieve_total": len(cases),
    }

    # --- 本 pack 实跑: malformed matrix ---
    mm = load(RAW, "malformed_matrix.json")
    summary["sections"]["own_malformed_matrix"] = {
        "per_backend_meeting": mm["per_backend_meeting_count"],
        "n_cases": mm["meta"]["n_cases"],
        "divergent_case_ids": mm["divergent_case_ids"],
    }

    # --- 本 pack 实跑: api surface ---
    api = load(RAW, "api_surface.json")
    summary["sections"]["own_api_surface"] = {"n_ok": api["n_ok"], "n_probes": api["n_probes"]}

    # --- 本 pack 实跑: unicode dammit ---
    ud = load(RAW, "unicode_dammit.json")
    summary["sections"]["own_unicode_dammit"] = {
        "n_dammit_recovered": ud["n_dammit_recovered"],
        "n_bs4_recovered": ud["n_bs4_recovered"],
        "n_cases": ud["n_cases"],
        "chardet_available": ud["meta"]["chardet_available"],
    }

    # --- 本 pack 实跑: gc refcycles ---
    gc = load(RAW, "gc_refcycles.json")
    summary["sections"]["own_gc_refcycles"] = {
        "conclusions": gc["conclusions"],
        "tags_gc_off_after_del": gc["bs4_gc_off"]["after_del_no_collect_tags"],
        "tags_gc_on_after_del": gc["bs4_gc_on"]["after_del_no_collect_tags"],
        "control_acyclic_delta": gc["control_acyclic_gc_off"]["delta_after_del"],
    }

    # --- 本 pack 实跑: soupsieve extended ---
    se = load(RAW, "soupsieve_extended.json")
    summary["sections"]["own_soupsieve_extended"] = {"tally": se["tally"], "n_cases": se["meta"]["n_cases"]}

    # --- 本 pack 实跑: real backend divergence ---
    rb = load(RAW, "real_backend_divergence.json")
    summary["sections"]["own_real_backend_divergence"] = {
        "n_pages": rb["meta"]["n_pages"],
        "n_pages_all_agree": rb["n_pages_all_backends_agree"],
        "divergent_pages": rb["divergent_pages"],
        "mdn_template_links_per_backend": (rb.get("template_probe") or {}).get("links_per_backend"),
    }

    # 总测试项计数 (派生)
    total_items = (
        mm["meta"]["n_cases"]
        + api["n_probes"]
        + ud["n_cases"]
        + se["meta"]["n_cases"]
        + rb["meta"]["n_pages"] * len(rb["meta"]["backends"])
    )
    summary["own_total_discriminating_items"] = total_items

    with open(OUT, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"wrote {OUT}")
    print(json.dumps({
        "total_own_items": total_items,
        "malformed_per_backend": mm["per_backend_meeting_count"],
        "api_ok": f"{api['n_ok']}/{api['n_probes']}",
        "dammit": f"{ud['n_dammit_recovered']}/{ud['n_cases']}",
        "soupsieve_ext": se["tally"],
        "real_agree": f"{rb['n_pages_all_backends_agree']}/{rb['meta']['n_pages']}",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
