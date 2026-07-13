#!/usr/bin/env python3
"""Generate synthetic PDFs with KNOWN ground-truth tables, for exact TableFormer
cell-fidelity measurement. Each generated PDF has a sidecar JSON ground truth so a
scorer can compute cell-level accuracy without human judgement.

Cases (chosen to stress Docling's TableFormer layout model, its headline claim):
  T1  simple bordered grid (baseline)              — 5 cols x 8 rows
  T2  borderless table (no rule lines at all)      — the hard case for line-detection
  T3  horizontal span (merged header over 2 cols)  — multi-level column header
  T4  vertical span (rowspan merged cell)          — merged down the first column
  T5  spanning + borderless combined               — worst case
  T6  numeric right-aligned financials + blank col — empty-cell handling
  T7  wide table (12 columns)                      — wide-table wrap/shift stress

Ground truth is a dense matrix (row-major) with span metadata. reportlab renders
exactly what we specify, so the matrix IS the truth by construction.
"""
import json, os, sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

OUT = os.path.join(os.path.dirname(__file__), "..", "artifacts", "fixtures", "pdf")
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)
styles = getSampleStyleSheet()


def render(name, title, data, style_cmds, spans=None, note=""):
    """data: list[list[str]] fully-expanded matrix (merged cells repeat the value in
    the covered region as reportlab requires the top-left to hold content).
    spans: list of ((c0,r0),(c1,r1)) SPAN regions for ground-truth metadata."""
    path = os.path.join(OUT, f"{name}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.7*inch, bottomMargin=0.7*inch)
    story = [Paragraph(title, styles["Heading2"]), Spacer(1, 8)]
    if note:
        story += [Paragraph(note, styles["Normal"]), Spacer(1, 8)]
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    doc.build(story)
    # ground truth sidecar
    gt = {
        "name": name, "title": title,
        "n_rows": len(data), "n_cols": len(data[0]) if data else 0,
        "cells": data,                       # row-major, exactly as rendered
        "spans": spans or [],                # ((c0,r0),(c1,r1)) inclusive
        "note": note,
    }
    with open(os.path.join(OUT, f"{name}.groundtruth.json"), "w") as f:
        json.dump(gt, f, indent=2)
    size = os.path.getsize(path)
    print(f"  {name}.pdf  ({len(data)}x{len(data[0])})  {size} bytes")
    return gt


def grid_border(nc, nr):
    return [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e1f2")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]


def main():
    manifest = []

    # T1 — simple bordered grid, 5 cols x 8 rows (1 header + 7 data)
    hdr = ["SKU", "Product", "Region", "Qty", "Revenue"]
    rows = [
        ["A-1001", "Widget Alpha", "EMEA", "1240", "18600.00"],
        ["A-1002", "Widget Beta", "APAC", "890", "13350.50"],
        ["A-1003", "Gadget Gamma", "AMER", "2310", "46200.00"],
        ["A-1004", "Gadget Delta", "EMEA", "540", "8100.75"],
        ["A-1005", "Sprocket Eps", "APAC", "1780", "26700.00"],
        ["A-1006", "Sprocket Zeta", "AMER", "330", "4950.25"],
        ["A-1007", "Cog Eta", "EMEA", "1990", "29850.00"],
    ]
    manifest.append(render("table_t1_simple_grid", "T1 — Simple bordered grid",
                           [hdr] + rows, grid_border(5, 8)))

    # T2 — borderless (NO rule lines). Same content, only column-header bottom rule.
    manifest.append(render("table_t2_borderless", "T2 — Borderless table (no grid lines)",
                           [hdr] + rows,
                           [("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")],
                           note="This table has no interior or exterior borders — only a single rule under the header."))

    # T3 — horizontal span: a 2-level header where 'Q1 2026' spans Units+Value.
    data_t3 = [
        ["Region", "Q1 2026", "Q1 2026", "Q2 2026", "Q2 2026"],
        ["", "Units", "Value", "Units", "Value"],
        ["EMEA", "1240", "18600", "1310", "19650"],
        ["APAC", "890", "13350", "970", "14550"],
        ["AMER", "2310", "46200", "2510", "50200"],
        ["LATAM", "540", "8100", "600", "9000"],
    ]
    spans_t3 = [((1, 0), (2, 0)), ((3, 0), (4, 0)), ((0, 0), (0, 1))]
    style_t3 = grid_border(5, 6) + [
        ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)), ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#d9e1f2")),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 1), "CENTER"),
    ]
    manifest.append(render("table_t3_colspan_header", "T3 — Merged 2-level column header (horizontal span)",
                           data_t3, style_t3, spans=spans_t3,
                           note="'Q1 2026' spans the Units+Value columns; region label spans two header rows."))

    # T4 — vertical span (rowspan): 'North' merged across 3 rows in column 0.
    data_t4 = [
        ["Zone", "City", "Stores", "AOV"],
        ["North", "Boston", "12", "84.20"],
        ["North", "Chicago", "9", "77.10"],
        ["North", "Detroit", "5", "69.90"],
        ["South", "Austin", "14", "91.30"],
        ["South", "Miami", "8", "88.75"],
    ]
    # ground-truth: rows 1-3 col0 are one merged 'North', rows 4-5 col0 one merged 'South'
    spans_t4 = [((0, 1), (0, 3)), ((0, 4), (0, 5))]
    style_t4 = grid_border(4, 6) + [
        ("SPAN", (0, 1), (0, 3)), ("SPAN", (0, 4), (0, 5)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    manifest.append(render("table_t4_rowspan", "T4 — Merged row-label cell (vertical span)",
                           data_t4, style_t4, spans=spans_t4,
                           note="'North' is one cell spanning 3 rows; 'South' spans 2 rows."))

    # T5 — spanning header + borderless (worst realistic case)
    style_t5 = [
        ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)), ("SPAN", (0, 0), (0, 1)),
        ("LINEBELOW", (0, 1), (-1, 1), 0.75, colors.black),
        ("LINEBELOW", (1, 0), (2, 0), 0.4, colors.black),
        ("LINEBELOW", (3, 0), (4, 0), 0.4, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 1), "CENTER"),
    ]
    manifest.append(render("table_t5_span_borderless", "T5 — Merged header + borderless (combined)",
                           data_t3, style_t5, spans=spans_t3,
                           note="Same 2-level header as T3 but with no full grid — only header rules."))

    # T6 — financials with a fully-blank column + right-aligned numerics
    data_t6 = [
        ["Account", "2024", "Adj.", "2025", "Notes"],
        ["Revenue", "1,204,000", "", "1,388,500", "organic"],
        ["COGS", "(602,000)", "", "(661,200)", ""],
        ["Gross profit", "602,000", "", "727,300", ""],
        ["Opex", "(410,500)", "", "(455,900)", ""],
        ["Operating income", "191,500", "", "271,400", "up 41.7%"],
    ]
    spans_t6 = []
    style_t6 = grid_border(5, 6) + [
        ("ALIGN", (1, 0), (3, -1), "RIGHT"),
    ]
    manifest.append(render("table_t6_financial_blankcol", "T6 — Financials, blank 'Adj.' column, right-aligned",
                           data_t6, style_t6, spans=spans_t6,
                           note="The 'Adj.' column is entirely empty; numerics are right-aligned and parenthesised."))

    # T7 — wide table, 12 columns (monthly)
    months = ["Item"] + [m for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov"]]
    data_t7 = [months]
    for item, base in [("Alpha", 100), ("Beta", 210), ("Gamma", 55), ("Delta", 333)]:
        data_t7.append([item] + [str(base + i * 7) for i in range(11)])
    manifest.append(render("table_t7_wide_12col", "T7 — Wide table (12 columns)",
                           data_t7, grid_border(12, 5),
                           note="12 columns to stress horizontal layout / column-shift on a wide grid."))

    with open(os.path.join(OUT, "TABLE_GROUNDTRUTH_INDEX.json"), "w") as f:
        json.dump([{"name": m["name"], "n_rows": m["n_rows"], "n_cols": m["n_cols"],
                    "n_spans": len(m["spans"])} for m in manifest], f, indent=2)
    print(f"\nGenerated {len(manifest)} synthetic table PDFs + ground truth into {OUT}")


if __name__ == "__main__":
    main()
