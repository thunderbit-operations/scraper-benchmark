#!/usr/bin/env python3
"""FINDING-D3 controlled A/B: is the "dropped table" a TableFormer parsing weakness,
or a layout-model page-context effect?

For each of two tables (T1 bordered grid, T4 rowspan) we compare two arms that hold
the *identical* table matrix constant and vary only the page context:

  arm A (isolated)   : the table alone on an otherwise near-empty page
  arm B (in-context) : the same table surrounded by ordinary body paragraphs

For every arm we record, all COMPUTED from the run (nothing hand-written):
  - text_layer_chars   : pypdfium2 char count of the page-1 text layer (rules out a
                         broken/imageless fixture — the PDF is a real digital PDF)
  - n_doc_tables       : len(DoclingDocument.tables)
  - n_doc_pictures     : len(DoclingDocument.pictures)
  - md_has_table       : did the exported Markdown contain a GFM table
  - do_ocr_false_*     : the isolated arm re-run with do_ocr=False, to prove the drop
                         is not an OCR mis-route (still dropped => layout, not OCR)
  - rowspan_repeats    : (T4 only) how many times the merged 'North' label appears in
                         the B-arm Markdown (expected 3 — one per spanned row)

The decisive signal: if A drops (n_doc_tables==0, classified as a Picture) while B
converts (n_doc_tables==1) for the SAME table, the failure is page-sparsity layout
context, not table parsing. Warm run (models already cached); seconds, not the 224 s
cold first conversion.

Run with the docling venv, HF_HOME pointed at the cached model dir:
  HF_HOME=.../artifacts/hf_cache_probe .venv/bin/python tests/pdf_sparse_page_ab.py
"""
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FIX = os.path.join(ROOT, "artifacts", "fixtures", "pdf")

# (label, isolated fixture, in-context fixture, merged-label-to-count or None)
PAIRS = [
    ("T1_bordered_grid", "table_t1_simple_grid", "table_t1b_grid_in_context", None),
    ("T4_rowspan", "table_t4_rowspan", "table_t4b_rowspan_in_context", "North"),
]


def text_layer_chars(path):
    """Page-1 text-layer character count via pypdfium2 (0 => scanned/imageless)."""
    import pypdfium2 as pdfium
    pd = pdfium.PdfDocument(path)
    tp = pd[0].get_textpage()
    n = len(tp.get_text_range())
    pd.close()
    return n


def md_has_gfm_table(md):
    lines = md.splitlines()
    for i in range(len(lines) - 1):
        nxt = lines[i + 1] or ""
        if "|" in lines[i] and set(nxt.strip()) <= set("|:- ") and "-" in nxt and "|" in nxt:
            return True
    return False


def convert_counts(conv, path):
    t0 = time.perf_counter()
    res = conv.convert(path)
    dt = round(time.perf_counter() - t0, 3)
    doc = res.document
    md = doc.export_to_markdown()
    return {
        "convert_s": dt,
        "n_doc_tables": len(doc.tables),
        "n_doc_pictures": len(doc.pictures),
        "md_has_table": md_has_gfm_table(md),
        "md_chars": len(md),
        "_md": md,
    }


def main():
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    conv = DocumentConverter()

    # a second converter with OCR disabled, to prove the isolated-table drop is not an
    # OCR mis-route (a Picture region could in principle be OCR'd instead of parsed).
    no_ocr_opts = PdfPipelineOptions()
    no_ocr_opts.do_ocr = False
    conv_no_ocr = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=no_ocr_opts)}
    )

    results = []
    for label, iso_name, ctx_name, merged_label in PAIRS:
        iso_pdf = os.path.join(FIX, f"{iso_name}.pdf")
        ctx_pdf = os.path.join(FIX, f"{ctx_name}.pdf")

        iso = convert_counts(conv, iso_pdf)
        ctx = convert_counts(conv, ctx_pdf)
        iso_no_ocr = convert_counts(conv_no_ocr, iso_pdf)

        entry = {
            "pair": label,
            "isolated_fixture": f"{iso_name}.pdf",
            "in_context_fixture": f"{ctx_name}.pdf",
            "isolated": {
                "text_layer_chars": text_layer_chars(iso_pdf),
                "n_doc_tables": iso["n_doc_tables"],
                "n_doc_pictures": iso["n_doc_pictures"],
                "md_has_table": iso["md_has_table"],
                "convert_s": iso["convert_s"],
            },
            "in_context": {
                "text_layer_chars": text_layer_chars(ctx_pdf),
                "n_doc_tables": ctx["n_doc_tables"],
                "n_doc_pictures": ctx["n_doc_pictures"],
                "md_has_table": ctx["md_has_table"],
                "convert_s": ctx["convert_s"],
            },
            "isolated_do_ocr_false": {
                "n_doc_tables": iso_no_ocr["n_doc_tables"],
                "n_doc_pictures": iso_no_ocr["n_doc_pictures"],
                "md_has_table": iso_no_ocr["md_has_table"],
            },
            # the finding, expressed as a boolean computed from the run:
            "drops_when_isolated_converts_in_context": (
                iso["n_doc_tables"] == 0 and iso["md_has_table"] is False
                and ctx["n_doc_tables"] >= 1 and ctx["md_has_table"] is True
            ),
            "isolated_classified_as_picture": (
                iso["n_doc_tables"] == 0 and iso["n_doc_pictures"] >= 1
            ),
            "drop_survives_do_ocr_false": (iso_no_ocr["n_doc_tables"] == 0),
        }
        if merged_label:
            entry["in_context_rowspan_label"] = merged_label
            entry["in_context_rowspan_repeats"] = ctx["_md"].count(merged_label)
        results.append(entry)
        print(f"{label}: isolated tables={entry['isolated']['n_doc_tables']} "
              f"pics={entry['isolated']['n_doc_pictures']} "
              f"chars={entry['isolated']['text_layer_chars']} | "
              f"in-context tables={entry['in_context']['n_doc_tables']} "
              f"md_table={entry['in_context']['md_has_table']} | "
              f"do_ocr=False tables={entry['isolated_do_ocr_false']['n_doc_tables']}")

    out = {
        "tool": "docling",
        "test": "sparse_page_ab",
        "description": "Same table isolated vs surrounded by text; layout-context effect isolation for FINDING-D3.",
        "results": results,
    }
    outp = os.path.join(ROOT, "artifacts", "raw", "pdf_sparse_page_ab.json")
    with open(outp, "w") as f:
        json.dump(out, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
