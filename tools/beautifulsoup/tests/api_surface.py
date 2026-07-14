#!/usr/bin/env python3
"""BeautifulSoup API 易用性 / 导航 / 检索能力矩阵 —— bs4 的核心卖点。

每个 API 用一个固定 fixture 跑一次, 记录返回值。`ok` 字段由运行时把实际返回
与预期比对算出 (闸门 3, 非手写常量)。这不是计时测试, 是"能力/保真度"测试。

输出: artifacts/raw/api_surface.json
"""
import json
import os
import sys
import warnings

from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "artifacts", "raw", "api_surface.json")

FIXTURE = """
<html><head><title>Doc Title</title></head>
<body>
  <div id="main" class="container primary">
    <h1 class="hdr">Heading One</h1>
    <p class="lead">First <b>bold</b> paragraph.</p>
    <p class="lead" data-role="LEAD">Second paragraph with <a href="/link1">link1</a>.</p>
    <ul>
      <li>alpha</li>
      <li>beta</li>
      <li>gamma</li>
    </ul>
    <input type="checkbox" disabled>
    <a href="/link2" class="btn">link2</a>
    <!-- a comment node -->
  </div>
</body></html>
"""


def main():
    import bs4

    soup = BeautifulSoup(FIXTURE, "html.parser")
    probes = {}

    def rec(name, got, expect, note=""):
        probes[name] = {
            "got": got if isinstance(got, (str, int, float, bool, list, type(None))) else repr(got),
            "expect": expect,
            "ok": got == expect,  # 运行时算出
            "note": note,
        }

    # --- find / find_all ---
    rec("find_by_tag", soup.find("h1").get_text(strip=True), "Heading One")
    rec("find_all_p_count", len(soup.find_all("p")), 2)
    rec("find_by_id", soup.find(id="main")["class"], ["container", "primary"])
    rec("find_by_class", len(soup.find_all("p", class_="lead")), 2)
    # 注意: get_text(strip=True) 逐节点 strip 后直接拼接, 节点间空格丢失
    # ("with" + "link1" -> "withlink1") —— 与 selectolax 的 strip-space 陷阱同理
    rec("find_by_attr", soup.find(attrs={"data-role": "LEAD"}).get_text(strip=True),
        "Second paragraph withlink1.",
        note="strip=True 逐节点拼接丢空格; 需 separator=' ' 保词界")
    rec("find_all_limit", len(soup.find_all("li", limit=2)), 2)
    # find 支持函数谓词 (bs4 特色)
    rec("find_with_lambda",
        soup.find(lambda t: t.name == "a" and "btn" in (t.get("class") or [])).get("href"),
        "/link2")

    # --- CSS select (soupsieve) ---
    rec("select_css_class", len(soup.select("p.lead")), 2)
    rec("select_descendant", len(soup.select("div#main a")), 2)
    rec("select_child_combinator", len(soup.select("ul > li")), 3)
    rec("select_attr_selector", soup.select_one("a[href='/link1']").get_text(), "link1")
    rec("select_nth_child", soup.select_one("li:nth-child(2)").get_text(), "beta")
    rec("select_one_missing", soup.select_one(".nonexistent"), None)

    # --- tree navigation (bs4 卖点) ---
    lead = soup.find("p", class_="lead")
    rec("parent_name", lead.parent.get("id"), "main")
    rec("next_sibling_tag",
        lead.find_next_sibling("p").get("data-role"), "LEAD")
    ul = soup.find("ul")
    rec("children_count", len([c for c in ul.find_all("li")]), 3)
    rec("descendants_has_bold", any(t.name == "b" for t in soup.descendants if hasattr(t, "name")), True)
    # .strings / stripped_strings
    strings = list(soup.find("ul").stripped_strings)
    rec("stripped_strings", strings, ["alpha", "beta", "gamma"])
    # find_parent
    b = soup.find("b")
    rec("find_parent_chain", b.find_parent("div").get("id"), "main")

    # --- get_text 变体 ---
    rec("get_text_default", soup.find("p", class_="lead").get_text(),
        "First bold paragraph.")
    rec("get_text_separator", soup.find("ul").get_text(separator="|", strip=True),
        "alpha|beta|gamma")

    # --- 属性访问 / 布尔属性陷阱 (对照 selectolax 的 boolean-attr 陷阱) ---
    cb = soup.find("input")
    rec("bool_attr_present_value", cb.get("disabled"), "")  # bs4: 空串, 非 None
    rec("bool_attr_membership", "disabled" in cb.attrs, True)
    rec("missing_attr_get_default", cb.get("nonexistent", "DEF"), "DEF")
    rec("multivalue_class_is_list", soup.find(id="main").get("class"), ["container", "primary"])

    # --- 修改 / 序列化 (bs4 是可读写 DOM) ---
    soup2 = BeautifulSoup("<p>Hello <b>World</b></p>", "html.parser")
    soup2.find("b").decompose()
    rec("decompose_removes", str(soup2), "<p>Hello </p>")
    soup3 = BeautifulSoup("<p>x</p>", "html.parser")
    new = soup3.new_tag("a", href="/new")
    new.string = "added"
    soup3.p.append(new)
    rec("new_tag_append", str(soup3), '<p>x<a href="/new">added</a></p>')
    soup4 = BeautifulSoup("<div><span>keep</span></div>", "html.parser")
    soup4.span.unwrap()
    rec("unwrap", str(soup4), "<div>keep</div>")

    # --- bs4 版本属性 (对照 selectolax __version__ 探针) ---
    rec("has_version_attr", hasattr(bs4, "__version__"), True)

    n_ok = sum(1 for p in probes.values() if p["ok"])
    out = {
        "meta": {
            "bs4_version": bs4.__version__,
            "python": sys.version.split()[0],
            "n_probes": len(probes),
            "note": "能力/保真度探针; ok 字段运行时比对算出, 非手写",
        },
        "n_ok": n_ok,
        "n_probes": len(probes),
        "probes": probes,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    fails = [k for k, v in probes.items() if not v["ok"]]
    print(json.dumps({"n_ok": n_ok, "n_probes": len(probes), "fails": fails}, ensure_ascii=False))


if __name__ == "__main__":
    main()
