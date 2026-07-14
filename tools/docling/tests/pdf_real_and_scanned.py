#!/usr/bin/env python3
"""Convert REAL PDFs (born-digital academic + scanned/OCR) and measure structure recovery,
per-page runtime, OCR text recall, and table detection. Ground-truth probes are strings
that MUST appear if the page was understood correctly.

Fixtures:
  arxiv_docling_report.pdf   9pp  2-column academic (tables, formulas, reading order)
  arxiv_attention.pdf       15pp  academic; famous multi-col results tables
  ocr_test.pdf               1pp  scanned -> triggers OCR
  nemotron_multipage.pdf     4pp  scanned multi-page

For each: convert, export markdown, then compute:
  n_pages, convert_s, s_per_page, md_chars, n_md_tables, heading_counts,
  probe hits (str-in-md), reading_order_signal (do section markers appear in order).
"""
import json, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PDF = os.path.join(ROOT, "artifacts", "fixtures", "pdf")
SCAN = os.path.join(ROOT, "artifacts", "fixtures", "scanned")

# (file, dir, n_pages_expected, [probes...], [ordered_section_markers...])
CASES = [
    ("arxiv_docling_report.pdf", PDF, 9,
     ["Docling", "TableFormer", "layout", "reading order", "PDF"],
     ["Abstract", "Introduction", "Related Work", "References"]),
    ("arxiv_attention.pdf", PDF, 15,
     ["Attention", "Transformer", "encoder", "BLEU", "multi-head"],
     ["Abstract", "Introduction", "Background", "Conclusion", "References"]),
    ("ocr_test.pdf", SCAN, 1,
     [],  # scanned; probes discovered below by dumping text
     []),
    ("nemotron_multipage.pdf", SCAN, 4,
     [],
     []),
]


def count_md_tables(md):
    n = 0
    lines = md.splitlines()
    for i in range(len(lines) - 1):
        if "|" in lines[i] and re.fullmatch(r"[\s|:\-]+", lines[i + 1] or "") and "-" in (lines[i + 1] or ""):
            n += 1
    return n


def heading_counts(md):
    hc = {}
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+\S", line)
        if m:
            lvl = len(m.group(1))
            hc[lvl] = hc.get(lvl, 0) + 1
    return hc


def text_layer_chars(path, pdfium):
    """Total embedded text-layer character count across all pages (0 => no text layer,
    i.e. genuinely scanned; any recovered text must then be OCR output, not a hidden
    layer). This is the probe that substantiates the 'verified zero text layer' claim."""
    pd = pdfium.PdfDocument(path)
    total = 0
    for i in range(len(pd)):
        total += len(pd[i].get_textpage().get_text_range())
    pd.close()
    return total


def ordered_markers(md, markers):
    """Return which markers appear and whether they appear in the given order."""
    lower = md.lower()
    positions = {}
    for mk in markers:
        idx = lower.find(mk.lower())
        if idx >= 0:
            positions[mk] = idx
    present = [mk for mk in markers if mk in positions]
    in_order = all(positions[present[i]] < positions[present[i + 1]] for i in range(len(present) - 1)) if len(present) > 1 else True
    return {"present": present, "in_order": in_order, "n_present": len(present), "n_total": len(markers)}


def main():
    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()
    import pypdfium2 as pdfium

    results = []
    for fname, d, exp_pages, probes, markers in CASES:
        path = os.path.join(d, fname)
        if not os.path.exists(path):
            results.append({"file": fname, "error": "missing fixture"})
            continue
        pd = pdfium.PdfDocument(path); n_pages = len(pd); pd.close()
        tl_chars = text_layer_chars(path, pdfium)
        t0 = time.perf_counter()
        res = conv.convert(path)
        dt = round(time.perf_counter() - t0, 2)
        md = res.document.export_to_markdown()
        entry = {
            "file": fname, "n_pages": n_pages, "expected_pages": exp_pages,
            "text_layer_chars": tl_chars, "has_text_layer": tl_chars > 0,
            "convert_s": dt, "s_per_page": round(dt / max(n_pages, 1), 2),
            "md_chars": len(md), "n_md_tables": count_md_tables(md),
            "heading_counts": heading_counts(md),
            "probe_hits": {p: (p.lower() in md.lower()) for p in probes},
            "reading_order": ordered_markers(md, markers) if markers else None,
        }
        # for scanned docs, capture a text sample to prove OCR fired (non-empty body).
        # text_layer_chars==0 above proves the recovered text is OCR, not a hidden layer.
        if not probes:
            body = re.sub(r"\s+", " ", md).strip()
            entry["ocr_body_chars"] = len(body)
            entry["ocr_sample"] = body[:400]
            entry["ocr_produced_text"] = len(body) > 50
        results.append(entry)
        print(f"{fname}: {n_pages}pp {dt}s ({entry['s_per_page']}s/pg) "
              f"tables={entry['n_md_tables']} chars={len(md)} "
              f"probes={sum(entry['probe_hits'].values())}/{len(probes)}")
        # save the markdown for manual spot-check
        with open(os.path.join(ROOT, "artifacts", "raw", f"real_{fname.replace('.pdf','')}.md"), "w") as f:
            f.write(md)

    outp = os.path.join(ROOT, "artifacts", "raw", "pdf_real_and_scanned.json")
    with open(outp, "w") as f:
        json.dump({"tool": "docling", "results": results}, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
