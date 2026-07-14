#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命名空间处理 —— XML/SVG/RSS/Atom 真实结构的 NS 绑定，selectolax（HTML-only、无 XPath）覆盖不到。

预注册若干带命名空间的文档 + 每条查询的**预期命中数**，再跑：
1. 默认命名空间：XPath 必须显式绑定前缀（libxml2 XPath 1.0 不支持无前缀默认 NS），
   预注册「不绑前缀 → 命中 0 / 绑前缀 → 命中 N」的对比，证明这是 lxml/XPath 的已知设计。
2. 多命名空间混合（Atom + Dublin Core + content:encoded 的 RSS）。
3. SVG 默认命名空间下取元素。
4. local-name() 规避前缀的技巧。
5. nsmap 内省 + QName 处理。

所有命中数由运行计算（闸门3）；预期集预注册。
"""
import json
import os
import sys
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

# --- 真实结构样本（浓缩但结构真实）---
RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Example Feed</title>
    <atom:link href="https://ex.com/feed" rel="self"/>
    <item>
      <title>Post A</title>
      <dc:creator>Alice</dc:creator>
      <content:encoded><![CDATA[<p>Body A</p>]]></content:encoded>
    </item>
    <item>
      <title>Post B</title>
      <dc:creator>Bob</dc:creator>
      <content:encoded><![CDATA[<p>Body B</p>]]></content:encoded>
    </item>
  </channel>
</rss>"""

SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="100" height="100">
  <rect id="r1" width="10" height="10"/>
  <rect id="r2" width="20" height="20"/>
  <circle id="c1" r="5"/>
  <use xlink:href="#r1"/>
</svg>"""

# 带默认命名空间的通用 XML（如 XHTML / 自定义 schema）
DEFAULT_NS = """<?xml version="1.0"?>
<catalog xmlns="urn:example:catalog">
  <book><title>T1</title></book>
  <book><title>T2</title></book>
  <book><title>T3</title></book>
</catalog>"""


def run():
    results = []

    def check(name, got, expect, extra=None):
        row = {"case": name, "got": got, "expected": expect, "pass": (got == expect)}
        if extra:
            row.update(extra)
        results.append(row)
        return row["pass"]

    # 1. RSS：dc:creator 命中数（绑前缀）
    rss = etree.fromstring(RSS.encode())
    ns_rss = {"content": "http://purl.org/rss/1.0/modules/content/",
              "dc": "http://purl.org/dc/elements/1.1/",
              "atom": "http://www.w3.org/2005/Atom"}
    creators = rss.xpath("//dc:creator/text()", namespaces=ns_rss)
    check("rss:dc-creator-bound", [str(c) for c in creators], ["Alice", "Bob"])

    # content:encoded 命中数
    enc = rss.xpath("//content:encoded", namespaces=ns_rss)
    check("rss:content-encoded-count", len(enc), 2)

    # atom:link 的 href 属性
    href = rss.xpath("//atom:link/@href", namespaces=ns_rss)
    check("rss:atom-link-href", [str(h) for h in href], ["https://ex.com/feed"])

    # 2. 默认命名空间：不绑前缀 → 命中 0（libxml2 XPath 1.0 已知行为）
    dns = etree.fromstring(DEFAULT_NS.encode())
    no_prefix = dns.xpath("//book")  # 不给 namespaces
    check("defaultns:no-prefix-misses", len(no_prefix), 0,
          {"why": "libxml2 XPath 1.0 无默认命名空间概念；//book 找的是无 NS 的 book"})

    # 绑一个人工前缀 → 命中 3
    with_prefix = dns.xpath("//c:book", namespaces={"c": "urn:example:catalog"})
    check("defaultns:with-prefix-hits", len(with_prefix), 3)

    # local-name() 规避前缀 → 命中 3
    local = dns.xpath("//*[local-name()='book']")
    check("defaultns:local-name-hits", len(local), 3)

    # 3. SVG 默认命名空间
    svg = etree.fromstring(SVG.encode())
    svg_ns = {"s": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}
    rects = svg.xpath("//s:rect", namespaces=svg_ns)
    check("svg:rect-count", len(rects), 2)
    # xlink:href（第二命名空间）
    use_href = svg.xpath("//s:use/@xlink:href", namespaces=svg_ns)
    check("svg:xlink-href", [str(h) for h in use_href], ["#r1"])

    # 4. nsmap 内省
    check("nsmap:rss-has-3-prefixes", len(rss.nsmap), 3)
    # QName 解析：把 clark notation {uri}local 拆开
    q = etree.QName(enc[0].tag)
    check("qname:localname", q.localname, "encoded")
    check("qname:namespace", q.namespace, "http://purl.org/rss/1.0/modules/content/")

    # 5. 混合：一次 XPath 同时跨两个命名空间（dc:creator 属于哪个 item 的 title）
    #    取每个 item 的 title + creator 配对
    titles = rss.xpath("//item/title/text()")
    check("rss:item-titles", [str(t) for t in titles], ["Post A", "Post B"])

    n_pass = sum(1 for r in results if r["pass"])
    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "note": "namespace handling on RSS/SVG/default-NS XML; hit counts computed at runtime; "
                    "expected values pre-registered",
        },
        "computed": {"pass": n_pass, "total": len(results),
                     "default_ns_requires_prefix_binding": (
                         next(r for r in results if r["case"] == "defaultns:no-prefix-misses")["got"] == 0
                         and next(r for r in results if r["case"] == "defaultns:with-prefix-hits")["got"] == 3)},
        "results": results,
    }
    dst = os.path.join(RAW, "namespaces.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"namespace cases pass: {n_pass}/{len(results)}")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL {r['case']}: got={r['got']} expected={r['expected']}")


if __name__ == "__main__":
    run()
