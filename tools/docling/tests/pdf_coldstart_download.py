#!/usr/bin/env python3
"""Measure the FIRST-RUN model-download cost of Docling's PDF path — the friction the
HTML-only smoke pack could not observe. Snapshots the HF cache size before/after the
first PDF conversion and times model init vs inference separately.

Run against a clean HF cache dir (we point HF_HOME at a fresh dir so the download is
isolated and measurable; the system cache is left untouched)."""
import json, os, sys, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def dir_size_bytes(path):
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def main():
    hf_home = os.environ.get("HF_HOME", "")
    small_pdf = os.path.join(ROOT, "artifacts", "fixtures", "pdf", "table_t1_simple_grid.pdf")
    result = {"hf_home": hf_home, "pdf": small_pdf}

    before = dir_size_bytes(hf_home) if hf_home and os.path.isdir(hf_home) else 0
    result["hf_cache_before_bytes"] = before

    t_import0 = time.perf_counter()
    from docling.document_converter import DocumentConverter
    t_import = time.perf_counter() - t_import0
    result["import_s"] = round(t_import, 3)

    # Converter init (may lazily create pipeline)
    t0 = time.perf_counter()
    conv = DocumentConverter()
    result["converter_init_s"] = round(time.perf_counter() - t0, 3)

    # FIRST PDF conversion — this triggers layout + TableFormer model download+load
    t1 = time.perf_counter()
    res = conv.convert(small_pdf)
    result["first_pdf_convert_s"] = round(time.perf_counter() - t1, 3)
    md = res.document.export_to_markdown()
    result["first_pdf_md_chars"] = len(md)
    result["first_pdf_has_table"] = "|" in md and "---" in md

    after = dir_size_bytes(hf_home) if hf_home and os.path.isdir(hf_home) else 0
    result["hf_cache_after_bytes"] = after
    result["model_download_bytes"] = after - before
    result["model_download_mb"] = round((after - before) / 1e6, 1)

    # SECOND conversion — models now cached, isolate warm inference cost
    t2 = time.perf_counter()
    conv.convert(small_pdf)
    result["second_pdf_convert_s"] = round(time.perf_counter() - t2, 3)

    print(json.dumps(result, indent=2))
    outp = os.path.join(ROOT, "artifacts", "raw", "pdf_coldstart_download.json")
    with open(outp, "w") as f:
        json.dump(result, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
