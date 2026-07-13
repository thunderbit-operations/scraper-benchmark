#!/usr/bin/env python
"""Real hands-on material tests for Docling (docling-project/docling).

Feeds four locally-saved HTML fixtures into Docling's DocumentConverter and
exports each to Markdown. Quantifies: heading hierarchy retention, body
completeness, HTML-table -> Markdown-table fidelity, link retention,
nav/footer boilerplate handling, output char count, wall time, success/fail.

No numbers are fabricated. Everything printed comes from the actual run.
Raw Markdown outputs are written to artifacts/raw/.
"""

import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # tools/docling
FIXTURES = ROOT / "artifacts" / "fixtures"
RAW = ROOT / "artifacts" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# fixture_key -> (local file, canonical source URL, human label)
FIXTURES_MAP = {
    "books": (
        FIXTURES / "books_toscrape.html",
        "https://books.toscrape.com/",
        "Books to Scrape (static catalog)",
    ),
    "quotes": (
        FIXTURES / "quotes_toscrape.html",
        "https://quotes.toscrape.com/",
        "Quotes to Scrape (static quotes)",
    ),
    "forms": (
        FIXTURES / "scrapethissite_forms.html",
        "https://www.scrapethissite.com/pages/forms/",
        "Scrape This Site Forms (HTML table)",
    ),
    "wikipedia": (
        FIXTURES / "wikipedia_web_scraping.html",
        "https://en.wikipedia.org/wiki/Web_scraping",
        "Wikipedia: Web scraping (article + tables)",
    ),
}


def count_md_tables(md: str) -> int:
    """Count GitHub-flavored Markdown tables via header-separator rows like |---|---|."""
    sep = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", re.M)
    return len(sep.findall(md))


def count_md_links(md: str) -> int:
    return len(re.findall(r"\[[^\]]*\]\([^)]+\)", md))


def heading_levels(md: str):
    levels = {}
    for m in re.finditer(r"^(#{1,6})\s+\S", md, re.M):
        levels[len(m.group(1))] = levels.get(len(m.group(1)), 0) + 1
    return levels


def run_one(converter, key):
    path, url, label = FIXTURES_MAP[key]
    entry = {
        "key": key,
        "label": label,
        "source_url": url,
        "fixture_file": str(path),
        "fixture_bytes": path.stat().st_size if path.exists() else None,
    }
    t0 = time.perf_counter()
    try:
        result = converter.convert(str(path))
        md = result.document.export_to_markdown()
        dt = time.perf_counter() - t0
        entry["success"] = True
        entry["runtime_s"] = round(dt, 3)
        entry["md_chars"] = len(md)
        entry["md_lines"] = md.count("\n") + 1
        entry["heading_levels"] = heading_levels(md)
        entry["md_tables"] = count_md_tables(md)
        entry["md_links"] = count_md_links(md)

        out = RAW / f"docling_{key}.md"
        out.write_text(md, encoding="utf-8")
        entry["raw_output"] = str(out)

        # Per-fixture ground-truth probes (real content checks)
        low = md.lower()
        if key == "books":
            # book titles present on the homepage
            for probe in ["a light in the", "tipping the velvet", "soumission"]:
                entry.setdefault("probes", {})[probe] = probe in low
        elif key == "quotes":
            for probe in ["albert einstein", "j.k. rowling",
                          "world as we have created it"]:
                entry.setdefault("probes", {})[probe] = probe in low
        elif key == "forms":
            # hockey table cells / headers (exact content from fixture)
            for probe in ["team name", "boston bruins", "win %",
                          "goals for", "44", "1990"]:
                entry.setdefault("probes", {})[probe] = probe in low
        elif key == "wikipedia":
            for probe in ["web scraping", "html", "http", "legal issues"]:
                entry.setdefault("probes", {})[probe] = probe in low
    except Exception as e:  # noqa: BLE001
        dt = time.perf_counter() - t0
        entry["success"] = False
        entry["runtime_s"] = round(dt, 3)
        entry["error"] = f"{type(e).__name__}: {e}"
    return entry


def main():
    from docling.document_converter import DocumentConverter
    import docling

    print(f"docling version: {getattr(docling, '__version__', 'unknown')}")
    t_init0 = time.perf_counter()
    converter = DocumentConverter()
    init_dt = time.perf_counter() - t_init0
    print(f"DocumentConverter() init: {init_dt:.3f}s")

    summary = {
        "docling_version": getattr(docling, "__version__", "unknown"),
        "python": sys.version.split()[0],
        "converter_init_s": round(init_dt, 3),
        "results": [],
    }
    for key in ["books", "quotes", "forms", "wikipedia"]:
        print(f"\n=== {key} ===")
        entry = run_one(converter, key)
        summary["results"].append(entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2))

    out = RAW / "docling-test-summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary written: {out}")


if __name__ == "__main__":
    main()
