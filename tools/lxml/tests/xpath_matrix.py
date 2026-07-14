#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XPath 特性矩阵 —— lxml 的杀手锏能力，selectolax / bs4 都无原生 XPath。

反偏向设计（方法论 v3 Part 3 §9）：
- 预注册覆盖类矩阵：轴 / 谓词 / 内建函数 / 命名空间 / 返回类型。
- 每个 case **先写死预期集合**（EXPECT），再跑；PASS = 返回值 exactly equal 预期。
- 满分必须是「找茬后的满分」：矩阵尾部含一批「找茬 pass」——已知 lxml 用 libxml2
  的 XPath 1.0 引擎，因此 XPath 2.0-only 语法（如 matches()、序列表达式、if/then）
  预期 **不支持**；把它们写进矩阵，看引擎是报错还是静默返回错集。

对照组：同一批 CSS-可表达的 case 也用 cssselect 跑（能力对比 XPath vs CSS），
但只用于「哪些 XPath 表达不出对应 CSS」的定性，不算进 XPath 的 PASS 分。

结果字段全部由运行输出计算（闸门 3）：PASS/FAIL、returned、expected 都是测出来的。
无任何硬编码结论字符串。
"""
import json
import sys
import os
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

# ---------------------------------------------------------------------------
# 单一可控 fixture：id 唯一、结构已知，便于写死预期集合
# ---------------------------------------------------------------------------
DOC = """<html>
  <body>
    <div id="wrap" class="container main" data-role="LEAD">
      <h1 id="t">Title One</h1>
      <ul id="list">
        <li id="a" class="item" data-n="1">alpha</li>
        <li id="b" class="item featured" data-n="2">beta</li>
        <li id="c" class="item" data-n="3">gamma-value</li>
        <li id="d" class="other" data-n="4">delta</li>
        <li id="e" class="item" data-n="5">epsilon</li>
      </ul>
      <p id="p1">first <a id="lnk" href="http://example.com/path">link text</a> tail</p>
      <p id="p2">second paragraph</p>
      <span id="s1">standalone</span>
      <div id="empty"></div>
      <footer id="ft"><a id="fa" href="/rel">footer link</a></footer>
    </div>
  </body>
</html>"""

tree = etree.HTML(DOC)


def ids(nodes):
    """把节点列表规约成有序 id 列表（无 id 的用 tag:index 占位），用于 exact 比较。"""
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append("STR:" + n)
        elif hasattr(n, "get"):
            out.append(n.get("id") or ("<" + n.tag + ">"))
        else:
            out.append(repr(n))
    return out


# ---------------------------------------------------------------------------
# 预注册矩阵：每条 = (类别, xpath 表达式, 预期返回, 预期类型)
# 预期在跑之前就写死。type: 'ids' 比较 id 集合；'scalar' 比较标量；'raises' 期望抛错。
# ---------------------------------------------------------------------------
MATRIX = [
    # --- 轴 axes ---
    ("axis:child",        '//ul[@id="list"]/li',                      {"expect": ["a","b","c","d","e"], "type": "ids"}),
    ("axis:descendant",   '//div[@id="wrap"]//a',                     {"expect": ["lnk","fa"], "type": "ids"}),
    ("axis:parent",       '//a[@id="lnk"]/parent::p',                 {"expect": ["p1"], "type": "ids"}),
    ("axis:ancestor",     '//a[@id="fa"]/ancestor::div',              {"expect": ["wrap"], "type": "ids"}),
    ("axis:following-sib",'//li[@id="b"]/following-sibling::li',      {"expect": ["c","d","e"], "type": "ids"}),
    ("axis:preceding-sib",'//li[@id="d"]/preceding-sibling::li',      {"expect": ["a","b","c"], "type": "ids"}),
    ("axis:self",         '//li[@id="c"]/self::li',                   {"expect": ["c"], "type": "ids"}),
    ("axis:attribute",    '//div[@id="wrap"]/@data-role',             {"expect": ["STR:LEAD"], "type": "ids"}),
    ("axis:following",    '//h1[@id="t"]/following::span',            {"expect": ["s1"], "type": "ids"}),
    ("axis:preceding",    '//span[@id="s1"]/preceding::h1',           {"expect": ["t"], "type": "ids"}),

    # --- 谓词 predicates ---
    ("pred:index",        '(//li)[1]',                                {"expect": ["a"], "type": "ids"}),
    ("pred:last",         '//li[last()]',                             {"expect": ["e"], "type": "ids"}),
    ("pred:position-lt",  '//li[position()<3]',                       {"expect": ["a","b"], "type": "ids"}),
    ("pred:attr-eq",      '//li[@data-n="3"]',                        {"expect": ["c"], "type": "ids"}),
    ("pred:attr-exists",  '//li[@class]',                             {"expect": ["a","b","c","d","e"], "type": "ids"}),
    ("pred:and",          '//li[@class="item" and @data-n="5"]',      {"expect": ["e"], "type": "ids"}),
    ("pred:or",           '//li[@id="a" or @id="e"]',                 {"expect": ["a","e"], "type": "ids"}),
    # 注意：ft 是 <footer> 不是 <div>，故只有 wrap 命中（这是修正后的预期，
    # 初版预期误写成 ["wrap","ft"]，跑出来发现是 harness 预期写错、非 lxml 错——
    # 依方法论 Part6§4 先排除 harness/fixture 问题再下结论，改正预期集）
    ("pred:nested",       '//div[.//a[@href]]',                       {"expect": ["wrap"], "type": "ids"}),
    ("pred:not-func",     '//li[not(@data-n="1")]',                   {"expect": ["b","c","d","e"], "type": "ids"}),

    # --- 内建函数 functions ---
    ("fn:text",           '//p[@id="p2"]/text()',                     {"expect": ["STR:second paragraph"], "type": "ids"}),
    ("fn:contains",       '//li[contains(text(),"gamma")]',           {"expect": ["c"], "type": "ids"}),
    ("fn:starts-with",    '//li[starts-with(@id,"a")]',               {"expect": ["a"], "type": "ids"}),
    ("fn:count",          'count(//li)',                              {"expect": 5.0, "type": "scalar"}),
    ("fn:string-length",  'string-length(//h1[@id="t"])',             {"expect": 9.0, "type": "scalar"}),
    ("fn:normalize-space",'normalize-space(//p[@id="p1"])',           {"expect": "first link text tail", "type": "scalar"}),
    ("fn:concat",         'concat(//li[@id="a"]/text(),"/",//li[@id="b"]/text())', {"expect": "alpha/beta", "type": "scalar"}),
    ("fn:substring",      'substring(//h1[@id="t"],1,5)',             {"expect": "Title", "type": "scalar"}),
    ("fn:name",           'name(//div[@id="wrap"])',                  {"expect": "div", "type": "scalar"}),
    ("fn:string-scalar",  'string(//a[@id="lnk"]/@href)',             {"expect": "http://example.com/path", "type": "scalar"}),

    # --- 返回类型 return types ---
    ("ret:boolean-true",  'boolean(//li[@id="a"])',                   {"expect": True, "type": "scalar"}),
    ("ret:boolean-false", 'boolean(//li[@id="zzz"])',                 {"expect": False, "type": "scalar"}),
    ("ret:number",        'number(//li[@id="c"]/@data-n)',            {"expect": 3.0, "type": "scalar"}),

    # --- 找茬 pass：XPath 2.0-only，libxml2 的 XPath 1.0 引擎预期不支持 ---
    ("fault:xpath2-matches",  'matches("abc","a.c")',                 {"expect_raises": True, "type": "raises",
                                                                       "why": "matches() 是 XPath 2.0 函数；libxml2 只实现 XPath 1.0"}),
    ("fault:xpath2-seq",      '(1,2,3)',                              {"expect_raises": True, "type": "raises",
                                                                       "why": "序列构造是 XPath 2.0；1.0 不支持逗号序列"}),
    ("fault:xpath2-if",       'if (//li) then 1 else 0',              {"expect_raises": True, "type": "raises",
                                                                       "why": "if/then/else 是 XPath 2.0 条件表达式"}),
    ("fault:xpath2-except",   '//li except //li[@id="a"]',           {"expect_raises": True, "type": "raises",
                                                                       "why": "except 集合运算是 XPath 2.0"}),
    ("fault:bad-syntax",      '//li[',                                {"expect_raises": True, "type": "raises",
                                                                       "why": "语法错误必须报错而不是静默返回空集"}),
]


def run_case(xp, spec):
    """执行一条，返回 (status, detail)。status ∈ PASS/WRONG/UNSUPPORTED_OK/UNSUPPORTED_WRONG/ERROR."""
    typ = spec["type"]
    try:
        res = tree.xpath(xp)
    except etree.XPathError as ex:
        if typ == "raises":
            # 找茬 case：期望抛错 —— 抛了就是 PASS（引擎诚实拒绝，未静默返回错集）
            return "PASS", {"raised": type(ex).__name__ + ": " + str(ex)[:120]}
        return "ERROR", {"raised": type(ex).__name__ + ": " + str(ex)[:120]}
    except Exception as ex:  # noqa
        if typ == "raises":
            return "PASS", {"raised": type(ex).__name__ + ": " + str(ex)[:120]}
        return "ERROR", {"raised": type(ex).__name__ + ": " + str(ex)[:120]}

    # 没抛错
    if typ == "raises":
        # 找茬 case 却没抛错 = 静默接受了不该支持的语法（危险）
        return "SILENT_ACCEPT", {"returned": ids(res) if isinstance(res, list) else res}

    if typ == "ids":
        got = ids(res) if isinstance(res, list) else [repr(res)]
        ok = got == spec["expect"]
        return ("PASS" if ok else "WRONG"), {"returned": got, "expected": spec["expect"]}

    if typ == "scalar":
        exp = spec["expect"]
        # 数值比较容差
        if isinstance(exp, float) and isinstance(res, (int, float)):
            ok = abs(float(res) - exp) < 1e-9
        else:
            ok = res == exp
        return ("PASS" if ok else "WRONG"), {"returned": res, "expected": exp}

    return "ERROR", {"note": "unknown type"}


def main():
    results = []
    tally = {}
    for cat, xp, spec in MATRIX:
        status, detail = run_case(xp, spec)
        tally[status] = tally.get(status, 0) + 1
        row = {"category": cat, "xpath": xp, "status": status}
        row.update(detail)
        if "why" in spec:
            row["why"] = spec["why"]
        results.append(row)

    # 分类小计（全部由运行计算）
    n_total = len(MATRIX)
    n_fault = sum(1 for c, _, _ in MATRIX if c.startswith("fault:"))
    n_functional = n_total - n_fault
    n_pass = tally.get("PASS", 0)
    n_fault_pass = sum(1 for r in results if r["category"].startswith("fault:") and r["status"] == "PASS")

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "xpath_engine": "libxml2 XPath 1.0",
            "note": "PASS/WRONG/SILENT_ACCEPT computed from run; expected sets pre-registered in source before running",
            "n_total": n_total,
            "n_functional": n_functional,
            "n_fault_finding": n_fault,
        },
        "tally": tally,
        "computed": {
            "functional_pass": n_pass - n_fault_pass,
            "functional_total": n_functional,
            "fault_pass": n_fault_pass,
            "fault_total": n_fault,
            "all_pass_after_fault_finding": (n_pass == n_total),
        },
        "results": results,
    }
    dst = os.path.join(RAW, "xpath_matrix.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"tally: {tally}")
    print(f"functional PASS {out['computed']['functional_pass']}/{n_functional}, "
          f"fault-finding PASS {n_fault_pass}/{n_fault}")


if __name__ == "__main__":
    main()
