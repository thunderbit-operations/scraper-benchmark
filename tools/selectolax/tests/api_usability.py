#!/usr/bin/env python3
"""API / usability + README claim verification.

Probes concrete behaviors a scraper author cares about:
  1. Missing element: css_first returns None (vs exception)?
  2. Missing attribute: .attributes.get() vs KeyError?
  3. DOM modification: decompose/remove, insert, replace_with, strip_tags, unwrap
  4. Serialization back to HTML: .html, html_pretty (Lexbor)
  5. Node-type introspection (Lexbor only): is_text_node etc.
  6. text() options: deep vs shallow, separator, strip
  7. attributes for boolean attrs (value None?)
  8. README claims: advanced selector example output, :lexbor-contains
Each probe records exact behavior for both engines where relevant.
"""
import json
import os

RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)
res = {}


def rec(key, val):
    res[key] = val
    print(f"{key}: {val}")


def main():
    import selectolax
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser

    # 0. __version__ probe (measured, not asserted).
    # v2 claimed `selectolax.__version__` raises AttributeError -- this was FALSE.
    # Record the actual result so the doc reflects reality.
    try:
        rec("module_has___version__", hasattr(selectolax, "__version__"))
        rec("module___version___value", repr(getattr(selectolax, "__version__", "<MISSING>")))
    except Exception as e:
        rec("module___version___value", "EXC:" + repr(e))

    H = '<html><body><div class="c"><p id="p1">Hello <b>World</b></p>' \
        '<a id="a1" href="/x" data-flag>link</a><input id="i" disabled></div></body></html>'

    # 1. missing element
    for eng, cls in [("lexbor", LexborHTMLParser), ("modest", HTMLParser)]:
        t = cls(H)
        rec(f"missing_css_first_returns[{eng}]", repr(t.css_first("nonexistent")))
        rec(f"missing_css_returns[{eng}]", repr(t.css("nonexistent")))

    # 2. missing attribute
    t = LexborHTMLParser(H)
    a = t.css_first("a#a1")
    rec("attributes_dict", a.attributes)
    rec("boolean_attr_value(data-flag)", repr(a.attributes.get("data-flag")))
    try:
        rec("missing_attr_get_default", repr(a.attributes.get("nope", "DEFAULT")))
    except Exception as e:
        rec("missing_attr_get_default", "EXC:" + repr(e))
    inp = t.css_first("input#i")
    rec("disabled_bool_attr_value", repr(inp.attributes.get("disabled")))

    # 3. text options
    p = t.css_first("p#p1")
    rec("text_deep_default", repr(p.text()))
    try:
        rec("text_deep_false", repr(p.text(deep=False)))
    except Exception as e:
        rec("text_deep_false", "EXC:" + repr(e))
    try:
        rec("text_separator", repr(p.text(separator="|")))
    except Exception as e:
        rec("text_separator", "EXC:" + repr(e))
    try:
        rec("text_strip", repr(p.text(strip=True)))
    except Exception as e:
        rec("text_strip", "EXC:" + repr(e))

    # 4. DOM modification: decompose
    t2 = LexborHTMLParser(H)
    b = t2.css_first("b")
    b.decompose()
    rec("after_decompose_b_html", t2.css_first("p#p1").html)

    # remove()
    t3 = LexborHTMLParser(H)
    t3.css_first("a#a1").remove()
    rec("after_remove_a_present", t3.css_first("a#a1") is None)

    # strip_tags
    t4 = LexborHTMLParser(H)
    t4.strip_tags(["b"])
    rec("after_strip_tags_b", t4.css_first("p#p1").html)

    # unwrap
    t5 = LexborHTMLParser(H)
    try:
        t5.css_first("b").unwrap()
        rec("after_unwrap_b", t5.css_first("p#p1").html)
    except Exception as e:
        rec("after_unwrap_b", "EXC:" + repr(e))

    # replace_with
    t6 = LexborHTMLParser(H)
    try:
        t6.css_first("b").replace_with("PLAIN")
        rec("after_replace_with", t6.css_first("p#p1").html)
    except Exception as e:
        rec("after_replace_with", "EXC:" + repr(e))

    # insert_before / insert_after
    t7 = LexborHTMLParser(H)
    try:
        t7.css_first("b").insert_before("[before]")
        rec("after_insert_before", t7.css_first("p#p1").html)
    except Exception as e:
        rec("after_insert_before", "EXC:" + repr(e))

    # 5. serialization
    rec("html_roundtrip", LexborHTMLParser(H).html[:80])
    try:
        rec("html_pretty_available", LexborHTMLParser(H).html_pretty()[:60])
    except Exception as e:
        rec("html_pretty_available", "EXC:" + repr(e))

    # 6. Node-type introspection (Lexbor)
    t8 = LexborHTMLParser("<div>text<!--c--><p>x</p></div>")
    div = t8.css_first("div")
    kinds = []
    for node in (div.iter(include_text=True) if _accepts_include_text(div) else div.iter()):
        # is_text_node / is_comment_node / is_element_node are PROPERTIES on Lexbor
        kinds.append({
            "tag": node.tag,
            "is_text": bool(node.is_text_node) if hasattr(node, "is_text_node") else "n/a",
            "is_comment": bool(node.is_comment_node) if hasattr(node, "is_comment_node") else "n/a",
            "is_element": bool(node.is_element_node) if hasattr(node, "is_element_node") else "n/a",
        })
    rec("lexbor_child_node_kinds", kinds)

    # 7. strip_tags on whole doc / unwrap_tags
    t9 = LexborHTMLParser(H)
    try:
        t9.unwrap_tags(["div"])
        rec("unwrap_tags_div_ok", "ok")
    except Exception as e:
        rec("unwrap_tags_div_ok", "EXC:" + repr(e))

    # 8. README advanced selector reproduction
    html = "<div><p id=p1><p id=p2><p id=p3><a>link</a><p id=p4><p id=p5>text<p id=p6></div>"
    selector = "div > :nth-child(2n+1):not(:has(a))"
    got = []
    for node in LexborHTMLParser(html).css(selector):
        got.append({"id": node.attributes.get("id"), "text": node.text(), "tag": node.tag})
    rec("readme_advanced_selector_result", got)
    rec("readme_advanced_selector_matches_doc", [g["id"] for g in got] == ["p1", "p5"])

    with open(os.path.join(RAW, "api_usability.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    print("\nwritten", os.path.join(RAW, "api_usability.json"))


def _accepts_include_text(node):
    import inspect
    try:
        return "include_text" in inspect.signature(node.iter).parameters
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    main()
