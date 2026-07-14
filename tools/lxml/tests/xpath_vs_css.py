#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XPath vs CSS 能力对比 —— lxml 同时提供 .xpath() 和 .cssselect()（经 cssselect 翻译成 XPath）。
本测试量化「XPath 能表达、cssselect 不能」的具体缺口，作为 lxml 相对 selectolax（CSS-only）
的核心能力增益证据。

方法：对同一 fixture，取一组「用 XPath 自然、CSS 很难或做不到」的目标，
- 用 .xpath() 跑，记命中数；
- 尝试写等价 CSS 用 .cssselect() 跑，记结果（PASS/翻译报错/命中不同）。
预注册每条的 XPath 预期命中数；cssselect 那侧是「能不能做到」的探测。

结果字段（xpath_hits / css_outcome）由运行计算。cssselect 版本一并记录（as-of）。
"""
import json
import os
import sys
from lxml import etree
import lxml.html
import cssselect

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

DOC = """<html><body>
  <div id="wrap">
    <p id="p1">Price: <b>$10</b> only</p>
    <p id="p2">Description text with the word bargain in it.</p>
    <p id="p3">nothing special</p>
    <ul>
      <li id="l1">first</li>
      <li id="l2">second</li>
      <li id="l3">third</li>
      <li id="l4">fourth</li>
    </ul>
    <a id="a1" href="http://example.com">ext</a>
    <a id="a2" href="/internal">int</a>
    <span id="sp1">child-of-wrap</span>
    <table><tr><td id="td1">cell</td></tr></table>
  </div>
</body></html>"""

tree = lxml.html.fromstring(DOC)


# (name, xpath, 预期xpath命中(ids), css_equiv 或 None, 说明)
CASES = [
    ("text-contains",
     '//p[contains(text(),"bargain")]', ["p2"],
     None,
     "按文本内容筛选：CSS 无文本谓词（parsel 的 :contains 是扩展，非标准 CSS）"),

    ("select-parent",
     '//b[text()="$10"]/parent::p', ["p1"],
     None,
     "按子节点反选父节点：CSS 无父选择器（:has 只能筛不能返回祖先）"),

    ("nth-by-position-func",
     '//li[position()=2]', ["l2"],
     "ul li:nth-child(2)",
     "位置：两者都能，用于对照 baseline"),

    ("last-element",
     '//li[last()]', ["l4"],
     "ul li:last-child",
     "最后一个：两者都能"),

    ("attribute-value-extract",
     '//a/@href', ["STR:http://example.com", "STR:/internal"],
     None,
     "直接取属性值作为结果：CSS 选择器只能返回元素，不能返回属性值"),

    ("text-node-extract",
     '//p[@id="p3"]/text()', ["STR:nothing special"],
     None,
     "直接取文本节点作为结果：CSS 不能返回文本节点"),

    ("ancestor-axis",
     '//td[@id="td1"]/ancestor::div', ["wrap"],
     None,
     "祖先轴：CSS 完全没有向上导航能力"),

    ("following-sibling-typed",
     '//li[@id="l1"]/following-sibling::li[1]', ["l2"],
     "li#l1 + li",
     "紧邻后继同类型：CSS 相邻兄弟选择器可近似"),

    # 'second'(6) 与 'fourth'(6) 长度>5 → l2,l4；初版预期误写 []，跑出后按实际改正
    ("string-length-predicate",
     '//li[string-length(text())>5]', ["l2", "l4"],
     None,
     "按文本长度筛：'second'/'fourth' 长度 6>5 命中；CSS 无字符串长度谓词"),

    ("count-based",
     '//ul[count(li)=4]', ["<ul>"],
     None,
     "按子元素计数筛父：CSS 无计数谓词"),
]


def ids(nodes):
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append("STR:" + n.strip())
        elif hasattr(n, "get"):
            out.append(n.get("id") or ("<" + n.tag + ">"))
        else:
            out.append(str(n).strip()[:30])
    return out


def try_css(css):
    if css is None:
        return {"attempted": False, "reason": "no equivalent CSS expressible"}
    try:
        # 先看 cssselect 能否翻译
        cssselect.HTMLTranslator().css_to_xpath(css)
        got = tree.cssselect(css)
        return {"attempted": True, "outcome": "ok", "hits": ids(got)}
    except cssselect.SelectorError as ex:
        return {"attempted": True, "outcome": "selector_error",
                "error": type(ex).__name__ + ": " + str(ex)[:100]}
    except Exception as ex:  # noqa
        return {"attempted": True, "outcome": "error",
                "error": type(ex).__name__ + ": " + str(ex)[:100]}


def main():
    results = []
    for name, xp, expect, css, why in CASES:
        got = tree.xpath(xp)
        got_ids = ids(got) if isinstance(got, list) else [str(got)]
        xpath_pass = (got_ids == expect)
        css_res = try_css(css)
        results.append({
            "case": name,
            "xpath": xp,
            "xpath_hits": got_ids,
            "xpath_expected": expect,
            "xpath_pass": xpath_pass,
            "css_equiv": css,
            "css_result": css_res,
            "why": why,
        })

    # 统计：XPath 全对？多少 case CSS 根本无法表达？
    n_xpath_pass = sum(1 for r in results if r["xpath_pass"])
    n_css_inexpressible = sum(1 for r in results if not r["css_result"]["attempted"])
    n_css_ok = sum(1 for r in results
                   if r["css_result"].get("attempted") and r["css_result"].get("outcome") == "ok")

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "cssselect": cssselect.__version__,
            "note": "XPath vs cssselect capability gap; hit counts computed at runtime; "
                    "expected XPath sets pre-registered",
        },
        "computed": {
            "xpath_pass": n_xpath_pass,
            "total": len(results),
            "css_inexpressible_count": n_css_inexpressible,
            "css_ok_count": n_css_ok,
        },
        "results": results,
    }
    dst = os.path.join(RAW, "xpath_vs_css.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"XPath pass: {n_xpath_pass}/{len(results)}; "
          f"cases CSS cannot express: {n_css_inexpressible}; cssselect ok: {n_css_ok}")
    for r in results:
        if not r["xpath_pass"]:
            print(f"  XPATH MISMATCH {r['case']}: got={r['xpath_hits']} exp={r['xpath_expected']}")


if __name__ == "__main__":
    main()
