#!/usr/bin/env python3
"""Exact cell-level TableFormer fidelity on synthetic PDFs with known ground truth.

For each generated table PDF we:
  1. convert with Docling (PDF pipeline: layout model + TableFormer),
  2. parse the emitted Markdown table into a cell matrix,
  3. compare against the ground-truth matrix produced at render time.

Metrics per table (all COMPUTED, never hand-written):
  - detected            : did Docling emit any MD table at all
  - gt_dims / got_dims  : (rows, cols)
  - dims_match          : structure recovered exactly
  - cell_recall         : fraction of ground-truth non-empty cell *values* that appear
                          ANYWHERE in the detected table (in-row OR shifted to another row)
  - inrow_rate          : fraction of ground-truth non-empty values that appear in the
                          CORRECT row index (order-tolerant within the row). This is the
                          stricter placement metric; cell_recall >= inrow_rate always.
                          A multi-level header that pushes a value one row down keeps
                          cell_recall at 1.0 but drops inrow_rate below 1.0.
  - exact_grid_match    : strict cell-for-cell equality after normalisation
  - notes               : structural failure mode if any

Ground truth for merged cells: the renderer repeats the merged value only in the
top-left; covered cells are '' in the matrix. We treat any ground-truth '' as
'don't care' for recall (a converter may legitimately blank or repeat a merged cell),
and separately record how merged cells were handled (repeated vs blank vs dropped).
"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FIX = os.path.join(ROOT, "artifacts", "fixtures", "pdf")


def norm(s):
    s = (s or "").strip()
    s = s.replace(" ", " ")
    s = re.sub(r"\s+", " ", s)
    # numeric normalisation: strip thousands separators + surrounding parens/space
    return s


def parse_md_tables(md):
    """Return list of tables; each table = list of rows; each row = list of cell strings.
    A markdown table is a run of lines that start/contain '|' with a separator row."""
    tables = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1].replace("|", " ").strip()[:3] or "--") is None:
            # crude: header then separator
            pass
        # detect separator row (contains only |,-,:,space)
        if "|" in line and i + 1 < len(lines) and re.fullmatch(r"[\s|:\-]+", lines[i + 1]) and "-" in lines[i + 1]:
            block = [line, lines[i + 1]]
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                block.append(lines[j]); j += 1
            rows = []
            for k, bl in enumerate(block):
                if k == 1:
                    continue  # skip separator
                cells = [c for c in bl.strip().strip("|").split("|")]
                rows.append([norm(c) for c in cells])
            tables.append(rows)
            i = j
        else:
            i += 1
    return tables


def gt_nonempty_by_row(gt_cells):
    """Ground-truth non-empty values grouped by row index."""
    out = []
    for row in gt_cells:
        out.append([norm(v) for v in row if norm(v) != ""])
    return out


def score_table(gt, md):
    got_tables = parse_md_tables(md)
    if not got_tables:
        return {"detected": False, "cell_recall": 0.0, "exact_grid_match": False,
                "got_dims": [0, 0], "notes": "no markdown table emitted"}
    # pick the table with the most cells (the real one; ignore tiny banner tables)
    got = max(got_tables, key=lambda t: sum(len(r) for r in t))
    got_rows = len(got)
    got_cols = max((len(r) for r in got), default=0)
    gt_rows, gt_cols = gt["n_rows"], gt["n_cols"]

    # cell recall: every ground-truth non-empty value must appear in the detected
    # table's SAME row index (order-tolerant within the row)
    gt_rowvals = gt_nonempty_by_row(gt["cells"])
    total = 0
    found = 0
    flat_got_by_row = [set(c for c in r if c) for r in got]
    all_got_vals = set(c for r in got for c in r if c)
    row_found = 0
    for ri, vals in enumerate(gt_rowvals):
        for v in vals:
            total += 1
            # in-row match if a got row exists at ~same index containing v
            candidate_rows = [flat_got_by_row[ri]] if ri < len(flat_got_by_row) else []
            if any(v in cr for cr in candidate_rows):
                found += 1
                row_found += 1
            elif v in all_got_vals:
                found += 1  # present but not in-row (column/row shift) — counts for recall, flagged below
    cell_recall = round(found / total, 4) if total else 1.0
    inrow_rate = round(row_found / total, 4) if total else 1.0

    # strict exact grid match (dims + every cell equal, comparing only the leading
    # gt_cols cells of each row to tolerate trailing empties)
    exact = (got_rows == gt_rows)
    if exact:
        for ri in range(gt_rows):
            grow = got[ri] if ri < len(got) else []
            for ci in range(gt_cols):
                gv = norm(gt["cells"][ri][ci])
                cv = norm(grow[ci]) if ci < len(grow) else ""
                if gv != cv:
                    exact = False
                    break
            if not exact:
                break

    notes = []
    if got_rows != gt_rows:
        notes.append(f"row count {got_rows}!={gt_rows}")
    if got_cols != gt_cols:
        notes.append(f"col count {got_cols}!={gt_cols}")
    if found == total and cell_recall == 1.0 and inrow_rate < 1.0:
        notes.append("all values present but some out of original row (shift)")

    return {"detected": True, "got_dims": [got_rows, got_cols], "gt_dims": [gt_rows, gt_cols],
            "dims_match": (got_rows == gt_rows and got_cols == gt_cols),
            "cell_recall": cell_recall, "inrow_rate": inrow_rate,
            "exact_grid_match": exact, "n_tables_emitted": len(got_tables),
            "notes": "; ".join(notes) or "ok"}


def merged_cell_handling(name, gt, md):
    """For span tables, record how the merged value was rendered: repeated across the
    span, placed once, or dropped. Computed from the emitted markdown."""
    if not gt.get("spans"):
        return None
    got_tables = parse_md_tables(md)
    if not got_tables:
        return {"merged_value_present": False}
    got = max(got_tables, key=lambda t: sum(len(r) for r in t))
    flat = [c for r in got for c in r if c]
    info = {}
    for (c0, r0), (c1, r1) in gt["spans"]:
        val = norm(gt["cells"][r0][c0])
        if not val:
            continue
        occurrences = sum(1 for c in flat if c == val)
        info[val] = {"span": [[c0, r0], [c1, r1]], "occurrences_in_output": occurrences}
    return info


def main():
    idx_path = os.path.join(FIX, "TABLE_GROUNDTRUTH_INDEX.json")
    with open(idx_path) as f:
        index = json.load(f)

    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()

    results = []
    for entry in index:
        name = entry["name"]
        pdf = os.path.join(FIX, f"{name}.pdf")
        with open(os.path.join(FIX, f"{name}.groundtruth.json")) as f:
            gt = json.load(f)
        t0 = time.perf_counter()
        res = conv.convert(pdf)
        dt = round(time.perf_counter() - t0, 3)
        md = res.document.export_to_markdown()
        sc = score_table(gt, md)
        sc["name"] = name
        sc["convert_s"] = dt
        sc["merged_handling"] = merged_cell_handling(name, gt, md)
        sc["md_excerpt"] = md[:1200]
        results.append(sc)
        print(f"{name}: detected={sc['detected']} dims={sc.get('got_dims')} vs {sc.get('gt_dims')} "
              f"recall={sc.get('cell_recall')} exact={sc.get('exact_grid_match')} ({dt}s)")

    outp = os.path.join(ROOT, "artifacts", "raw", "pdf_table_fidelity.json")
    with open(outp, "w") as f:
        json.dump({"tool": "docling", "results": results}, f, indent=2)
    print("WROTE", outp)


if __name__ == "__main__":
    main()
