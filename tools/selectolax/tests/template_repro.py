#!/usr/bin/env python3
"""FINDING-14 minimal reproduction (executable): Lexbor does not descend into
`<template>` content, while Modest / lxml / both BeautifulSoup backends do.

This is the runnable check behind the doc's minimal-repro block, so the claim
rests on committed output rather than a hand-typed code sample. Reproduces:
  1. css("a") count across five parsers on a 3-anchor fixture with one anchor
     inside a <template> (spec-inert DocumentFragment).
  2. The Lexbor template node's content being effectively unreachable via the
     API: template_node.css("a") == [], .child is None, .inner_html == '' even
     though .html shows the inner <a>.
Output -> results/template_repro.json (every field computed at runtime).
"""
import json
import os
import sys

RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

FIXTURE = ('<a href="/outside">o</a>'
           '<template><a href="/inside">t</a></template>'
           '<a href="/normal">n</a>')


def count_css_a():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser
    import lxml.html
    from bs4 import BeautifulSoup
    return {
        "selectolax_lexbor": len(LexborHTMLParser(FIXTURE).css("a")),
        "selectolax_modest": len(HTMLParser(FIXTURE).css("a")),
        "lxml_html": len(lxml.html.fromstring(FIXTURE).cssselect("a")),
        "bs4_html_parser": len(BeautifulSoup(FIXTURE, "html.parser").select("a")),
        "bs4_lxml": len(BeautifulSoup(FIXTURE, "lxml").select("a")),
    }


def lexbor_template_reachability():
    from selectolax.lexbor import LexborHTMLParser
    tree = LexborHTMLParser(FIXTURE)
    tmpl = tree.css_first("template")
    return {
        "template_node_found": tmpl is not None,
        "template_css_a_len": len(tmpl.css("a")) if tmpl else None,
        "template_child_is_none": (tmpl.child is None) if tmpl else None,
        "template_inner_html_repr": repr(tmpl.inner_html) if tmpl else None,
        "template_html_contains_inside_anchor": ("/inside" in (tmpl.html or "")) if tmpl else None,
    }


def main():
    counts = count_css_a()
    reach = lexbor_template_reachability()
    out = {
        "meta": {"python": sys.version.split()[0],
                 "fixture": FIXTURE,
                 "expected": "lexbor=2 (misses /inside); modest/lxml/bs4=3"},
        "css_a_counts": counts,
        "lexbor_only_drops_template_anchor": bool(
            counts["selectolax_lexbor"] == 2
            and counts["selectolax_modest"] == 3
            and counts["lxml_html"] == 3
            and counts["bs4_html_parser"] == 3
            and counts["bs4_lxml"] == 3),
        "lexbor_template_content_unreachable_via_api": bool(
            reach["template_css_a_len"] == 0
            and reach["template_child_is_none"] is True
            and reach["template_inner_html_repr"] == "''"
            and reach["template_html_contains_inside_anchor"] is True),
        "lexbor_template_reachability": reach,
    }
    path = os.path.join(RAW, "template_repro.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    for k, v in counts.items():
        print(f"[TEMPLATE] {k:<18} css('a') -> {v}")
    print(f"[TEMPLATE] lexbor-only-drops-template-anchor: {out['lexbor_only_drops_template_anchor']}")
    print(f"[TEMPLATE] lexbor template unreachable via API: {out['lexbor_template_content_unreachable_via_api']}")
    print("written", path)


if __name__ == "__main__":
    main()
