#!/usr/bin/env python3
"""BeautifulSoup 三后端畸形 HTML 修复矩阵 (反偏向: 预注册样本 + 写死预期后再跑).

方法论 v3 Part 3 §9: case 集预注册 —— 每条畸形样本先写死一个"结构断言"
(用后端无关的、可判定的谓词表达"修复后应满足什么"), 再跑三后端 (html.parser /
lxml / html5lib), 记录各自 verdict。断言在跑之前就固定 (见 CASES 列表), 结果字段
`meets_expectation` 由运行时比对算出, 不是手写常量 (闸门 3)。

每个 case 的 `expect` 是一个可调用谓词, 接收 (soup) 返回 bool。谓词表达的是
"一个合理的容错解析器应当满足的最小结构性质", 对三后端一视同仁 —— 谁满足谁不满足
由运行决定, 不预判赢家。

输出: artifacts/raw/malformed_matrix.json
"""
import json
import os
import sys
import warnings

from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")  # html5lib/bs4 偶发 markup-resembles-locator 警告, 不影响结构

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "artifacts", "raw", "malformed_matrix.json")

BACKENDS = ["html.parser", "lxml", "html5lib"]


def parse(markup, backend):
    return BeautifulSoup(markup, backend)


# ---------------------------------------------------------------------------
# 预注册 case 集: (id, 描述, markup, expect 谓词)
# expect 谓词在写代码时就固定, 表达"修复后应满足的结构性质", 后端无关。
# ---------------------------------------------------------------------------
def _has_tag(soup, name):
    return soup.find(name) is not None


def _text_reachable(soup, needle):
    return needle in soup.get_text()


CASES = [
    # 1. 未闭合 <p> —— 期望三个段落文本都可达 (无论树形如何)
    dict(
        id="unclosed_p",
        desc="连续未闭合 <p>",
        markup="<div><p>one<p>two<p>three</div>",
        expect=lambda s: all(_text_reachable(s, w) for w in ("one", "two", "three"))
        and len(s.find_all("p")) == 3,
    ),
    # 2. 错误嵌套 <b><i></b></i> —— 期望 b 和 i 都存在, 文本可达
    dict(
        id="misnested_bi",
        desc="交叉错误嵌套 <b><i></b></i>",
        markup="<p><b>bold<i>both</b>italic</i></p>",
        expect=lambda s: _has_tag(s, "b")
        and _has_tag(s, "i")
        and _text_reachable(s, "both"),
    ),
    # 3. 表格缺 <tbody>/未闭合 <td> —— 期望能取到所有单元格文本
    dict(
        id="broken_table",
        desc="缺 tbody + 未闭合 td/tr",
        markup="<table><tr><td>a<td>b<tr><td>c<td>d</table>",
        expect=lambda s: {c.get_text() for c in s.find_all("td")} == {"a", "b", "c", "d"},
    ),
    # 4. 完全缺 <html>/<head>/<body> —— 期望内容仍在, 文本可达
    dict(
        id="no_skeleton",
        desc="裸内容, 无 html/head/body",
        markup="<title>T</title><p>body content</p>",
        expect=lambda s: _text_reachable(s, "body content") and _has_tag(s, "p"),
    ),
    # 5. 属性未加引号 + 含空格 —— 期望 href 属性被正确解析
    dict(
        id="unquoted_attr",
        desc="属性未加引号",
        markup="<a href=/path/to/x class=btn>link</a>",
        expect=lambda s: s.find("a") is not None
        and s.find("a").get("href") == "/path/to/x",
    ),
    # 6. 乱序标签 (</p> 出现在 <p> 前) —— 期望不崩溃, 文本可达
    dict(
        id="stray_close",
        desc="孤立闭合标签在前",
        markup="</p></div>orphan<p>real</p>",
        expect=lambda s: _text_reachable(s, "orphan") and _text_reachable(s, "real"),
    ),
    # 7. <li> 未闭合 + 缺 <ul> 包裹 —— 期望三个 li 都在
    dict(
        id="bare_li",
        desc="裸 li 无 ul, 未闭合",
        markup="<li>a<li>b<li>c",
        expect=lambda s: len(s.find_all("li")) == 3
        and {li.get_text() for li in s.find_all("li")} == {"a", "b", "c"},
    ),
    # 8. <script> 里含 < > 未转义 —— 期望 script 内容不被当标签解析, 后续 <p> 独立
    dict(
        id="script_lt_gt",
        desc="script 内含裸 < >",
        markup="<script>if (a < b && c > d) {}</script><p>after</p>",
        expect=lambda s: _text_reachable(s, "after")
        and s.find("p") is not None
        and s.find("p").get_text() == "after",
    ),
    # 9. 注释未闭合 —— 期望不吞掉整个文档 (至少能拿到注释前内容)
    dict(
        id="unclosed_comment",
        desc="注释未闭合 <!--",
        markup="<p>before</p><!-- dangling comment <p>inside</p>",
        expect=lambda s: _text_reachable(s, "before"),
    ),
    # 10. 属性重复 —— 期望取到值 (HTML 规范: 保留第一个)
    dict(
        id="dup_attr",
        desc="重复属性 id",
        markup='<div id="first" id="second">x</div>',
        expect=lambda s: s.find("div") is not None
        and s.find("div").get("id") == "first",
    ),
    # 11. <form> 嵌 <form> (HTML 禁止嵌套 form) —— 期望内层输入仍可达
    dict(
        id="nested_form",
        desc="嵌套 form (规范禁止)",
        markup='<form><input name=a><form><input name=b></form></form>',
        expect=lambda s: len(s.find_all("input")) == 2,
    ),
    # 12. 大小写混合标签 + 未闭合 —— 期望大小写规范化后可查
    dict(
        id="mixed_case",
        desc="大小写混合 <DIV><SPAN>",
        markup="<DIV><SPAN>text</SPAN>",
        expect=lambda s: s.find("div") is not None and _text_reachable(s, "text"),
    ),
    # 13. 实体未闭合 (&amp 无分号) —— 期望文本仍可达, 不崩
    dict(
        id="bad_entity",
        desc="残缺实体 &amp 无分号",
        markup="<p>Tom &amp Jerry &copy 2024</p>",
        expect=lambda s: "Tom" in s.get_text() and "Jerry" in s.get_text(),
    ),
    # 14. <a> 里嵌块级 <div> (旧规范禁止, 新规范允许) —— 期望链接文本可达
    dict(
        id="block_in_inline",
        desc="块级元素嵌在 <a> 内",
        markup='<a href="/x"><div>block link</div></a>',
        expect=lambda s: _text_reachable(s, "block link"),
    ),
    # 15. 属性值含未转义引号 —— 期望不崩溃, 标签可识别
    dict(
        id="messy_quote",
        desc="属性值内含裸引号",
        markup='<img src="a.jpg alt="pic">next',
        expect=lambda s: _text_reachable(s, "next"),
    ),
]


def run_case(case):
    rec = {"id": case["id"], "desc": case["desc"], "backends": {}}
    for backend in BACKENDS:
        entry = {}
        try:
            soup = parse(case["markup"], backend)
            entry["parsed"] = True
            # meets_expectation 由预注册谓词运行时算出 —— 非手写常量 (闸门 3)
            try:
                entry["meets_expectation"] = bool(case["expect"](soup))
            except Exception as e:
                entry["meets_expectation"] = False
                entry["expect_error"] = f"{type(e).__name__}: {e}"
            # 记录一些结构指纹供人工核查 (计数, 非结论)
            entry["n_tags"] = len(soup.find_all(True))
            entry["text_len"] = len(soup.get_text())
        except Exception as e:
            entry["parsed"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
            entry["meets_expectation"] = False
        rec["backends"][backend] = entry
    # divergence: 三后端 meets_expectation 是否一致 (运行时算出)
    verdicts = [rec["backends"][b].get("meets_expectation") for b in BACKENDS]
    rec["all_backends_agree"] = len(set(verdicts)) == 1
    rec["n_backends_meeting"] = sum(1 for v in verdicts if v)
    return rec


def main():
    import bs4
    results = [run_case(c) for c in CASES]
    # 汇总: 每后端满足数 (运行时算出)
    per_backend = {b: sum(1 for r in results if r["backends"][b].get("meets_expectation")) for b in BACKENDS}
    divergences = [r["id"] for r in results if not r["all_backends_agree"]]
    out = {
        "meta": {
            "bs4_version": bs4.__version__,
            "python": sys.version.split()[0],
            "backends": BACKENDS,
            "n_cases": len(CASES),
            "note": "预注册畸形样本集; expect 谓词写死于源码后再跑三后端; meets_expectation 运行时算出",
        },
        "per_backend_meeting_count": per_backend,
        "divergent_case_ids": divergences,
        "cases": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps({"per_backend": per_backend, "divergences": divergences}, ensure_ascii=False))


if __name__ == "__main__":
    main()
