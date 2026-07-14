#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两套 API 行为对比：lxml.etree（严格 XML）vs lxml.html（宽容 HTML）+ recover=True 容错。

预注册若干「同一畸形输入」，写死每套 API 的**预期行为类别**（raises / recovers / ...），
再跑，看实测是否符合。结果字段（outcome / recovered_root / n_recovered）全部由运行计算。

维度：
1. 严格 XML 解析器对畸形输入 —— 默认 raise。
2. recover=True —— 是否吞掉错误并尽力恢复。
3. lxml.html —— HTML5 宽容模式，对同样输入是否直接接受。
4. error_log —— recover 后能否枚举被吞掉的错误（lxml 独有的诊断能力）。
"""
import json
import os
import sys
from lxml import etree
import lxml.html

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

# (name, input, 预期: etree严格 / etree-recover / html宽容 三档行为标签)
CASES = [
    ("unclosed_tag",       "<root><a>text</root>",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
    ("mismatched_nesting",  "<root><b><i>x</b></i></root>",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
    ("undefined_entity",    "<root>&nbsp;</root>",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
    ("bare_ampersand",      "<root>Tom & Jerry</root>",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
    ("multiple_roots",      "<a>1</a><b>2</b>",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
    ("well_formed_xml",     "<root><a>ok</a></root>",
     {"etree_strict": "accepts", "etree_recover": "accepts", "html": "accepts"}),
    ("html_boolean_attr",   "<input disabled><p>hi",
     {"etree_strict": "raises", "etree_recover": "recovers", "html": "accepts"}),
]


def try_etree(xml_bytes, recover):
    parser = etree.XMLParser(recover=recover)
    try:
        root = etree.fromstring(xml_bytes, parser)
        if root is None:
            return {"outcome": "recovered_none", "root_tag": None,
                    "n_errors_logged": len(parser.error_log)}
        return {"outcome": "ok" if not recover else "recovered",
                "root_tag": root.tag,
                "n_descendants": len(list(root.iter())),
                "n_errors_logged": len(parser.error_log),
                "first_error": (str(parser.error_log[0]) if len(parser.error_log) else None)}
    except etree.XMLSyntaxError as ex:
        return {"outcome": "raised", "error": str(ex)[:140],
                "n_errors_logged": len(parser.error_log)}


def try_html(s):
    try:
        root = lxml.html.fromstring(s)
        return {"outcome": "ok", "root_tag": root.tag,
                "n_descendants": len(list(root.iter()))}
    except Exception as ex:  # noqa
        return {"outcome": "raised", "error": type(ex).__name__ + ": " + str(ex)[:120]}


def classify(res):
    """把原始 outcome 映射到 raises/recovers/accepts 标签，便于和预期比对。
    判据由实测数据驱动：raise 了→raises；未 raise 但 error_log 非空（吞了错并恢复）→recovers；
    未 raise 且 error_log 为空（本就合法，无需恢复）→accepts。"""
    o = res["outcome"]
    if o == "raised":
        return "raises"
    if res.get("n_errors_logged", 0) > 0:
        return "recovers"
    return "accepts"


def main():
    results = []
    n_match = 0
    for name, s, expect in CASES:
        xml_bytes = s.encode("utf-8")
        r_strict = try_etree(xml_bytes, recover=False)
        r_recover = try_etree(xml_bytes, recover=True)
        r_html = try_html(s)

        actual = {
            "etree_strict": classify(r_strict),
            "etree_recover": classify(r_recover),
            "html": classify(r_html),
        }
        matches = {k: (actual[k] == expect[k]) for k in expect}
        all_match = all(matches.values())
        n_match += 1 if all_match else 0

        results.append({
            "case": name,
            "input": s,
            "expected_behavior": expect,
            "actual_behavior": actual,
            "matches_expectation": matches,
            "all_match": all_match,
            "detail": {
                "etree_strict": r_strict,
                "etree_recover": r_recover,
                "lxml_html": r_html,
            },
        })

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "note": "behavior labels (raises/recovers/accepts) computed from run; "
                    "expected labels pre-registered before running",
        },
        "computed": {
            "cases_matching_prereg": n_match,
            "cases_total": len(CASES),
        },
        "results": results,
    }
    dst = os.path.join(RAW, "two_api_behavior.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"cases matching pre-registration: {n_match}/{len(CASES)}")
    for r in results:
        flag = "OK" if r["all_match"] else "DIVERGES"
        print(f"  [{flag}] {r['case']:20s} strict={r['actual_behavior']['etree_strict']:9s}"
              f" recover={r['actual_behavior']['etree_recover']:9s} html={r['actual_behavior']['html']}")


if __name__ == "__main__":
    main()
