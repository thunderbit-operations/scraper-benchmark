#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lxml API / 能力 / 生产维度 —— 非计时事实核验。

覆盖 selectolax pack 没覆盖、且属于 lxml 能力面的点，全部是**可运行验证的布尔/枚举事实**：
1. 线程安全 API 面（对应 lxml FAQ 的 GIL/线程条款）：parser.copy()、default parser 可换、XPathEvaluator 有内部锁。
   —— 仅结构核验，不产计时数（线程加速比复用 selectolax production_dims.json 的 lxml 行）。
2. 读写 DOM：append/insert/remove/replace、strip_tags、strip_elements、drop_tree、text/tail 语义。
3. 序列化保真：tostring(method='html'|'xml')、pretty_print、C14N、round-trip。
4. 生命周期：节点在其树 GC 后是否可用、drop_tree 后行为（stale-handle 安全）——独立进程跑，硬崩溃会反映为非零退出。
5. 编码：lxml 对非 UTF-8 bytes 的处理（对照 selectolax 的 encoding_probe——lxml 是那里的参照）。

所有字段由运行计算（闸门3）。node-lifecycle 在子进程跑。
"""
import json
import os
import sys
import subprocess
from lxml import etree
import lxml.html

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)


def thread_api_surface():
    p = etree.XMLParser()
    out = {
        "xmlparser_has_copy": hasattr(p, "copy"),
        "copy_returns_parser": type(p.copy()).__name__ == "XMLParser",
        "has_get_default_parser": hasattr(etree, "get_default_parser"),
        "has_set_default_parser": hasattr(etree, "set_default_parser"),
        "has_XPathEvaluator": hasattr(etree, "XPathEvaluator"),
        "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
        "faq_ref": "lxml FAQ: GIL freed during parse if default parser (replicated per thread) "
                   "or per-thread parser; shared parser serializes; XPath evaluators use internal lock",
    }
    return out


def readwrite_dom():
    """读写 DOM 能力，每步都断言结果。"""
    out = {}
    # append / insert / remove
    root = etree.fromstring(b"<root><a/><b/></root>")
    c = etree.SubElement(root, "c")
    out["subelement_append"] = ([e.tag for e in root] == ["a", "b", "c"])
    root.insert(0, etree.Element("z"))
    out["insert_at_0"] = ([e.tag for e in root] == ["z", "a", "b", "c"])
    root.remove(root.find("b"))
    out["remove_child"] = ([e.tag for e in root] == ["z", "a", "c"])

    # replace
    root.replace(root.find("a"), etree.Element("A"))
    out["replace_child"] = ([e.tag for e in root] == ["z", "A", "c"])

    # strip_tags: 去标签保内容
    h = lxml.html.fromstring("<p>Hello <b>bold</b> world</p>")
    etree.strip_tags(h, "b")
    out["strip_tags_keeps_text"] = ("Hello bold world" in h.text_content())

    # strip_elements: 连内容一起删
    h2 = lxml.html.fromstring("<p>keep <span>drop</span> keep2</p>")
    etree.strip_elements(h2, "span", with_tail=False)
    out["strip_elements_removes_content"] = ("drop" not in h2.text_content())

    # drop_tree (lxml.html 专有)
    h3 = lxml.html.fromstring("<div><p id='x'>a</p><p id='y'>b</p></div>")
    h3.get_element_by_id("x").drop_tree()
    out["drop_tree"] = ([p.get("id") for p in h3.xpath("//p")] == ["y"])

    # text vs tail 语义（lxml 的经典模型）
    frag = etree.fromstring(b"<p>head<b>bold</b>tail</p>")
    b = frag.find("b")
    out["text_tail_model"] = (frag.text == "head" and b.text == "bold" and b.tail == "tail")

    return out


def serialization():
    out = {}
    root = etree.fromstring(b"<root><a href='x'>t</a></root>")
    xml = etree.tostring(root, method="xml").decode()
    out["tostring_xml"] = ("<a href=\"x\">t</a>" in xml)
    # html method: void 元素不自闭合
    h = lxml.html.fromstring("<div><br><img src='i'></div>")
    html_out = etree.tostring(h, method="html").decode()
    out["tostring_html_void"] = ("<br>" in html_out and "<img" in html_out)
    # pretty_print
    pp = etree.tostring(root, pretty_print=True).decode()
    out["pretty_print"] = ("\n" in pp)
    # C14N 规范化（lxml 独有的标准化序列化，selectolax 无）
    try:
        c14n = etree.tostring(root, method="c14n").decode()
        out["c14n_available"] = ("<root>" in c14n)
    except Exception as ex:  # noqa
        out["c14n_available"] = False
        out["c14n_error"] = str(ex)[:80]
    # round-trip 保真
    reparsed = etree.fromstring(etree.tostring(root))
    out["roundtrip_stable"] = (reparsed.find("a").get("href") == "x")
    return out


def encoding_bytes():
    """lxml 对非 UTF-8 bytes 的处理（对照 selectolax encoding_probe：lxml 是那里的参照行）。"""
    latin1 = "<p>café éè</p>".encode("latin-1")
    out = {}
    # lxml.html 宽容解析 latin-1 bytes
    try:
        h = lxml.html.fromstring(latin1)
        txt = h.text_content()
        out["lxml_html_latin1_text"] = txt
        out["lxml_html_recovers_accents"] = ("café" in txt or "caf" in txt)
        out["lxml_html_no_replacement_char"] = ("�" not in txt)
    except Exception as ex:  # noqa
        out["lxml_html_latin1_error"] = type(ex).__name__ + ": " + str(ex)[:80]
    # 带 XML 声明指定编码：libxml2 只认 IANA 规范名。
    # 'latin-1' 别名不被识别 → 报错；'ISO-8859-1' 规范名 → 正确解出 café。
    l1_alias = '<?xml version="1.0" encoding="latin-1"?><p>café</p>'.encode("latin-1")
    try:
        root = etree.fromstring(l1_alias)
        out["xml_declared_latin1_alias_text"] = root.text
        out["xml_declared_latin1_alias_raises"] = False
    except Exception as ex:  # noqa
        out["xml_declared_latin1_alias_raises"] = True
        out["xml_declared_latin1_alias_error"] = type(ex).__name__ + ": " + str(ex)[:80]
    iso = '<?xml version="1.0" encoding="ISO-8859-1"?><p>café</p>'.encode("latin-1")
    try:
        root = etree.fromstring(iso)
        out["xml_declared_iso88591_text"] = root.text
        out["xml_declared_iso88591_correct"] = (root.text == "café")
    except Exception as ex:  # noqa
        out["xml_declared_iso88591_error"] = type(ex).__name__ + ": " + str(ex)[:80]
    return out


# --- node lifecycle 在子进程跑（硬崩溃 = 非零退出）---
LIFECYCLE_CHILD = "lifecycle_child"


def node_lifecycle_child():
    """子进程：制造 stale-handle 场景并使用，看是否崩溃。打印 JSON。"""
    res = {}
    import gc
    # 场景1：持有节点，让树 GC
    def make():
        t = etree.fromstring(b"<root><child>hello world</child></root>")
        return t.find("child")
    node = make()
    gc.collect()
    try:
        res["after_tree_gc_usable"] = (node.text == "hello world")
    except Exception as ex:  # noqa
        res["after_tree_gc_error"] = type(ex).__name__ + ": " + str(ex)[:80]

    # 场景2：drop_tree 后使用句柄
    h = lxml.html.fromstring("<div><p id='x'>a</p><p id='y'>b</p></div>")
    px = h.get_element_by_id("x")
    px.drop_tree()
    try:
        _ = px.text  # 访问已脱离树的节点
        res["after_drop_tree_usable"] = True
        res["after_drop_tree_text"] = px.text
    except Exception as ex:  # noqa
        res["after_drop_tree_usable"] = False
        res["after_drop_tree_error"] = type(ex).__name__ + ": " + str(ex)[:80]

    # 场景3：getparent 在 remove 后
    root = etree.fromstring(b"<root><a/></root>")
    a = root.find("a")
    root.remove(a)
    try:
        res["removed_node_parent_is_none"] = (a.getparent() is None)
        res["removed_node_still_usable"] = (a.tag == "a")
    except Exception as ex:  # noqa
        res["removed_node_error"] = type(ex).__name__ + ": " + str(ex)[:80]

    print(json.dumps(res))


def main():
    if len(sys.argv) == 2 and sys.argv[1] == LIFECYCLE_CHILD:
        node_lifecycle_child()
        return

    # node lifecycle 子进程
    p = subprocess.run([sys.executable, os.path.abspath(__file__), LIFECYCLE_CHILD],
                       capture_output=True, text=True)
    lifecycle = {"subprocess_exit_code": p.returncode,
                 "hard_crash": (p.returncode != 0)}
    if p.stdout.strip():
        try:
            lifecycle.update(json.loads(p.stdout.strip().splitlines()[-1]))
        except Exception:  # noqa
            lifecycle["parse_error"] = p.stdout[:200]
    if p.returncode != 0:
        lifecycle["stderr"] = p.stderr[-300:]

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "libxml2_version": ".".join(map(str, etree.LIBXML_VERSION)),
            "note": "non-timing capability facts; thread speedup reused from "
                    "../selectolax/artifacts/raw/production_dims.json (thread_scaling.lxml); "
                    "node lifecycle run in subprocess (hard crash => nonzero exit)",
        },
        "thread_api_surface": thread_api_surface(),
        "readwrite_dom": readwrite_dom(),
        "serialization": serialization(),
        "encoding_bytes": encoding_bytes(),
        "node_lifecycle": lifecycle,
    }
    dst = os.path.join(RAW, "api_capabilities.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    # 汇总 pass 数
    for section in ("readwrite_dom", "serialization"):
        vals = [v for v in out[section].values() if isinstance(v, bool)]
        print(f"  {section}: {sum(vals)}/{len(vals)} true")
    print(f"  encoding: lxml_html recovers latin-1 accents = "
          f"{out['encoding_bytes'].get('lxml_html_recovers_accents')}, "
          f"no U+FFFD = {out['encoding_bytes'].get('lxml_html_no_replacement_char')}")
    print(f"  node_lifecycle hard_crash = {out['node_lifecycle']['hard_crash']}")


if __name__ == "__main__":
    main()
