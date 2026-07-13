#!/usr/bin/env python3
"""Substantiate Docling's 'unified multi-format' claim on DOCX / XLSX / PPTX with
known ground-truth probes + structure checks. Also exports to JSON to test the
lossless-DoclingDocument claim (does export_to_dict round-trip the content)."""
import json, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DOCS = os.path.join(ROOT, "artifacts", "fixtures", "docs")


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
            hc[len(m.group(1))] = hc.get(len(m.group(1)), 0) + 1
    return hc


def main():
    with open(os.path.join(DOCS, "DOC_GROUNDTRUTH.json")) as f:
        gt = json.load(f)
    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()

    results = []
    for fname, meta in gt.items():
        path = os.path.join(DOCS, fname)
        t0 = time.perf_counter()
        res = conv.convert(path)
        dt = round(time.perf_counter() - t0, 3)
        md = res.document.export_to_markdown()
        probe_hits = {p: (p.lower() in md.lower()) for p in meta["probes"]}
        # JSON round-trip (lossless claim) — export dict and re-check probes survive
        try:
            dj = res.document.export_to_dict()
            json_blob = json.dumps(dj).lower()
            json_probe_hits = {p: (p.lower() in json_blob) for p in meta["probes"]}
            json_ok = all(json_probe_hits.values())
        except Exception as e:
            json_ok = False
            json_probe_hits = {"error": str(e)}
        entry = {
            "file": fname, "convert_s": dt, "md_chars": len(md),
            "n_md_tables": count_md_tables(md), "heading_counts": heading_counts(md),
            "probe_hits": probe_hits, "all_probes_found": all(probe_hits.values()),
            "json_all_probes_found": json_ok,
            "md_excerpt": md[:900],
        }
        results.append(entry)
        print(f"{fname}: {dt}s probes={sum(probe_hits.values())}/{len(meta['probes'])} "
              f"tables={entry['n_md_tables']} json_ok={json_ok}")
        with open(os.path.join(ROOT, "artifacts", "raw", f"doc_{fname.replace('.','_')}.md"), "w") as f:
            f.write(md)

    outp = os.path.join(ROOT, "artifacts", "raw", "multiformat_docs.json")
    with open(outp, "w") as f:
        json.dump({"tool": "docling", "results": results}, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
