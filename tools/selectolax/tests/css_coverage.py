#!/usr/bin/env python3
"""Exhaustive CSS-selector coverage matrix with an explicit fault-finding pass.

Each (selector, engine) cell runs in an ISOLATED SUBPROCESS. This is required
because some engine/selector combinations abort the whole process at the C level
(e.g. selectolax-Modest on `:dir()` raises SIGABRT, not a Python exception) --
running in-process would kill the entire matrix. Subprocess isolation lets us
record that hard abort as its own outcome (PROCESS_ABORT) instead of losing the
run, and it is itself a robustness finding.

Engines (5): selectolax Lexbor, selectolax Modest, lxml(cssselect),
parsel(cssselect), soupsieve (BeautifulSoup's CSS engine).

Outcome per (selector, engine):
  PASS          - returned exactly the expected id set
  WRONG         - ran but returned wrong ids (SILENT mis-evaluation)
  UNSUPPORTED   - raised a Python exception (selector not supported)
  PROCESS_ABORT - crashed the process (C-level abort / segfault); nonzero exit

Methodology v3 Part 3 (anti-bias):
  - soupsieve added (it is in the perf matrix and supports :has()/[i]); excluding
    it manufactured a "best-in-class" gap.
  - Fault-finding pass appends selectors chosen to BREAK Lexbor (:lang(), :dir(),
    plus a two-case [a=v i] check) so a high Lexbor score is earned against
    hostile selectors, not only against selectors it was built to pass.
  - :has() divergence classified precisely: cssselect has parsed :has() since
    1.2.0 (released 2022-10-27, "with some limitations"); this pack tests
    cssselect 1.4.0. So lxml/parsel returning the wrong set here is WRONG
    ("supported but buggy evaluation"), which is worse than "unsupported"
    (cf. scrapy/cssselect#138).
"""
import json
import os
import subprocess
import sys

RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)
PY = sys.executable

# ---- child: run ONE (engine, selector, fixture) and print a JSON verdict ----
CHILD = r'''
import sys, json
engine = sys.argv[1]
sel = sys.argv[2]
fx = sys.argv[3]

def ids():
    if engine == "lexbor":
        from selectolax.lexbor import LexborHTMLParser
        return [n.attributes.get("id") for n in LexborHTMLParser(fx).css(sel) if n.attributes.get("id")]
    if engine == "modest":
        from selectolax.parser import HTMLParser
        return [n.attributes.get("id") for n in HTMLParser(fx).css(sel) if n.attributes.get("id")]
    if engine == "lxml":
        import lxml.html
        return [n.get("id") for n in lxml.html.fromstring(fx).cssselect(sel) if n.get("id")]
    if engine == "parsel":
        from parsel import Selector
        return Selector(text=fx).css(sel).xpath("@id").getall()
    if engine == "soupsieve":
        import soupsieve as sv
        from bs4 import BeautifulSoup
        return [n.get("id") for n in sv.select(sel, BeautifulSoup(fx, "html.parser")) if n.get("id")]
    raise SystemExit("unknown engine")

try:
    got = ids()
    print(json.dumps({"outcome": "RAN", "got": sorted(set(got))}))
except Exception as e:
    print(json.dumps({"outcome": "UNSUPPORTED", "err": (type(e).__name__+": "+str(e))[:160]}))
'''


# Common fixture with rich structure for most selectors
FX = """
<html><body>
<div id="wrap">
  <p id="p1" class="a" data-role="lead" title="hello world" lang="en-US">first</p>
  <p id="p2" class="a b">second</p>
  <span id="s1" class="a">span1</span>
  <p id="p3" class="c" data-role="body">third <a id="lnk" href="http://x">L</a></p>
  <p id="p4">fourth</p>
  <ul id="list">
    <li id="li1">one</li>
    <li id="li2">two</li>
    <li id="li3">three</li>
    <li id="li4">four</li>
  </ul>
  <input id="in1" type="text" disabled>
  <input id="in2" type="checkbox" checked>
</div>
</body></html>
"""

FX_LANG = ('<div id="w"><p id="p1" lang="en-US">a</p>'
           '<p id="p2" lang="fr">b</p><q id="q1" lang="en">c</q></div>')
FX_DIR = '<div id="w"><p id="p1" dir="rtl">a</p><p id="p2" dir="ltr">b</p></div>'
FX_CASE = ('<div id="w"><p id="p1" data-role="lead">x</p>'
           '<p id="p2" data-role="LEAD">y</p></div>')

# (label, selector, fixture, expected_ids_set)
CASES = [
    ("type selector", "p", FX, {"p1", "p2", "p3", "p4"}),
    ("id selector", "#p2", FX, {"p2"}),
    ("class selector", ".a", FX, {"p1", "p2", "s1"}),
    ("multiple class (chained)", ".a.b", FX, {"p2"}),
    ("grouping (comma)", "#p1, #p4", FX, {"p1", "p4"}),
    ("descendant combinator", "#wrap p", FX, {"p1", "p2", "p3", "p4"}),
    ("child combinator >", "#list > li", FX, {"li1", "li2", "li3", "li4"}),
    ("adjacent sibling +", "#p1 + p", FX, {"p2"}),
    ("general sibling ~", "#p1 ~ span", FX, {"s1"}),
    ("universal *", "#list > *", FX, {"li1", "li2", "li3", "li4"}),
    ("attr presence [attr]", "[data-role]", FX, {"p1", "p3"}),
    ("attr equals [a=v]", '[data-role="lead"]', FX, {"p1"}),
    ("attr prefix [a^=v]", '[title^="hello"]', FX, {"p1"}),
    ("attr suffix [a$=v]", '[title$="world"]', FX, {"p1"}),
    ("attr substring [a*=v]", '[title*="lo wo"]', FX, {"p1"}),
    ("attr lang dash [a|=v]", '[lang|="en"]', FX, {"p1"}),
    ("attr whitespace [a~=v]", '[class~="b"]', FX, {"p2"}),
    (":first-child", "#list li:first-child", FX, {"li1"}),
    (":last-child", "#list li:last-child", FX, {"li4"}),
    (":nth-child(2)", "#list li:nth-child(2)", FX, {"li2"}),
    (":nth-child(odd)", "#list li:nth-child(odd)", FX, {"li1", "li3"}),
    (":nth-child(2n)", "#list li:nth-child(2n)", FX, {"li2", "li4"}),
    (":nth-last-child(1)", "#list li:nth-last-child(1)", FX, {"li4"}),
    (":nth-of-type(2)", "#wrap p:nth-of-type(2)", FX, {"p2"}),
    (":nth-last-of-type(1)", "#wrap p:nth-last-of-type(1)", FX, {"p4"}),
    (":only-child", "#p3 a:only-child", FX, {"lnk"}),
    (":first-of-type", "#wrap p:first-of-type", FX, {"p1"}),
    (":last-of-type", "#wrap p:last-of-type", FX, {"p4"}),
    (":not(simple)", "#wrap p:not(.a)", FX, {"p3", "p4"}),
    (":not(compound .a.b)", "#wrap p:not(.a):not(.c)", FX, {"p4"}),
    (":empty", "p:empty", "<div><p id=e1></p><p id=e2>x</p></div>", {"e1"}),
    (":checked", "#in2:checked", FX, {"in2"}),
    (":disabled", "#in1:disabled", FX, {"in1"}),
    (":has(child)", "p:has(a)", FX, {"p3"}),
    (":is() list", ":is(#p1, #p4)", FX, {"p1", "p4"}),
    (":where() list", ":where(#p2)", FX, {"p2"}),
    ("attr case-insensitive [a=v i]", '[data-role="LEAD" i]', FX, {"p1"}),
    # README compound. Fixture is WELL-FORMED (explicitly closed <p> siblings):
    # an earlier version used unclosed <p> tags, which soupsieve's html.parser
    # tree builder nested rather than treating as siblings, making soupsieve
    # return [] (a tree-builder artifact, not a :has() bug). With six real
    # siblings, soupsieve returns the correct {p1,p5} and only cssselect
    # (lxml/parsel) genuinely mis-evaluates the compound (adds p3). See FINDING-09.
    ("complex nth+not (README)",
     "div > :nth-child(2n+1):not(:has(a))",
     "<div><p id=p1></p><p id=p2></p><p id=p3><a>link</a></p>"
     "<p id=p4></p><p id=p5>text</p><p id=p6></p></div>",
     {"p1", "p5"}),
    # ---- fault-finding pass (methodology v3) ----
    (":lang(en) [FAULT-FIND]", ":lang(en)", FX_LANG, {"p1", "q1"}),
    (":dir(rtl) [FAULT-FIND]", ":dir(rtl)", FX_DIR, {"p1"}),
    ("[a=v i] both-case [FAULT-FIND]", '[data-role="LEAD" i]', FX_CASE, {"p1", "p2"}),
]

ENGINES = ["lexbor", "modest", "lxml", "parsel", "soupsieve"]


def run_cell(engine, sel, fx, expected):
    """Run one cell in a subprocess; classify PASS/WRONG/UNSUPPORTED/PROCESS_ABORT."""
    p = subprocess.run([PY, "-c", CHILD, engine, sel, fx],
                       capture_output=True, text=True, timeout=30)
    line = (p.stdout.strip().splitlines() or [""])[-1]
    if p.returncode != 0 and not line:
        return {"status": "PROCESS_ABORT", "returncode": p.returncode,
                "stderr": p.stderr[-120:], "got": None}
    try:
        v = json.loads(line)
    except Exception:
        return {"status": "PARSE_ERR", "raw": p.stdout[-120:], "got": None}
    if v.get("outcome") == "UNSUPPORTED":
        return {"status": "UNSUPPORTED", "err": v.get("err"), "got": None}
    got = set(v.get("got") or [])
    if got == expected:
        return {"status": "PASS", "got": sorted(got)}
    return {"status": "WRONG", "got": sorted(got)}


# ---- extra probes, each crash-isolated in a subprocess ----
PROBE_CHILD = r'''
import sys, json
kind = sys.argv[1]
out = {}
try:
    if kind == "pseudo_lexbor":
        from selectolax.lexbor import LexborHTMLParser
        t = LexborHTMLParser("<div><p id=p1>x</p></div>")
        n = t.css("p::text"); out = {"status": "RAN", "count": len(n)}
    elif kind == "pseudo_modest":
        from selectolax.parser import HTMLParser
        t = HTMLParser("<div><p id=p1>x</p></div>")
        n = t.css("p::text"); out = {"status": "RAN", "count": len(n)}
    elif kind == "pseudo_parsel":
        from parsel import Selector
        s = Selector(text='<div><p id=p1>hi</p><a href="/x">L</a></div>')
        out = {"status": "PASS", "text": s.css("p::text").getall(),
               "attr": s.css("a::attr(href)").getall()}
    elif kind == "lexbor_contains":
        from selectolax.lexbor import LexborHTMLParser
        h = "<div><p id=a>hello </p><p id=b>lexbor is AwesOme</p></div>"
        t = LexborHTMLParser(h)
        out = {"ci": [n.attributes.get("id") for n in t.css('p:lexbor-contains("awesome" i)')],
               "cs": [n.attributes.get("id") for n in t.css('p:lexbor-contains("AwesOme")')],
               "no_flag": [n.attributes.get("id") for n in t.css('p:lexbor-contains("awesome")')]}
    elif kind.startswith("xpath_"):
        eng = kind.split("_",1)[1]
        if eng == "lexbor":
            from selectolax.lexbor import LexborHTMLParser
            out = {"has_xpath_method": hasattr(LexborHTMLParser("<p/>"), "xpath")}
        elif eng == "modest":
            from selectolax.parser import HTMLParser
            out = {"has_xpath_method": hasattr(HTMLParser("<p/>"), "xpath")}
        elif eng == "lxml":
            import lxml.html
            lxml.html.fromstring("<p/>").xpath("//p"); out = {"has_xpath_method": True, "works": True}
        elif eng == "parsel":
            from parsel import Selector
            Selector(text="<p/>").xpath("//p"); out = {"has_xpath_method": True, "works": True}
    print(json.dumps(out))
except Exception as e:
    print(json.dumps({"status": "UNSUPPORTED", "err": (type(e).__name__+": "+str(e))[:120]}))
'''


def run_probe(kind):
    p = subprocess.run([PY, "-c", PROBE_CHILD, kind], capture_output=True, text=True, timeout=30)
    line = (p.stdout.strip().splitlines() or [""])[-1]
    if p.returncode != 0 and not line:
        return {"status": "PROCESS_ABORT", "returncode": p.returncode}
    try:
        return json.loads(line)
    except Exception:
        return {"status": "PARSE_ERR", "raw": p.stdout[-120:]}


def main():
    rows = []
    for label, sel, fx, exp in CASES:
        r = {"selector": label, "css": sel, "expected": sorted(exp),
             "fault_find": "[FAULT-FIND]" in label}
        for eng in ENGINES:
            r[eng] = run_cell(eng, sel, fx, exp)
        rows.append(r)
        print(f"{label:<34} " + " ".join(
            f"{eng[:4]}={r[eng]['status'][:5]}" for eng in ENGINES))

    print("\n--- pseudo-element probes (::text / ::attr) ---")
    pseudo = {"lexbor": run_probe("pseudo_lexbor"), "modest": run_probe("pseudo_modest"),
              "parsel": run_probe("pseudo_parsel")}
    for k, v in pseudo.items():
        print(f"{k} ::text/::attr -> {v}")

    print("\n--- :scope probe (context-dependent, reported not scored) ---")
    scope = {}
    FX_SCOPE = '<div id="w"><p id="p1">a</p><p id="p2">b</p></div>'
    for eng in ENGINES:
        scope[eng] = run_cell(eng, ":scope > p", FX_SCOPE, {"p1", "p2"})
        print(f"{eng} :scope>p -> status={scope[eng]['status']} got={scope[eng].get('got')}")

    print("\n--- :lexbor-contains (selectolax Lexbor extension) ---")
    lc = run_probe("lexbor_contains")
    print("lexbor-contains:", lc)

    print("\n--- XPath support probe ---")
    xpath = {e: run_probe("xpath_" + e) for e in ["lexbor", "modest", "lxml", "parsel"]}
    print("xpath support:", json.dumps(xpath))

    out = {"engines": ENGINES, "cases": rows, "pseudo_elements": pseudo,
           "scope_probe": scope, "lexbor_contains": lc, "xpath": xpath}
    with open(os.path.join(RAW, "css_coverage.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\nwritten", os.path.join(RAW, "css_coverage.json"))

    def counts(subset, eng):
        return (sum(1 for r in subset if r[eng]["status"] == "PASS"),
                sum(1 for r in subset if r[eng]["status"] == "WRONG"),
                sum(1 for r in subset if r[eng]["status"] == "UNSUPPORTED"),
                sum(1 for r in subset if r[eng]["status"] == "PROCESS_ABORT"))

    print("\n--- summary (all cases) ---")
    for eng in ENGINES:
        p, w, u, a = counts(rows, eng)
        print(f"{eng:<10}: PASS={p} WRONG={w} UNSUPPORTED={u} ABORT={a} / {len(rows)}")
    print("--- fault-finding cases only ---")
    ff = [r for r in rows if r["fault_find"]]
    for eng in ENGINES:
        p, w, u, a = counts(ff, eng)
        print(f"{eng:<10}: PASS={p} WRONG={w} UNSUPPORTED={u} ABORT={a} / {len(ff)}")


if __name__ == "__main__":
    main()
