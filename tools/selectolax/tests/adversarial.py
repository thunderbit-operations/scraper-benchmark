#!/usr/bin/env python3
"""Adversarial / boundary input robustness tests.

For each pathological input we run selectolax Lexbor, selectolax Modest, and lxml
(as a reference). We classify the outcome:
  CRASH        - raised an exception
  HANG/TIMEOUT - exceeded time budget (run in subprocess with alarm)
  OK           - parsed and a follow-up query behaved sanely
For OK cases we also record a small correctness probe so "didn't crash" doesn't
hide "produced garbage".

Each case runs in a SUBPROCESS with a hard timeout so a hang on one input cannot
stall the whole suite.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(HERE, "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)
PY = sys.executable

# Child runs ONE (engine, case) and prints a JSON verdict.
CHILD = r'''
import sys, json, signal

engine = sys.argv[1]
case = sys.argv[2]

def handler(signum, frame):
    print(json.dumps({"status":"HANG_TIMEOUT"}))
    sys.exit(0)
signal.signal(signal.SIGALRM, handler)
signal.alarm(25)  # hard wall

def build(case):
    if case == "unclosed_tags":
        return "<html><body><div><p>hello<p>world<span>x</div></body>", ("count_p", None)
    if case == "misnested":
        return "<b><i>bold italic</b> only italic</i>", ("count_i", None)
    if case == "no_html_body":
        return "<p id=x>just a paragraph</p>", ("first_p_text", "just a paragraph")
    if case == "deep_nesting_1000":
        return "<div>"*1000 + "deep" + "</div>"*1000, ("find_deep", "deep")
    if case == "deep_nesting_5000":
        return "<div>"*5000 + "deep" + "</div>"*5000, ("find_deep", "deep")
    if case == "empty":
        return "", ("root_not_none", None)
    if case == "whitespace_only":
        return "   \n\t  ", ("root_not_none", None)
    if case == "binary_non_html":
        return bytes(range(256))*40, ("no_crash", None)  # raw bytes
    if case == "bom_utf8":
        return "﻿<p id=b>bom text</p>", ("first_p_text", "bom text")
    if case == "latin1_bytes":
        return "<p>café \xe9\xe8</p>".encode("latin-1"), ("no_crash", None)
    if case == "huge_attr_1mb":
        big = "a"*1_000_000
        return f'<div data-x="{big}"><p id=p>ok</p></div>', ("first_p_text", "ok")
    if case == "many_elements_100k":
        return "<ul>" + "<li>x</li>"*100_000 + "</ul>", ("count_li_100k", 100_000)
    if case == "unicode_emoji":
        return "<p id=e>hello 🌍👨‍👩‍👧‍👦 مرحبا 日本語</p>", ("first_p_text_contains", "🌍")
    if case == "null_bytes":
        return "<p id=n>a\x00b\x00c</p>", ("no_crash", None)
    if case == "cdata_comments":
        return "<div><!-- comment --><![CDATA[data]]><p id=c>after</p></div>", ("first_p_text", "after")
    if case == "script_style_raw":
        return "<script>if (a<b && c>d) {}</script><p id=s>body</p>", ("first_p_text", "body")
    if case == "broken_entities":
        return "<p id=amp>a &amp b &notreal; &#999999999; c</p>", ("no_crash", None)
    if case == "attr_no_quotes_spaces":
        return "<p id = p1 class = foo bar>text</p>", ("no_crash", None)
    raise SystemExit("unknown case "+case)

data, probe = build(case)
pk, expected = probe

def parse_and_probe():
    if engine == "lexbor":
        from selectolax.lexbor import LexborHTMLParser
        t = LexborHTMLParser(data)
    elif engine == "modest":
        from selectolax.parser import HTMLParser
        t = HTMLParser(data)
    elif engine == "lxml":
        import lxml.html
        if isinstance(data, bytes):
            t = lxml.html.fromstring(data)
        else:
            t = lxml.html.fromstring(data)
        return probe_lxml(t)
    return probe_selectolax(t)

def probe_selectolax(t):
    out = {"parsed": True}
    if pk == "count_p":
        out["n_p"] = len(t.css("p"))
    elif pk == "count_i":
        out["n_i"] = len(t.css("i"))
    elif pk == "first_p_text":
        n = t.css_first("p")
        out["value"] = n.text() if n else None
        out["match"] = (out["value"] == expected)
    elif pk == "find_deep":
        # deepest text should still be reachable
        out["has_deep"] = ("deep" in (t.body.text() if t.body else t.text() or ""))
    elif pk == "root_not_none":
        out["root_not_none"] = t.root is not None
        out["html_len"] = len(t.html or "")
    elif pk == "no_crash":
        out["html_len"] = len(t.html or "")
    elif pk == "count_li_100k":
        out["n_li"] = len(t.css("li"))
        out["match"] = (out["n_li"] == expected)
    elif pk == "first_p_text_contains":
        n = t.css_first("p")
        out["value"] = n.text() if n else None
        out["contains"] = (expected in (out["value"] or ""))
    return out

def probe_lxml(t):
    out = {"parsed": True}
    if pk == "count_p":
        out["n_p"] = len(t.cssselect("p"))
    elif pk == "count_i":
        out["n_i"] = len(t.cssselect("i"))
    elif pk == "first_p_text":
        ns = t.cssselect("p")
        out["value"] = ns[0].text_content() if ns else None
        out["match"] = (out["value"] == expected)
    elif pk == "find_deep":
        out["has_deep"] = ("deep" in t.text_content())
    elif pk == "root_not_none":
        out["root_not_none"] = t is not None
    elif pk == "no_crash":
        out["ok"] = True
    elif pk == "count_li_100k":
        out["n_li"] = len(t.cssselect("li"))
        out["match"] = (out["n_li"] == expected)
    elif pk == "first_p_text_contains":
        ns = t.cssselect("p")
        v = ns[0].text_content() if ns else None
        out["value"] = v
        out["contains"] = (expected in (v or ""))
    return out

try:
    res = parse_and_probe()
    res["status"] = "OK"
    print(json.dumps(res, default=str))
except Exception as e:
    print(json.dumps({"status":"CRASH", "error": repr(e)[:300]}))
'''

CASES = [
    "unclosed_tags", "misnested", "no_html_body", "deep_nesting_1000",
    "deep_nesting_5000", "empty", "whitespace_only", "binary_non_html",
    "bom_utf8", "latin1_bytes", "huge_attr_1mb", "many_elements_100k",
    "unicode_emoji", "null_bytes", "cdata_comments", "script_style_raw",
    "broken_entities", "attr_no_quotes_spaces",
]
ENGINES = ["lexbor", "modest", "lxml"]


def run(engine, case):
    p = subprocess.run([PY, "-c", CHILD, engine, case], capture_output=True, text=True, timeout=40)
    line = (p.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        v = json.loads(line)
    except Exception:
        v = {"status": "PARSE_ERR", "raw_stdout": p.stdout[-300:], "stderr": p.stderr[-300:]}
    if p.returncode != 0 and v.get("status") not in ("CRASH", "HANG_TIMEOUT"):
        v.setdefault("status", "SUBPROC_FAIL")
        v["stderr"] = p.stderr[-300:]
    return v


def main():
    results = {}
    for case in CASES:
        results[case] = {}
        line = f"{case:<24}"
        for eng in ENGINES:
            v = run(eng, case)
            results[case][eng] = v
            line += f" {eng}={v.get('status'):<12}"
        print(line)
    with open(os.path.join(RAW, "adversarial.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\nwritten", os.path.join(RAW, "adversarial.json"))

    # summary
    print("\n--- crash/hang summary ---")
    for eng in ENGINES:
        crashes = [c for c in CASES if results[c][eng].get("status") == "CRASH"]
        hangs = [c for c in CASES if results[c][eng].get("status") == "HANG_TIMEOUT"]
        print(f"{eng:<8} CRASH={crashes}  HANG={hangs}")


if __name__ == "__main__":
    main()
