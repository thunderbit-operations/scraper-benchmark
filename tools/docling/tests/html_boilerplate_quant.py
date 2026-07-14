#!/usr/bin/env python3
"""Quantify EXACTLY how much site-chrome/boilerplate survives Docling's raw HTML->MD
conversion (Docling does no readability-style main-content extraction). Self-contained:
we count boilerplate-marker lines and pre-main-heading chrome on Docling's own output,
so the 'keeps boilerplate' caveat gets a number, not an adjective.

For each HTML fixture:
  - total_md_lines
  - lines_before_first_content_heading   (chrome that leads the doc)
  - boilerplate_marker_lines             (nav/cookie/footer/legal marker hits)
  - pct_boilerplate_lines
  - main_heading_line                    (where the real article starts)
"""
import json, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FIX = os.path.join(ROOT, "artifacts", "fixtures")

# markers that indicate site chrome rather than article content
BOILER = [
    "move to sidebar", "hide", "toggle the table of contents", "jump to content",
    "navigation", "personal tools", "create account", "log in", "search wikipedia",
    "cs1 maint", "articles with", "wikipedia articles", "categories:", "hidden categories",
    "cookie", "privacy policy", "terms of", "sign in", "sign up", "subscribe",
    "skip to", "back to top", "all rights reserved", "©", "download as pdf",
    "printable version", "what links here", "related changes", "permanent link",
    "page information", "cite this page", "edit source", "view history",
]

# main content heading per fixture (the line marking where the real article starts)
MAIN_HEADING = {
    "wikipedia_web_scraping.html": "# web scraping",
    "books_toscrape.html": None,
    "quotes_toscrape.html": None,
    "scrapethissite_forms.html": None,
}


def analyze(md, main_h):
    lines = [l for l in md.splitlines()]
    total = len([l for l in lines if l.strip()])
    lower = [l.lower() for l in lines]
    boiler_hits = sum(1 for l in lower if any(b in l for b in BOILER))
    # lines before first content heading (any '# ' that isn't itself a chrome marker)
    main_line = None
    if main_h:
        for i, l in enumerate(lower):
            if l.strip().startswith(main_h):
                main_line = i
                break
    lead_chrome = main_line if main_line is not None else None
    return {
        "total_nonblank_md_lines": total,
        "boilerplate_marker_lines": boiler_hits,
        "pct_boilerplate_lines": round(100 * boiler_hits / max(total, 1), 1),
        "main_heading_line": main_line,
        "lines_before_main_heading": lead_chrome,
    }


def main():
    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()
    results = []
    for fname, main_h in MAIN_HEADING.items():
        path = os.path.join(FIX, fname)
        if not os.path.exists(path):
            continue
        res = conv.convert(path)
        md = res.document.export_to_markdown()
        a = analyze(md, main_h)
        a["file"] = fname
        results.append(a)
        print(f"{fname}: {a['total_nonblank_md_lines']} lines, "
              f"{a['boilerplate_marker_lines']} boilerplate ({a['pct_boilerplate_lines']}%), "
              f"main heading at line {a['main_heading_line']}")
    outp = os.path.join(ROOT, "artifacts", "raw", "html_boilerplate_quant.json")
    with open(outp, "w") as f:
        # _method describes HOW the numbers were produced (metadata), not a conclusion
        # about the tool; the interpretation lives in research-materials.md, not here.
        json.dump({"tool": "docling",
                   "_method": "counts boilerplate-marker lines (see BOILER list) and pre-main-heading lines in Docling's raw HTML->Markdown export; no main-content extraction is applied by the test or the tool",
                   "results": results}, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
