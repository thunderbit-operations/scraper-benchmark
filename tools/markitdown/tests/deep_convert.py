#!/usr/bin/env python3
"""
Deep conversion harness for the MarkItDown review.

Covers, in one pass, and writes every result field computed-from-run (no
hard-coded conclusions):

  A. Web HTML->Markdown on the 4 shared fixtures — headings, GFM table rows,
     links, char count, and BOILERPLATE RESIDUE (quantified as a % of output
     lines that are chrome/nav/footer, using a pre-registered chrome-marker set).
  B. Document-type matrix: real PDF (text layer), scanned PDF (no text layer),
     DOCX, XLSX, PPTX, equations.docx — success, chars, headings, table rows,
     and per-type structural probes (pre-registered must_contain strings).
  C. Complex-table matrix: each of the 13 pre-registered table cases converted
     in isolation and scored against manifest.json expected facts — did every
     `must_contain` token survive, is the pipe-column arity what a correct GFM
     grid needs, did in-cell pipes corrupt the row.

Instrumentation: wall-clock via time.perf_counter around convert() only; all
numeric fields derived from the produced Markdown. Nothing about "fast" or
"faithful" is written by this script — it only emits measurements.
"""
import json
import os
import re
import sys
import time

from markitdown import MarkItDown

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))


def _pick(*candidates):
    """Return the first existing path; else the first candidate (for makedirs)."""
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


# Works in both layouts: the research pack (artifacts/fixtures, artifacts/raw)
# and the clean public repo (fixtures, results).
FIX = _pick(os.path.join(BASE, "artifacts", "fixtures"), os.path.join(BASE, "fixtures"))
DOCS = os.path.join(FIX, "docs")
TAB = os.path.join(FIX, "tables")
RAW = _pick(os.path.join(BASE, "artifacts", "raw"), os.path.join(BASE, "results"))
OUT = os.path.join(RAW, "md_outputs")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

HEADING_RE = re.compile(r"^(#{1,6})\s", re.M)
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]+\)")

# Pre-registered chrome/boilerplate markers (substring, case-insensitive).
# These are site-chrome phrases that a *readability* extractor would strip but a
# whole-document converter keeps. Registered before the run.
CHROME_MARKERS = [
    "jump to content", "toggle the table of contents", "retrieved from",
    "this page was last edited", "privacy policy", "terms of use",
    "per page", "next", "previous", "sign in", "log in", "log out",
    "subscribe", "cookie", "©", "all rights reserved", "skip to",
    "main menu", "navigation", "breadcrumb", "search", "languages",
    "hartley brody", "creative commons",
]


def heading_counts(md):
    h = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for m in HEADING_RE.finditer(md):
        h[len(m.group(1))] += 1
    return {"h1": h[1], "h2": h[2], "h3": h[3], "h4": h[4], "h5": h[5], "h6": h[6],
            "total": sum(h.values())}


def table_rows(md):
    return sum(1 for ln in md.splitlines() if TABLE_ROW_RE.match(ln))


def link_count(md):
    return len(LINK_RE.findall(md))


def chrome_line_fraction(md):
    """Fraction of non-empty output lines that contain a registered chrome marker.
    A rough, reproducible proxy for boilerplate residue."""
    lines = [ln for ln in md.splitlines() if ln.strip()]
    if not lines:
        return {"nonempty_lines": 0, "chrome_lines": 0, "chrome_fraction": 0.0,
                "markers_hit": []}
    low = [ln.lower() for ln in lines]
    hits = []
    chrome_lines = 0
    markers_hit = set()
    for ln in low:
        matched = [mk for mk in CHROME_MARKERS if mk in ln]
        if matched:
            chrome_lines += 1
            markers_hit.update(matched)
    return {"nonempty_lines": len(lines), "chrome_lines": chrome_lines,
            "chrome_fraction": round(chrome_lines / len(lines), 4),
            "markers_hit": sorted(markers_hit)}


def convert_timed(md_engine, path, n_iters=1):
    """Convert once for content, then time n_iters conversions; return (text, timings_ms)."""
    res = md_engine.convert(path)
    text = res.text_content
    timings = []
    for _ in range(n_iters):
        t0 = time.perf_counter()
        md_engine.convert(path)
        timings.append((time.perf_counter() - t0) * 1000.0)
    return text, timings


def probe_present(md, tokens):
    low = md.lower()
    return {tok: (tok.lower() in low) for tok in tokens}


def run_web(md_engine):
    """A. Web HTML->Markdown on shared fixtures."""
    web = [
        ("books_toscrape", "books_toscrape.html",
         ["Home", "Books", "Travel", "Sharp Objects", "£"]),
        ("quotes_toscrape", "quotes_toscrape.html",
         ["Albert Einstein", "quote", "tags", "Login"]),
        ("scrapethissite_forms", "scrapethissite_forms.html",
         ["Boston Bruins", "Team Name", "Win %", "Hartley Brody"]),
        ("wikipedia_web_scraping", "wikipedia_web_scraping.html",
         ["Web scraping", "History", "Techniques", "References", "See also"]),
    ]
    out = []
    for name, fn, probes in web:
        p = os.path.join(FIX, fn)
        text, timings = convert_timed(md_engine, p, n_iters=5)
        with open(os.path.join(OUT, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write(text)
        out.append({
            "fixture": name,
            "input_bytes": os.path.getsize(p),
            "output_chars": len(text),
            "headings": heading_counts(text),
            "md_table_rows": table_rows(text),
            "md_links": link_count(text),
            "body_probes": probe_present(text, probes),
            "boilerplate": chrome_line_fraction(text),
            "timings_ms": [round(t, 3) for t in timings],
            "time_ms_median": round(sorted(timings)[len(timings) // 2], 3),
        })
    return out


def run_docs(md_engine):
    """B. Document-type matrix."""
    docs = [
        ("pdf_arxiv_attention", "arxiv_1706.03762.pdf",
         ["Attention Is All You Need", "Transformer", "Multi-Head Attention",
          "BLEU", "References", "Encoder", "Decoder"]),
        ("pdf_bitcoin", "../fixtures/bitcoin.pdf" if False else None,  # placeholder
         []),
        ("pdf_scanned_financial", "scanned_financial.pdf",
         ["QUARTERLY", "Revenue", "North America", "Total"]),
        ("docx_test", "mid_test.docx",
         ["Microsoft", "AutoGen"]),
        ("docx_equations", "mid_equations.docx",
         ["equation", "="]),
        ("xlsx_test", "mid_test.xlsx", ["Sheet"]),
        ("pptx_test", "mid_test.pptx", ["slide"]),
    ]
    out = []
    # fix bitcoin path
    docs = [d for d in docs if d[1] is not None]
    docs.insert(1, ("pdf_bitcoin", os.path.join(FIX, "bitcoin.pdf"),
                    ["Satoshi Nakamoto", "Abstract", "proof-of-work",
                     "double-spending", "References", "Conclusion"]))
    for name, fn, probes in docs:
        p = fn if os.path.isabs(fn) else os.path.join(DOCS, fn)
        if not os.path.exists(p):
            out.append({"doc": name, "error": f"missing fixture {p}"})
            continue
        try:
            text, timings = convert_timed(md_engine, p, n_iters=3)
            with open(os.path.join(OUT, f"{name}.md"), "w", encoding="utf-8") as f:
                f.write(text)
            out.append({
                "doc": name,
                "input_bytes": os.path.getsize(p),
                "output_chars": len(text),
                "headings": heading_counts(text),
                "md_table_rows": table_rows(text),
                "md_links": link_count(text),
                "structural_probes": probe_present(text, probes),
                "probes_present_ratio":
                    f"{sum(probe_present(text, probes).values())}/{len(probes)}"
                    if probes else "n/a",
                "timings_ms": [round(t, 3) for t in timings],
                "time_ms_median": round(sorted(timings)[len(timings) // 2], 3),
            })
        except Exception as e:
            out.append({"doc": name, "error": f"{type(e).__name__}: {e}"})
    return out


def run_tables(md_engine):
    """C. Complex-table matrix scored against pre-registered manifest."""
    with open(os.path.join(TAB, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    cases = {c["id"]: c for c in manifest["cases"]}
    out = []
    for cid in sorted(cases):
        p = os.path.join(TAB, f"{cid}.html")
        exp = cases[cid]["expected"]
        must = exp.get("must_contain", [])
        try:
            text = md_engine.convert(p).text_content
        except Exception as e:
            out.append({"case": cid, "error": f"{type(e).__name__}: {e}"})
            continue
        with open(os.path.join(OUT, f"table_{cid}.md"), "w", encoding="utf-8") as f:
            f.write(text)
        present = probe_present(text, must)
        n_present = sum(present.values())
        # pipe-table analysis: collect pipe rows, compute their column counts
        pipe_rows = [ln for ln in text.splitlines() if TABLE_ROW_RE.match(ln)]
        col_counts = []
        for r in pipe_rows:
            # count interior columns: split on unescaped pipes
            body = r.strip().strip("|")
            # naive: count pipe separators not preceded by backslash
            cols = len(re.split(r"(?<!\\)\|", body))
            col_counts.append(cols)
        # is it a syntactically usable GFM table? (>=2 rows incl a separator row)
        has_separator = any(re.match(r"^\s*\|[\s:|-]+\|\s*$", ln) for ln in pipe_rows)
        distinct_col_counts = sorted(set(col_counts))
        out.append({
            "case": cid,
            "desc": cases[cid]["desc"],
            "expected": exp,
            "output_chars": len(text),
            "must_contain_present": present,
            "must_contain_ratio": f"{n_present}/{len(must)}" if must else "n/a",
            "all_tokens_survived": (n_present == len(must)) if must else None,
            "pipe_row_count": len(pipe_rows),
            "pipe_col_counts": col_counts,
            "distinct_pipe_col_counts": distinct_col_counts,
            "has_gfm_separator_row": has_separator,
            "column_arity_consistent": len(distinct_col_counts) <= 1,
        })
    return out


def run_recursion(md_engine):
    """D. Deep-nesting recursion-fallback probe.

    Convert N-deep nested <div> wrappers around a heading+paragraph, varying N,
    and record (a) whether MarkItDown's intentional RecursionError->get_text()
    fallback fires (warning text), and (b) whether the '## H' Markdown heading
    survives.  Everything computed from the run.
    """
    import io
    import warnings
    from markitdown import StreamInfo

    def conv(depth):
        inner = "<h2>H</h2><p>para</p>"
        html = "<html><body>" + "<div>" * depth + inner + "</div>" * depth + "</body></html>"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            txt = md_engine.convert_stream(
                io.BytesIO(html.encode()),
                stream_info=StreamInfo(mimetype="text/html", extension=".html",
                                       charset="utf-8")).text_content
            warned = any("recursion" in str(x.message).lower()
                         or "nested" in str(x.message).lower() for x in w)
        return {"depth": depth, "fallback_fired": warned,
                "md_heading_survives": ("## H" in txt or "##H" in txt),
                "out_chars": len(txt.strip())}

    return [conv(d) for d in (50, 100, 200, 300, 400, 450, 500, 2000, 6000)]


def main():
    md_engine = MarkItDown(enable_plugins=False)
    result = {
        "tool": "markitdown",
        "version": __import__("importlib.metadata", fromlist=["version"]).version("markitdown"),
        "python": sys.version.split()[0],
        "web": run_web(md_engine),
        "docs": run_docs(md_engine),
        "tables": run_tables(md_engine),
        "recursion": run_recursion(md_engine),
    }
    outp = os.path.join(RAW, "deep_convert.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"wrote {outp}")
    # brief stdout summary (computed, for the log)
    print("\n-- WEB --")
    for w in result["web"]:
        print(f"  {w['fixture']:26s} chars={w['output_chars']:>7} "
              f"h1/h2/h3={w['headings']['h1']}/{w['headings']['h2']}/{w['headings']['h3']} "
              f"tbl_rows={w['md_table_rows']:>3} links={w['md_links']:>3} "
              f"chrome={w['boilerplate']['chrome_fraction']:.3f} "
              f"({w['boilerplate']['chrome_lines']}/{w['boilerplate']['nonempty_lines']} lines)")
    print("\n-- DOCS --")
    for d in result["docs"]:
        if "error" in d:
            print(f"  {d['doc']:26s} ERROR {d['error']}")
        else:
            print(f"  {d['doc']:26s} chars={d['output_chars']:>7} "
                  f"tbl_rows={d['md_table_rows']:>3} probes={d['probes_present_ratio']} "
                  f"t={d['time_ms_median']}ms")
    print("\n-- TABLES --")
    for t in result["tables"]:
        if "error" in t:
            print(f"  {t['case']:22s} ERROR {t['error']}")
        else:
            print(f"  {t['case']:22s} tokens={t['must_contain_ratio']:>6} "
                  f"survived={t['all_tokens_survived']} "
                  f"pipe_rows={t['pipe_row_count']:>2} "
                  f"col_counts={t['distinct_pipe_col_counts']} "
                  f"sep={t['has_gfm_separator_row']}")
    print("\n-- RECURSION FALLBACK --")
    for r in result["recursion"]:
        print(f"  depth={r['depth']:>5} fallback={r['fallback_fired']!s:5} "
              f"md_heading_survives={r['md_heading_survives']!s:5} chars={r['out_chars']}")


if __name__ == "__main__":
    main()
