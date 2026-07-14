#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度嵌套截断 + huge_tree 旁路 —— 把 selectolax pack 的 FINDING-11a
（「lxml 在深嵌套下静默丢最深内容」）从「疑似 bug」精确化为「libxml2 的 DoS 防护默认上限，可配置抬升」。

selectolax pack 复用点：其 adversarial.json 记录 lxml 在 1000/5000 深 <div> 下 has_deep=False
（as-of 2026-07-13）。本测试用**默认 parser vs huge_tree=True**对照，量化：
1. 默认 parser 的实际可达深度（libxml2 ~256 层安全上限）；
2. huge_tree=True 能否恢复中等深度（300）；
3. 极深（5000）时是否还有第二道更硬的天花板（huge_tree 也吃不下）。

这解释了「静默丢内容」的**机制（documented DoS guard）**并给出**动作项（huge_tree=True）**。
所有 reached_depth / has_deep 由运行计算。
"""
import json
import os
import sys
import lxml.html
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)


def deep_html(n):
    return "<div>" * n + "deep" + "</div>" * n


def reached_depth(root):
    d = 0
    cur = root
    while len(cur):
        cur = cur[0]
        d += 1
    return d


def probe(depth):
    h = deep_html(depth)
    root_default = lxml.html.fromstring(h)
    parser = lxml.html.HTMLParser(huge_tree=True)
    root_huge = lxml.html.fromstring(h, parser=parser)
    return {
        "requested_depth": depth,
        "default": {
            "has_deep": "deep" in (root_default.text_content() or ""),
            "reached_depth": reached_depth(root_default),
        },
        "huge_tree": {
            "has_deep": "deep" in (root_huge.text_content() or ""),
            "reached_depth": reached_depth(root_huge),
        },
    }


def main():
    probes = [probe(d) for d in (300, 1000, 5000)]

    p300 = next(p for p in probes if p["requested_depth"] == 300)
    p5000 = next(p for p in probes if p["requested_depth"] == 5000)

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "reuse_ref": "selectolax adversarial.json (lxml deep_nesting_1000/5000 has_deep=false, as-of 2026-07-13)",
            "mechanism": "libxml2 default ~256-level nesting cap = DoS guard; huge_tree=True lifts it (documented; "
                         "lxml FAQ / launchpad #65510)",
            "note": "reached_depth / has_deep computed at runtime",
        },
        "computed": {
            "default_caps_around_256": (250 <= p300["default"]["reached_depth"] <= 260),
            "huge_tree_recovers_depth_300": p300["huge_tree"]["has_deep"],
            "huge_tree_still_capped_at_5000": (not p5000["huge_tree"]["has_deep"]),
            "huge_tree_depth_at_5000": p5000["huge_tree"]["reached_depth"],
        },
        "probes": probes,
    }
    dst = os.path.join(RAW, "depth_limit.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    for p in probes:
        print(f"  depth {p['requested_depth']:>4}: default reached {p['default']['reached_depth']} "
              f"(has_deep={p['default']['has_deep']}) | huge_tree reached {p['huge_tree']['reached_depth']} "
              f"(has_deep={p['huge_tree']['has_deep']})")
    print(f"  huge_tree recovers depth 300: {out['computed']['huge_tree_recovers_depth_300']}; "
          f"still capped at 5000: {out['computed']['huge_tree_still_capped_at_5000']}")


if __name__ == "__main__":
    main()
