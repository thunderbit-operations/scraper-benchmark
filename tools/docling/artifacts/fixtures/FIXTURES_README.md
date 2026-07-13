# Docling fixtures — how to reproduce

Small fixtures are committed. Two sets are **not** committed (size / provenance) and must be re-fetched before running `tests/pdf_real_and_scanned.py`:

## Real academic PDFs (`pdf/`) — re-download
```bash
curl -sL "https://arxiv.org/pdf/2408.09869" -o pdf/arxiv_docling_report.pdf   # the Docling technical report, 9pp
curl -sL "https://arxiv.org/pdf/1706.03762" -o pdf/arxiv_attention.pdf        # Attention Is All You Need, 15pp
```

## Scanned / OCR fixtures (`scanned/`) — from Docling's own test suite (Apache-2.0/MIT)
```bash
BASE="https://raw.githubusercontent.com/docling-project/docling/main/tests/data/scanned/sources"
curl -sL "$BASE/ocr_test.pdf"           -o scanned/ocr_test.pdf            # 1pp scan, 0 text layer
curl -sL "$BASE/nemotron_multipage.pdf" -o scanned/nemotron_multipage.pdf  # 4pp scan
curl -sL "$BASE/old_newspaper.png"      -o scanned/old_newspaper.png
curl -sL "$BASE/qr_bill_example.jpg"    -o scanned/qr_bill_example.jpg
```

## Committed (regenerate with the venv python)
- `pdf/table_t*.pdf` + `pdf/*.groundtruth.json` — synthetic tables with known ground truth: `python tests/gen_pdf_fixtures.py`
- `docs/*.{docx,xlsx,pptx}` + `docs/DOC_GROUNDTRUTH.json` — `python tests/gen_doc_fixtures.py`

## Environment
```bash
python3.10+ -m venv .venv && . .venv/bin/activate
pip install docling reportlab python-docx openpyxl python-pptx xlsxwriter
# first PDF conversion downloads ~576 MB of models (see research-materials.md §first run)
```
