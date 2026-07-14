#!/usr/bin/env python3
"""Measure the FIRST-RUN model-download cost of Docling's PDF path — the friction the
HTML-only smoke pack could not observe. Snapshots the HF cache size before/after the
first PDF conversion and times model init vs inference separately.

Run against a clean HF cache dir (we point HF_HOME at a fresh dir so the download is
isolated and measurable; the system cache is left untouched).

Two size instruments, reported SEPARATELY (they differ ~2x and the reconciliation is
the point — see FINDING-D1):
  - walk_total_bytes  : os.walk + os.path.getsize over ALL of HF_HOME. os.path.getsize
                        FOLLOWS symlinks (it stats the target), and the HF cache stores
                        each model file once in blobs/ and re-exposes it as a
                        snapshots/ symlink. So this instrument counts every model file
                        TWICE and roughly DOUBLES the real footprint (this is why the
                        earlier headline read ~1060 MB). The hf-xet transfer cache is
                        NOT the cause (it is ~0.2 MB after transfer).
  - durable_hub_bytes : os.walk over HF_HOME/hub/** but SKIPPING symlinks (real blobs
                        only). This matches `du -sh HF_HOME/hub` and is the honest
                        "on-disk model" figure (~506 MiB / 530 MB decimal).
  - xet_cache_bytes   : HF_HOME/xet/** on its own (the transient transfer cache).
RapidOCR weights land in site-packages (outside HF_HOME) and are measured by
rapidocr_models_bytes.
"""
import json, os, sys, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def dir_size_bytes(path, skip_symlinks=False):
    """Sum file sizes under path. os.path.getsize follows symlinks, so on an HF cache
    (snapshots/ symlink back into blobs/) the default double-counts; pass
    skip_symlinks=True for the de-duplicated, `du`-matching figure."""
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            fp = os.path.join(dp, fn)
            if skip_symlinks and os.path.islink(fp):
                continue
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def rapidocr_models_bytes():
    """On-disk size of RapidOCR's bundled/downloaded weights inside site-packages
    (they bypass HF_HOME entirely). Returns 0 if not found."""
    for p in sys.path:
        cand = os.path.join(p, "rapidocr", "models")
        if os.path.isdir(cand):
            return dir_size_bytes(cand)
    return 0


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

    # --- size accounting, two instruments reported separately (see docstring) ---
    hub = os.path.join(hf_home, "hub") if hf_home else ""
    xet = os.path.join(hf_home, "xet") if hf_home else ""
    after_walk = dir_size_bytes(hf_home) if hf_home and os.path.isdir(hf_home) else 0
    durable_hub = dir_size_bytes(hub, skip_symlinks=True) if hub and os.path.isdir(hub) else 0
    xet_cache = dir_size_bytes(xet) if xet and os.path.isdir(xet) else 0
    rapid = rapidocr_models_bytes()

    # legacy field kept for backward-compat with earlier summaries (== walk_total):
    result["hf_cache_after_bytes"] = after_walk
    result["model_download_bytes"] = after_walk - before
    result["model_download_mb"] = round((after_walk - before) / 1e6, 1)

    result["walk_total_bytes"] = after_walk
    result["walk_total_mb"] = round(after_walk / 1e6, 1)
    result["durable_hub_bytes"] = durable_hub
    result["durable_hub_mb"] = round(durable_hub / 1e6, 1)
    result["xet_cache_bytes"] = xet_cache
    result["xet_cache_mb"] = round(xet_cache / 1e6, 1)
    result["rapidocr_models_bytes"] = rapid
    result["rapidocr_models_mb"] = round(rapid / 1e6, 1)
    # note: walk_total counts durable_hub + xet_cache + any staging; on a fresh xet
    # download walk_total is ~2x durable_hub. Report durable_hub as the on-disk model
    # footprint and walk_total only with the xet-cache caveat.

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
