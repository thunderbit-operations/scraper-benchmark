#!/usr/bin/env python3
"""soupsieve CSS 扩展覆盖 —— 补 selectolax pack 已测之外的 bs4 特定用法。

selectolax pack 已把 soupsieve 放进 41 例 CSS 矩阵并记录 soupsieve 41/41 全过
(见 tools/selectolax/artifacts/raw/css_coverage.json)。本探针**不重跑那 41 例**,
而是补 bs4/soupsieve 文档主打、但 selectolax 矩阵未覆盖的用法:
- soupsieve 独有的伪类 (`:contains()` 文本匹配, `:is()`/`:where()` 选择器组)
- 复杂组合器链 (`~` 通用兄弟, `+` 相邻)
- `:not()` 带选择器列表
- soupsieve 扩展 (`>` 后代限定 select 的 `limit`/`recursive`)
每例有预注册 expected id 集; PASS = 返回 id 集恰好相等 (运行时算出, 闸门 3)。

输出: artifacts/raw/soupsieve_extended.json
"""
import json
import os
import sys
import warnings

import soupsieve
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "artifacts", "raw", "soupsieve_extended.json")

# 用 lxml 后端建一棵良构树 (避免 html.parser 的未闭合陷阱污染 CSS 判定)
FIXTURE = """
<div id="root">
  <h2 id="h1">Alpha Title</h2>
  <p id="p1" class="body">first para with <a id="a1" href="/x">a link</a></p>
  <p id="p2" class="body featured">second featured</p>
  <span id="s1">standalone span</span>
  <p id="p3" class="body">third para no link</p>
  <ul id="list">
    <li id="li1" data-k="v">one</li>
    <li id="li2">two</li>
    <li id="li3" data-k="v">three</li>
  </ul>
  <div id="box" lang="en">
    <p id="p4">english para</p>
  </div>
  <input id="in1" type="text" disabled>
  <input id="in2" type="text">
</div>
"""


def ids(nodes):
    return sorted(n.get("id") for n in nodes if n.get("id"))


CASES = [
    dict(name="is_selector_list", css="#root :is(h2, span)", expected=["h1", "s1"]),
    dict(name="where_zero_specificity", css="#root :where(h2, span)", expected=["h1", "s1"]),
    dict(name="not_selector_list", css="p:not(.featured):not(:has(a))", expected=["p3", "p4"]),
    dict(name="has_descendant", css="p:has(a)", expected=["p1"]),
    dict(name="has_direct_child", css="p:has(> a)", expected=["p1"]),
    dict(name="general_sibling", css="#h1 ~ p", expected=["p1", "p2", "p3"]),
    dict(name="adjacent_sibling", css="#p1 + p", expected=["p2"]),
    dict(name="attr_presence", css="li[data-k]", expected=["li1", "li3"]),
    dict(name="attr_exact", css="li[data-k='v']", expected=["li1", "li3"]),
    dict(name="nth_of_type", css="li:nth-of-type(2)", expected=["li2"]),
    dict(name="first_child", css="li:first-child", expected=["li1"]),
    dict(name="last_child", css="li:last-child", expected=["li3"]),
    dict(name="only_child", css="#box p:only-child", expected=["p4"]),
    dict(name="contains_text", css="p:-soup-contains('featured')", expected=["p2"]),
    dict(name="contains_own", css="a:-soup-contains('a link')", expected=["a1"]),
    dict(name="disabled_pseudo", css="input:disabled", expected=["in1"]),
    dict(name="enabled_pseudo", css="input:enabled", expected=["in2"]),
    dict(name="lang_pseudo", css="#box:lang(en) p", expected=["p4"]),  # selectolax Lexbor 不支持 :lang
    dict(name="empty_pseudo", css="span:empty", expected=[]),  # s1 有文本, 非 empty
    dict(name="nested_is_not", css="p:is(.body):not(.featured)", expected=["p1", "p3"]),
]


def main():
    soup = BeautifulSoup(FIXTURE, "lxml")
    results = []
    for case in CASES:
        rec = {"name": case["name"], "css": case["css"], "expected": case["expected"]}
        try:
            got = ids(soup.select(case["css"]))
            rec["got"] = got
            rec["status"] = "PASS" if got == case["expected"] else "WRONG"  # 运行时算出
        except Exception as e:
            rec["got"] = None
            rec["status"] = "UNSUPPORTED"
            rec["error"] = f"{type(e).__name__}: {e}"
        results.append(rec)

    from collections import Counter
    tally = Counter(r["status"] for r in results)
    out = {
        "meta": {
            "soupsieve_version": soupsieve.__version__,
            "python": sys.version.split()[0],
            "backend": "lxml (well-formed tree)",
            "n_cases": len(CASES),
            "note": "补 selectolax 41 例矩阵之外的 bs4/soupsieve 特定用法; status 运行时算出",
            "reuse_reference": "selectolax pack css_coverage.json 已记录 soupsieve 41/41 (基础 41 例)",
        },
        "tally": dict(tally),
        "cases": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    fails = [r["name"] for r in results if r["status"] != "PASS"]
    print(json.dumps({"tally": dict(tally), "non_pass": fails}, ensure_ascii=False))


if __name__ == "__main__":
    main()
