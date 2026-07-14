#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实脏 HTML —— 复用 selectolax pack 的 11 个已入库实站抓取（fixtures/real/），
以 lxml 为主角，测 lxml.html 宽容解析器在真实脏页上的**保真度与容错行为**（非计时）。

复用来源（只读引用，不重抓、不重跑计时）：
  ../selectolax/artifacts/fixtures/real/*.html  （as-of 2026-07-10 抓取）

本测试测的是能力/保真，不是速度：
1. lxml.html.fromstring 对每个真实页是否成功解析、error_log 里吞了多少个 libxml2 恢复错误
   （真实网页几乎都不是 well-formed，lxml.html 靠 libxml2 HTML 恢复模式吃下）。
2. 抽取 <a href> / h1-h6 / <img src> 计数，与该 pack 复用的 selectolax real_world.json 里
   lxml 的计数**交叉核对一致性**（同一 fixture、同一库、应当吻合 → 证明复用口径对齐）。
3. lxml.etree 严格 XML 解析器对同样的真实 HTML 会怎样（预期大量 raise）——两套 API 的真实对照。

计数由运行计算；对照的 selectolax lxml 计数从复用 JSON 读入比对，不硬编码。
"""
import json
import os
import sys
from lxml import etree
import lxml.html

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
# 复用来源（只读）
REUSE_FIX = os.path.join(HERE, "..", "..", "selectolax", "artifacts", "fixtures", "real")
REUSE_JSON = os.path.join(HERE, "..", "..", "selectolax", "artifacts", "raw", "real_world.json")
os.makedirs(RAW, exist_ok=True)


def extract_counts_htmlparser(html_bytes):
    """用 lxml.html（宽容）解析并计数，同时捕获 libxml2 恢复错误数。
    计数口径对齐复用的 selectolax pack real_world.py（cssselect('a') 后按 href 真值过滤，
    空字符串 href 不计），以保证交叉核对是同口径。另记录「按属性存在计」与「按真值计」的差，
    暴露 href="" 这类空链接边界（纯口径差异，非 lxml 行为差异）。"""
    parser = lxml.html.HTMLParser(recover=True)
    root = lxml.html.fromstring(html_bytes, parser=parser)
    # 口径 A（对齐复用口径）：真值过滤
    n_links_truthy = len([n for n in root.cssselect("a") if n.get("href")])
    # 口径 B：属性存在即计（空串也算）
    n_links_present = len(root.xpath("//a[@href]"))
    n_headings = len(root.cssselect("h1, h2, h3, h4, h5, h6"))
    n_imgs = len([n for n in root.cssselect("img") if n.get("src")])
    return {
        "parsed": True,
        "n_links": n_links_truthy,           # 用于交叉核对（对齐复用口径）
        "n_links_attr_present": n_links_present,
        "n_links_empty_href": n_links_present - n_links_truthy,
        "n_headings": n_headings,
        "n_imgs": n_imgs,
        "libxml2_recovery_errors": len(parser.error_log),
        "first_recovery_error": (str(parser.error_log[0])[:120] if len(parser.error_log) else None),
    }


def try_strict_xml(html_bytes):
    """严格 XML 解析器吃真实 HTML —— 预期几乎都 raise。"""
    try:
        etree.fromstring(html_bytes, etree.XMLParser())
        return {"outcome": "ok"}
    except etree.XMLSyntaxError as ex:
        return {"outcome": "raised", "error": str(ex)[:100]}
    except Exception as ex:  # noqa
        return {"outcome": "raised", "error": type(ex).__name__ + ": " + str(ex)[:100]}


def main():
    if not os.path.isdir(REUSE_FIX):
        print(f"ERROR: reuse fixtures not found at {REUSE_FIX}", file=sys.stderr)
        sys.exit(1)

    # 载入复用的 selectolax lxml 计数做交叉核对
    reuse = json.load(open(REUSE_JSON))
    reuse_lxml = {}
    for name, d in reuse["pages"].items():
        if d.get("admitted") and "lxml" in d.get("compare", {}):
            c = d["compare"]["lxml"]
            reuse_lxml[name] = {"n_links": c["n_links"], "n_headings": c["n_headings"], "n_imgs": c["n_imgs"]}

    files = sorted(f for f in os.listdir(REUSE_FIX) if f.endswith(".html"))
    results = []
    n_parsed = 0
    n_strict_raised = 0
    n_count_match = 0
    n_compared = 0

    for fn in files:
        path = os.path.join(REUSE_FIX, fn)
        html_bytes = open(path, "rb").read()
        lenient = extract_counts_htmlparser(html_bytes)
        strict = try_strict_xml(html_bytes)
        if lenient["parsed"]:
            n_parsed += 1
        if strict["outcome"] == "raised":
            n_strict_raised += 1

        # 交叉核对（若复用 JSON 有该页）
        xcheck = None
        if fn in reuse_lxml:
            n_compared += 1
            r = reuse_lxml[fn]
            match = (lenient["n_links"] == r["n_links"]
                     and lenient["n_headings"] == r["n_headings"]
                     and lenient["n_imgs"] == r["n_imgs"])
            if match:
                n_count_match += 1
            xcheck = {"reuse_lxml": r,
                      "this_run": {"n_links": lenient["n_links"],
                                   "n_headings": lenient["n_headings"],
                                   "n_imgs": lenient["n_imgs"]},
                      "match": match}

        results.append({
            "fixture": fn,
            "size_bytes": len(html_bytes),
            "lxml_html_lenient": lenient,
            "lxml_etree_strict": strict,
            "crosscheck_vs_reused_selectolax_lxml": xcheck,
        })

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "reuse_source": {
                "fixtures": "../selectolax/artifacts/fixtures/real/ (as-of 2026-07-10 curl capture)",
                "crosscheck_json": "../selectolax/artifacts/raw/real_world.json (field: pages.*.compare.lxml.n_*)",
            },
            "note": "capability/fidelity on real dirty HTML, NOT timing; counts computed at runtime; "
                    "crosscheck compares this run's lxml counts to the reused selectolax pack's lxml counts",
        },
        "computed": {
            "n_fixtures": len(files),
            "n_parsed_lenient": n_parsed,
            "n_strict_xml_raised": n_strict_raised,
            "n_crosscheck_compared": n_compared,
            "n_crosscheck_count_match": n_count_match,
            "all_lenient_parsed": (n_parsed == len(files)),
            "all_crosscheck_match": (n_count_match == n_compared and n_compared > 0),
        },
        "results": results,
    }
    dst = os.path.join(RAW, "real_world_lxml.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"lenient parsed: {n_parsed}/{len(files)}; strict XML raised: {n_strict_raised}/{len(files)}")
    print(f"crosscheck vs reused selectolax-lxml counts: {n_count_match}/{n_compared} match")
    for r in results:
        x = r["crosscheck_vs_reused_selectolax_lxml"]
        rec = r["lxml_html_lenient"]["libxml2_recovery_errors"]
        flag = "" if (x is None or x["match"]) else "  <-- COUNT MISMATCH"
        print(f"  {r['fixture']:38s} links={r['lxml_html_lenient']['n_links']:>4} "
              f"recov_errs={rec:>4} strict={r['lxml_etree_strict']['outcome']}{flag}")


if __name__ == "__main__":
    main()
