#!/usr/bin/env python3
"""Compute the docling deep-test summary JSON from the raw result files. Every number
here is derived from a run artifact — nothing is hand-authored. This is the anti-
hardcoding gate: the summary is a pure function of artifacts/raw/*.json."""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "artifacts", "raw")


def load(name):
    p = os.path.join(RAW, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def main():
    summary = {"tool": "docling"}

    cold = load("pdf_coldstart_download.json")
    if cold:
        summary["coldstart"] = {
            "import_s": cold.get("import_s"),
            "first_pdf_convert_s_incl_download": cold.get("first_pdf_convert_s"),
            "second_pdf_convert_s_warm": cold.get("second_pdf_convert_s"),
            "hf_model_download_mb_reported": cold.get("model_download_mb"),
        }

    tf = load("pdf_table_fidelity.json")
    if tf:
        rows = tf["results"]
        detected = [r for r in rows if r.get("detected")]
        summary["table_fidelity"] = {
            "n_tables_tested": len(rows),
            "n_detected": len(detected),
            "n_dims_match": sum(1 for r in rows if r.get("dims_match")),
            "n_recall_1.0": sum(1 for r in detected if r.get("cell_recall") == 1.0),
            "mean_cell_recall_of_detected": round(
                sum(r.get("cell_recall", 0) for r in detected) / max(len(detected), 1), 4),
            "not_detected": [r["name"] for r in rows if not r.get("detected")],
            "per_table": {r["name"]: {"detected": r.get("detected"),
                                       "dims_match": r.get("dims_match"),
                                       "cell_recall": r.get("cell_recall"),
                                       "convert_s": r.get("convert_s")} for r in rows},
        }

    real = load("pdf_real_and_scanned.json")
    if real:
        rows = real["results"]
        summary["real_and_scanned"] = {}
        for r in rows:
            if "error" in r:
                continue
            entry = {"n_pages": r.get("n_pages"), "convert_s": r.get("convert_s"),
                     "s_per_page": r.get("s_per_page"), "n_md_tables": r.get("n_md_tables"),
                     "md_chars": r.get("md_chars")}
            if r.get("probe_hits"):
                entry["probes_found"] = sum(r["probe_hits"].values())
                entry["probes_total"] = len(r["probe_hits"])
            if r.get("reading_order"):
                entry["reading_order_in_order"] = r["reading_order"].get("in_order")
                entry["sections_present"] = f"{r['reading_order'].get('n_present')}/{r['reading_order'].get('n_total')}"
            if "ocr_produced_text" in r:
                entry["ocr_produced_text"] = r.get("ocr_produced_text")
                entry["ocr_body_chars"] = r.get("ocr_body_chars")
            summary["real_and_scanned"][r["file"]] = entry

    mf = load("multiformat_docs.json")
    if mf:
        summary["multiformat"] = {
            r["file"]: {"convert_s": r.get("convert_s"),
                        "all_probes_found": r.get("all_probes_found"),
                        "json_all_probes_found": r.get("json_all_probes_found"),
                        "n_md_tables": r.get("n_md_tables")}
            for r in mf["results"]}

    bp = load("html_boilerplate_quant.json")
    if bp:
        summary["html_boilerplate"] = {
            r["file"]: {"pct_boilerplate_lines": r.get("pct_boilerplate_lines"),
                        "boilerplate_marker_lines": r.get("boilerplate_marker_lines"),
                        "lines_before_main_heading": r.get("lines_before_main_heading")}
            for r in bp["results"]}

    outp = os.path.join(RAW, "docling-deep-summary.json")
    with open(outp, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print("\nWROTE", outp)


if __name__ == "__main__":
    main()
