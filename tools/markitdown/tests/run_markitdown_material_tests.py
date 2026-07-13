#!/usr/bin/env python3
"""
MarkItDown material test runner for the Thunderbit open-source scraper review pack.

Converts 4 unified local HTML fixtures (downloaded via curl) to Markdown using
microsoft/markitdown, and records quantitative metrics for each page:
  - heading levels preserved (count of #, ##, ### markers)
  - body completeness (probe strings that must survive)
  - HTML table -> Markdown table conversion (count of GFM pipe-table rows)
  - link preservation (count of []() markdown links)
  - nav/footer boilerplate handling (presence of known chrome strings)
  - output char count
  - conversion wall-clock time
  - success / failure

Honest by design: only real measured numbers are written. No fabrication.
Raw markdown outputs are saved to artifacts/raw/. A JSON summary is written to
artifacts/raw/markitdown-test-summary.json.
"""
import json
import os
import re
import sys
import time
import traceback

from markitdown import MarkItDown

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIX = os.path.join(BASE, "artifacts", "fixtures")
RAW = os.path.join(BASE, "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)

# GFM table row = a line that starts and ends with a pipe (after strip).
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
# Markdown inline link [text](url)
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]+\)")


def heading_counts(md: str):
    counts = {"h1": 0, "h2": 0, "h3": 0, "h4": 0, "h5": 0, "h6": 0}
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+\S", line)
        if m:
            counts[f"h{len(m.group(1))}"] += 1
    return counts


def count_table_rows(md: str) -> int:
    return sum(1 for line in md.splitlines() if TABLE_ROW_RE.match(line))


def count_links(md: str) -> int:
    return len(LINK_RE.findall(md))


def probe(md: str, needles):
    """Return dict needle->bool for body-completeness / boilerplate checks."""
    return {n: (n.lower() in md.lower()) for n in needles}


# Per-fixture test spec. Probes chosen from the real page content / chrome.
TESTS = [
    {
        "id": "books_toscrape",
        "file": "books_toscrape.html",
        "url": "https://books.toscrape.com/",
        "body_probes": [
            "A Light in the Attic",     # first product title
            "Tipping the Velvet",       # another product
            "£51.77",                   # a price string
        ],
        "boiler_probes": [
            "Books to Scrape",          # site brand (nav/header)
            "Home",                     # breadcrumb / nav
        ],
        "expect_table": False,
    },
    {
        "id": "quotes_toscrape",
        "file": "quotes_toscrape.html",
        "url": "https://quotes.toscrape.com/",
        "body_probes": [
            "The world as we have created it",  # first quote
            "Albert Einstein",                  # first author
            "J.K. Rowling",                     # another author
            "change",                           # a tag
        ],
        "boiler_probes": [
            "Quotes to Scrape",         # brand
            "Login",                    # nav link
        ],
        "expect_table": False,
    },
    {
        "id": "scrapethissite_forms",
        "file": "scrapethissite_forms.html",
        "url": "https://www.scrapethissite.com/pages/forms/",
        "body_probes": [
            "Boston Bruins",            # first team row
            "Buffalo Sabres",           # another team
            "Team Name",                # table header cell
            "Win %",                    # table header cell
        ],
        "boiler_probes": [
            "Scrape This Site",         # brand
            "Sponsors",                 # footer/nav
        ],
        "expect_table": True,
    },
    {
        "id": "wikipedia_web_scraping",
        "file": "wikipedia_web_scraping.html",
        "url": "https://en.wikipedia.org/wiki/Web_scraping",
        "body_probes": [
            "Web scraping",             # title / lede
            "HTTP",                     # body term
            "screen scraping",          # body term
            "History",                  # a section heading
            "Legal issues",             # a section heading
        ],
        "boiler_probes": [
            "Jump to content",          # wiki chrome
            "Retrieved from",           # wiki footer
            "This page was last edited",# wiki footer
        ],
        "expect_table": False,  # only layout/infobox tables, not a data grid
    },
]


def run():
    md = MarkItDown()
    results = []
    for spec in TESTS:
        path = os.path.join(FIX, spec["file"])
        rec = {
            "id": spec["id"],
            "url": spec["url"],
            "fixture": spec["file"],
            "fixture_bytes": os.path.getsize(path) if os.path.exists(path) else None,
        }
        try:
            t = time.perf_counter()
            out = md.convert(path)
            dt = time.perf_counter() - t
            text = out.markdown
            rec["success"] = True
            rec["convert_time_s"] = round(dt, 4)
            rec["output_chars"] = len(text)
            rec["heading_counts"] = heading_counts(text)
            rec["md_table_rows"] = count_table_rows(text)
            rec["md_links"] = count_links(text)
            rec["body_probes"] = probe(text, spec["body_probes"])
            rec["body_probes_hit"] = sum(rec["body_probes"].values())
            rec["body_probes_total"] = len(spec["body_probes"])
            rec["boiler_probes"] = probe(text, spec["boiler_probes"])
            rec["expect_table"] = spec["expect_table"]
            # save raw
            outpath = os.path.join(RAW, f"{spec['id']}.md")
            with open(outpath, "w", encoding="utf-8") as f:
                f.write(text)
            rec["raw_output"] = os.path.relpath(outpath, BASE)
        except Exception as e:  # noqa: BLE001
            rec["success"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()
        results.append(rec)

    summary = {
        "tool": "markitdown",
        "as_of": "2026-07-10",
        "markitdown_version": "0.1.6",
        "python": sys.version.split()[0],
        "results": results,
    }
    with open(os.path.join(RAW, "markitdown-test-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # human-readable console table
    print("\n=== MarkItDown material test results (as-of 2026-07-10, v0.1.6) ===\n")
    for r in results:
        if not r["success"]:
            print(f"[FAIL] {r['id']}: {r.get('error')}")
            continue
        hc = r["heading_counts"]
        hs = " ".join(f"{k}={v}" for k, v in hc.items() if v)
        print(f"[OK]   {r['id']}")
        print(f"       chars={r['output_chars']}  time={r['convert_time_s']}s")
        print(f"       headings: {hs or '(none)'}")
        print(f"       md_table_rows={r['md_table_rows']}  md_links={r['md_links']}")
        print(f"       body_probes={r['body_probes_hit']}/{r['body_probes_total']}  {r['body_probes']}")
        print(f"       boiler_probes={r['boiler_probes']}")
        print()


if __name__ == "__main__":
    run()
