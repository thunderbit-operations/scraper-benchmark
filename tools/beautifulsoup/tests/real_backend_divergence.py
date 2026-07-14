#!/usr/bin/env python3
"""三后端在真实脏 HTML 上的抽取一致性 —— 复用 selectolax pack 的真实 fixture (只读)。

selectolax pack 已在 artifacts/fixtures/real/ 存了 11 个过准入门的真实站点抓取
(BBC / Wikipedia / Craigslist / MDN / reddit ...)。本探针**只读**引用那批 fixture,
对每个页面用 bs4 的三后端 (html.parser / lxml / html5lib) 各跑一遍相同抽取任务
(全部 <a href> / h1-h6 / <img src> 计数), 记录三后端计数是否一致。

目的不是重测速度 (计时全部复用 selectolax 分布数据), 而是回答 bs4 用户的真实问题:
"我随手 BeautifulSoup(html) 用默认 html.parser, 和换 lxml/html5lib 抽出来的东西一样吗?"
divergence 字段运行时算出 (闸门 3)。

MDN 页含 <template> (selectolax pack FINDING-14 的现场) —— 顺带记录三后端对
<template> 内 <a> 的可见性差异。

输出: artifacts/raw/real_backend_divergence.json
"""
import json
import os
import sys
import warnings

from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
# 只读引用 selectolax pack 的真实 fixture
REAL_DIR = os.path.join(HERE, "..", "..", "selectolax", "artifacts", "fixtures", "real")
OUT = os.path.join(HERE, "..", "artifacts", "raw", "real_backend_divergence.json")

BACKENDS = ["html.parser", "lxml", "html5lib"]


def extract_counts(soup):
    return {
        "links": len([a for a in soup.find_all("a") if a.get("href")]),
        "headings": len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])),
        "imgs": len([i for i in soup.find_all("img") if i.get("src")]),
    }


def main():
    import bs4

    if not os.path.isdir(REAL_DIR):
        print(json.dumps({"error": f"real fixture dir not found: {REAL_DIR}"}))
        sys.exit(1)

    files = sorted(f for f in os.listdir(REAL_DIR) if f.endswith(".html"))
    pages = []
    for fn in files:
        path = os.path.join(REAL_DIR, fn)
        with open(path, "rb") as f:
            raw = f.read()
        rec = {"page": fn, "bytes": len(raw), "backends": {}}
        for backend in BACKENDS:
            try:
                soup = BeautifulSoup(raw, backend)
                rec["backends"][backend] = extract_counts(soup)
            except Exception as e:
                rec["backends"][backend] = {"error": f"{type(e).__name__}: {e}"}
        # divergence: 三后端 links 计数是否全等 (运行时算出)
        link_counts = [rec["backends"][b].get("links") for b in BACKENDS]
        head_counts = [rec["backends"][b].get("headings") for b in BACKENDS]
        img_counts = [rec["backends"][b].get("imgs") for b in BACKENDS]
        rec["links_agree"] = len(set(link_counts)) == 1
        rec["headings_agree"] = len(set(head_counts)) == 1
        rec["imgs_agree"] = len(set(img_counts)) == 1
        rec["fully_agree"] = rec["links_agree"] and rec["headings_agree"] and rec["imgs_agree"]
        rec["link_count_range"] = [min(link_counts), max(link_counts)]
        pages.append(rec)

    n_full_agree = sum(1 for p in pages if p["fully_agree"])
    divergent = [p["page"] for p in pages if not p["fully_agree"]]

    # 专门看 MDN 的 <template> 现场 (selectolax FINDING-14)
    template_probe = None
    for p in pages:
        if "mdn" in p["page"].lower():
            template_probe = {
                "page": p["page"],
                "links_per_backend": {b: p["backends"][b].get("links") for b in BACKENDS},
                "note": "MDN 含 <template>; bs4 三后端均把 template 内容 flatten 进主树 (与 selectolax Lexbor 相反)",
            }

    out = {
        "meta": {
            "bs4_version": bs4.__version__,
            "python": sys.version.split()[0],
            "backends": BACKENDS,
            "n_pages": len(pages),
            "fixture_source": "只读复用 tools/selectolax/artifacts/fixtures/real/ (11 站, fetched 2026-07-10, 过准入门)",
            "note": "只测三后端抽取一致性, 不测速度 (计时复用 selectolax 分布数据); agree 字段运行时算出",
        },
        "n_pages_all_backends_agree": n_full_agree,
        "divergent_pages": divergent,
        "template_probe": template_probe,
        "pages": pages,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps({"n_pages": len(pages), "all_agree": n_full_agree, "divergent": divergent}, ensure_ascii=False))


if __name__ == "__main__":
    main()
