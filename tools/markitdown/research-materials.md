# MarkItDown Review Research Materials

Date: 2026-07-13 (deep pass under methodology v3; supersedes the 2026-07-10 smoke-test pack)

Status: source material for a future Thunderbit blog article. This is **not** a final blog draft and should not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **MarkItDown** (`microsoft/markitdown`), a Python utility that converts files and Office documents to Markdown for LLM/text pipelines. It contains: an install-friction deep-dive (the `[all]`→0.0.2 backtrack **root-caused to the exact PyPI constraint and matched to the upstream fix issue**, a measured core-install footprint, and a cold-import profile), an HTML→Markdown pass on the four shared web fixtures used across this review series (with **quantified boilerplate residue**), a document-type matrix over **real public documents** (arXiv PDF with a text layer, an image-only scanned PDF with no text layer, DOCX/XLSX/PPTX, a DOCX with equations), a **13-case complex-table structural matrix scored against a pre-registered manifest**, a deep-nesting recursion-fallback probe, and a scale/stress run (a 492-page government PDF, a 50k-row XLSX) with timing distributions and clean-process peak RSS. The later writing stage decides the final article structure, screenshots, narrative angle, and Thunderbit positioning.

**Positioning note (read first):** MarkItDown is a **document-to-Markdown converter**, not a web scraper or crawler. It has **no HTTP crawling, no JavaScript rendering, no link-following, no pagination, and no boilerplate/main-content extraction**. It takes bytes you already have (a local file or a stream) and converts the whole document to Markdown. For comparability we fed it the **same local HTML fixtures** the other tools in this series ingest, but the fair framing is "how good is its HTML→Markdown conversion," not "how good a scraper is it." Its home turf is **PDF / DOCX / PPTX / XLSX → Markdown** — see §B.

All measurements are on one machine (macOS arm64 / Python 3.14.2) and reproducible from the scripts in `tests/`. Failures are recorded as failures. Untested areas are in **Gaps**. Every result field in `artifacts/raw/*.json` is computed from a run, not hand-written.

**Reproducible pack (this repo):** the harness, fixtures, and raw results live in this benchmark repository under `tools/markitdown/` (`github.com/thunderbit-operations/scraper-benchmark`, MIT). From that directory a fresh checkout regenerates the headline complex-table findings out of the box (`PYTHONPATH=tests python -c "import deep_convert; …run_tables…"` → 13/13 cases, identical ragged/broken set); the four large document fixtures are omitted from git and re-fetchable/regenerable per `artifacts/fixtures/FIXTURES_README.md`. The `artifacts/raw/md_outputs/table_*.md` files are the exact Markdown MarkItDown emitted for each table case.

### How to read the findings

Findings are numbered `FINDING-NN` and carry two tags:

- a **confidence** tag — `[multi-run]` (held across all timing runs / reproduced by ≥2 separate checks), `[single-observation]` (measured once), or `[hypothesis]` (mechanism proposed but no attribution experiment run); and
- a **novelty** tag from the pre-registration search (§Novelty verification) — `[EXCLUSIVE]`, `[KNOWN-ISSUE: link]`, or `[DOCUMENTED]`.

No finding is dressed up with self-evaluative adjectives by this document; novelty is decided by the search table, not by adjective.

## Source Snapshot

MarkItDown is positioned by Microsoft as a lightweight Python utility that converts many formats — Office documents, PDF, images, audio, HTML, CSV/JSON/XML, ZIP, EPub, and YouTube URLs — into Markdown optimized for LLMs. It exposes a **CLI** (`markitdown file.pdf -o out.md`, or stdin piping), a **Python API** (`MarkItDown().convert(...)`), and an optional **MCP server**. Source: [MarkItDown GitHub README](https://github.com/microsoft/markitdown) (Tier 1).

Point-in-time repo metadata fetched from the GitHub API and PyPI on **2026-07-13** (refresh within 48h of publication):

| Field | Value |
|---|---|
| Repo | [microsoft/markitdown](https://github.com/microsoft/markitdown) |
| Description | "Python tool for converting files and office documents to Markdown." |
| Stars | **165,282** |
| Forks | **11,790** |
| Open issues | **833** |
| License | **MIT** |
| Default branch | **main** |
| Created | **2024-11-13** |
| Latest GitHub release | **v0.1.6** ("Version 0.1.6"), published **2026-05-26** |
| Last push to repo | **2026-06-24** |
| PyPI version tested | **0.1.6** |
| PyPI Python requirement | **`>=3.10`** |

Raw snapshots: [github_repo_snapshot_2026-07-13.json](artifacts/raw/github_repo_snapshot_2026-07-13.json), [github_release_latest_2026-07-13.json](artifacts/raw/github_release_latest_2026-07-13.json), [pypi_snapshot_2026-07-13.json](artifacts/raw/pypi_snapshot_2026-07-13.json).

*Editorial note:* the star count is very high (Microsoft-org repo) and reflects general LLM-tooling popularity, not web-extraction depth. Do not over-read it as a maturity signal for the scraping/conversion internals.

## Novelty verification (pre-registration search)

Before any finding was written up, each candidate was searched against three sources: the upstream issue tracker (`microsoft/markitdown` **and**, where relevant, its conversion dependency `markdownify`), the official README/docs, and the top SERP results (incl. published third-party benchmarks). Classification is `EXCLUSIVE` (zero hits), `KNOWN-ISSUE` (recorded upstream, link given), or `DOCUMENTED`.

| Candidate finding | Verdict | Prior record |
|---|---|---|
| `pip install markitdown[all]` silently backtracks to 0.0.2 on current PyPI | **KNOWN-ISSUE** | [markitdown#2179](https://github.com/microsoft/markitdown/issues/2179) (open, 2026-06-30, *"unpin youtube-transcript-api in [all] extra (broken on current PyPI)"*) states the identical root cause (the `~=1.0.0` pin is unsatisfiable; silent downgrade to 0.0.2). Our added detail: re-confirmed live **as-of 2026-07-13**, plus the Python-3.14 version-gate interaction (see FINDING-01). The 2026-07-10 draft attributed this to `magika`; that attribution is **corrected** here to match the tracker. |
| Scanned / image-only PDF yields empty output, no OCR, no error | **KNOWN-ISSUE** | OCR-for-scanned-PDF is an open, heavily-tracked gap: [#1268](https://github.com/microsoft/markitdown/issues/1268) (*"Add OCR fallback for scanned/non-searchable PDFs"*), plus #1650/#1652/#1863/#1888/#1920 and PRs. Our added detail: the exact **0-char, no-exception** behavior on a controlled no-text-layer fixture (FINDING-05). |
| In-cell `\|` corrupts HTML→Markdown table columns (not escaped) | **KNOWN-ISSUE (class), HTML path is the added detail** | The pipe-escaping bug class is tracked for the **CSV** converter ([#2019](https://github.com/microsoft/markitdown/issues/2019), open BUG; plus #1785 PPTX, #1872, #2035). Those issues are CSV/PPTX-specific; the **HTML→markdownify path** we exercise (T12) is not in them, and the root cause is upstream `markdownify`'s default `convert_td` (see FINDING-08). |
| Nested HTML table / colspan / rowspan degrade the GFM grid | **KNOWN-ISSUE (design limitation)** | The Markdown-table target's structural limits are tracked: [#1211](https://github.com/microsoft/markitdown/issues/1211) (*"Use HTML tables instead of Markdown syntax for better table support"*), [#1248](https://github.com/microsoft/markitdown/issues/1248) (*"Nested tables in DOCX are lost"*). Our added detail: a **13-case controlled matrix** quantifying which span/nesting/ragged shapes break vs survive (FINDING-07). |
| MarkItDown PDF output has no heading hierarchy; table fidelity is low | **DOCUMENTED** | Independent public benchmarks report the same: the OpenDataLoader / READoc-style comparisons put MarkItDown's PDF heading-hierarchy at ~0.0 and table fidelity ~0.27, well below Docling (see [danilchenko.dev](https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/), [jimmysong.io](https://jimmysong.io/blog/pdf-to-markdown-open-source-deep-dive/), [READoc arXiv 2409.05137](https://arxiv.org/pdf/2409.05137)). Our result **reproduces** this on our own fixtures (FINDING-06). |
| Core `import markitdown` costs ~2.5 s (eager pandas/magika/pptx load) | **EXCLUSIVE** (zero hits) | Issue-tracker search for slow-import/lazy-loading: **0 hits**. README: not mentioned. SERP: only generic "pandas import is slow" threads ([pandas#7282](https://github.com/pandas-dev/pandas/issues/7282)), nothing MarkItDown-specific. The measurement and the eager-`converters`-registry root cause (FINDING-02) are not previously recorded. Low controversy — it is a startup-latency observation, not a correctness claim. |
| Deeply-nested HTML (~≥500 levels) silently drops all Markdown structure | **KNOWN-ISSUE (by-design fallback), threshold is the added detail** | The behavior is **intentional and documented in the source** (`_html_converter.py` catches `RecursionError` and falls back to `get_text()` with a warning). Our added detail: the measured threshold (survives at depth 400, falls back at 500) and confirmation that headings collapse (FINDING-09). |

**Consequence for the writer:** most findings here are **reproductions + quantification + live re-confirmation of already-public issues**, and must be framed that way (with the issue links), not as discoveries. The independent benchmark corroboration (heading=0, table fidelity low) is a *strength* of the evidence, not a weakness — it means our numbers agree with a third party. The one finding that clears all three novelty arms is the **~2.5 s cold-import tax** (FINDING-02).

## Official Capability Claims to Verify

From the README (Tier 1):

1. **Broad format coverage**: PDF, PowerPoint, Word, Excel, Images (EXIF + optional OCR/LLM captioning), Audio (EXIF + optional transcription), HTML, text formats, ZIP, YouTube, EPub.
2. **LLM-oriented Markdown**: token-efficient, structure-preserving for downstream LLM use — explicitly *not* pixel-perfect rendering.
3. **Optional extras / plugins**: functionality gated behind pip extras (`[pdf]`, `[docx]`, `[pptx]`, `[xlsx]`, `[xls]`, `[audio-transcription]`, `[youtube-transcription]`, `[az-doc-intel]`, `[outlook]`, and a bundle `[all]`), plus a plugin system and an optional Azure Document Intelligence backend.
4. **CLI + Python API + optional MCP server**.

What the README does **not** claim, and we verified it does not do: crawling, JS rendering, link-following, or readability-style main-content extraction. This is the single most important framing for the article. Coverage claims for images/audio/OCR/Azure are **not** exercised here (no OCR engine / model / keys) and are flagged in **Gaps**.

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS arm64 (Apple Silicon), macOS 26.5.2 |
| Python | **3.14.2** |
| MarkItDown | **0.1.6** |
| Conversion deps (measured) | markdownify **1.2.3**, beautifulsoup4 **4.15.0**, pdfminer-six **20260107**, pdfplumber **0.11.10**, mammoth **1.11.0** (DOCX), python-pptx **1.0.2**, openpyxl **3.1.5**, magika **0.6.3**, onnxruntime **1.27.0** |
| Install method | isolated `python -m venv` + pip |
| Working install command | `pip install 'markitdown==0.1.6'`, then extras individually (`[pdf]`, `[docx]`, `[pptx]`, `[xlsx]`, `[xls]`) |
| Core-only install footprint | **161 MB** (empty venv baseline 13 MB → +148 MB), see FINDING-03 |
| Full footprint (core + document extras) | **310 MB** |
| Scripts | `tests/` (see Raw Artifact Index) |

### Test corpus

- **Shared web fixtures** (same bytes as the rest of the series, fetched once with a browser UA): `books_toscrape.html` (51,294 B), `quotes_toscrape.html` (11,064 B), `scrapethissite_forms.html` (50,439 B, one real 26×9 data table), `wikipedia_web_scraping.html` (226,771 B).
- **Complex-table matrix**: `artifacts/fixtures/tables/` — 13 synthetic, individually-addressable table cases + `manifest.json` recording each case's **pre-registered** expected shape (written before the run). Generated by [make_fixtures.py](tests/make_fixtures.py).
- **Real documents** (`artifacts/fixtures/docs/`): arXiv "Attention Is All You Need" ([1706.03762](https://arxiv.org/pdf/1706.03762), 2.2 MB text-layer PDF with real tables/refs); the Bitcoin whitepaper (9 pp); an **image-only scanned PDF** we rendered so it has **zero text layer** (confirmed: pdfminer extracts 0 chars); NIST SP 800-53r5 ([492 pp, 6 MB public-domain PDF](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf)) for scale; the DOCX/XLSX/PPTX and equations.docx from **markitdown's own MIT-licensed test suite** (the files its maintainers regression-test against, seeded with UUIDs to detect silent content loss); a synthetic 50k-row XLSX and a 64-column XLSX.

## A. HTML → Markdown on the shared web fixtures (+ boilerplate residue)

All four converted successfully on the **core** install (no extras needed for HTML). Metrics computed from the produced Markdown; timings are the median of 5 conversions. Boilerplate residue = the fraction of non-empty output lines containing any of a **pre-registered** set of site-chrome markers (`jump to content`, `retrieved from`, `per page`, `©`, `cookie`, `log in`, `languages`, …). Data: [deep_convert.json](artifacts/raw/deep_convert.json) → `web`.

| Fixture | out chars | h1/h2/h3 | GFM table rows | MD links | body probes | **chrome-line residue** | median ms |
|---|---:|:--:|---:|---:|:--:|---:|---:|
| books.toscrape | 10,478 | 1 / 0 / 0 | 0 | 94 | 5/5 | **0.6%** (1/159) | 0.02 |
| quotes.toscrape | 2,973 | 1 / 1 / 0 | 0 | 55 | 4/4 | **1.2%** (1/86) | 0.01 |
| scrapethissite/forms | 3,385 | 1 / 0 / 0 | **27** | 31 | 4/4 | **6.7%** (5/75) | 0.01 |
| wikipedia/Web_scraping | 60,159 | 1 / **7** / **12** | 9 | 418 | 5/5 | **12.4%** (42/338) | 0.05 |

**FINDING-04 [multi-run] [DOCUMENTED]:** on well-tagged HTML, MarkItDown's HTML→Markdown is **fast and content-complete** — all four pages convert in **10–50 ms** on local fixtures, every body probe survives (5/5, 4/4, 4/4, 5/5), heading structure mirrors the source (Wikipedia: h1×1/h2×7/h3×12, matching the article's section tree), and links are preserved as real `[text](url)` (418 on Wikipedia). The 26×9 hockey-stats `<table>` on the forms page becomes a proper GFM pipe table (27 rows = header + separator + 26 data rows) with empty cells preserved. This is the whole-document conversion the tool is built for, and on clean HTML it is faithful.

**FINDING-04a [multi-run] [DOCUMENTED]:** MarkItDown does **not** strip boilerplate, and the residue scales with page chrome — from **0.6%** of output lines on the near-chrome-free Books homepage to **12.4%** on Wikipedia (42 of 338 non-empty lines are site chrome: `jump to content`, `toggle the table of contents`, `22 languages`, `retrieved from`, `this page was last edited`, cookie/CC-license footers). The Wikipedia maintenance banners ("This article needs additional citations") are faithfully converted into 2-column GFM tables (that is where the 9 pipe-table rows on a page with **no real data table** come from). MarkItDown is a *whole-document* converter, not a readability extractor: `faithful HTML→Markdown ≠ clean article extraction`. Tools like trafilatura/Firecrawl aim to return only main content; MarkItDown returns the whole page, boilerplate included. Neither is wrong — different jobs. (Root cause in source: `_html_converter.py` extracts `<script>`/`<style>` only, then hands the entire `<body>` to markdownify — no main-content heuristic.)

## B. Document-type matrix (real public documents)

Python API, core+document-extras install. Structural probes are pre-registered `must_contain` strings; timings are the median of 3 conversions. Data: [deep_convert.json](artifacts/raw/deep_convert.json) → `docs`. Raw Markdown: `artifacts/raw/md_outputs/`.

| Document | input | out chars | GFM rows | probes | median ms | notes |
|---|---:|---:|---:|:--:|---:|---|
| arXiv 1706.03762 (text-layer PDF) | 2.2 MB | 40,174 | 72 | **7/7** | 930 | title, "Transformer", "Multi-Head Attention", "BLEU", "References" all present |
| Bitcoin whitepaper (9 pp PDF) | 184 KB | 22,485 | 24 | **6/6** | 377 | "Satoshi Nakamoto", "Abstract", "proof-of-work", "Conclusion" present |
| **scanned PDF (no text layer)** | 89 KB | **0** | 0 | **0/4** | 2.5 | **empty output, no error, no OCR** — FINDING-05 |
| DOCX (test.docx) | 136 KB | 4,651 | 7 | — | 19 | headings + GFM table + image alt-text; embedded UUIDs survive |
| DOCX equations | 15 KB | 240 | 0 | — | 15 | **LaTeX math preserved**: `$$sin θ=\frac{mλ}{a}…$$` — FINDING-10 |
| XLSX (test.xlsx) | 12 KB | 808 | 31 | — | 10 | each sheet → `## SheetName` + GFM table |
| PPTX (test.pptx) | 278 KB | 2,047 | 11 | — | 12 | `<!-- Slide number: N -->` markers, tables, even a chart→table |

**FINDING-05 [multi-run] [KNOWN-ISSUE: [#1268](https://github.com/microsoft/markitdown/issues/1268)]:** on an **image-only PDF with no text layer**, MarkItDown returns an **empty string** — **0 characters, no exception, no warning** (converted in 2.5 ms because there is nothing to extract). MarkItDown's PDF path is text-extraction only (pdfminer/pdfplumber); it ships **no OCR** in core or any pip extra. A developer feeding a batch of PDFs where some are scans gets silently empty results for those files with no signal that anything was skipped. This reproduces the long-open OCR-fallback gap (#1268 and siblings) with the exact no-error behavior. The recommended path (per the tracker and README) is the optional Azure Document Intelligence backend or a plugin — neither is in the default install. *Root-cause check:* we confirmed the fixture itself is text-free (pdfminer `extract_text` returns 0 chars on it), so the empty output is MarkItDown's behavior on a genuine scan, not a broken fixture.

**FINDING-06 [multi-run] [DOCUMENTED]:** across **both** text-layer PDFs, MarkItDown produces **zero Markdown heading markers** (0/0/0 on the arXiv paper and the Bitcoin whitepaper) — a PDF carries no semantic heading tags, and MarkItDown does not infer them from font size, so every line lands at body level. Text recall is high (7/7 and 6/6 probes), but the *structure* is flat. This **reproduces** independent public benchmarks that score MarkItDown's PDF heading-hierarchy at ~0.0 and table fidelity ~0.27, far below Docling's TableFormer-backed ~0.88 ([danilchenko.dev](https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/), [READoc](https://arxiv.org/pdf/2409.05137)). The trade-off those benchmarks also report — MarkItDown is ~**100× faster** than Docling — is consistent with our sub-second times on documents that take Docling minutes. Suggested article framing: *MarkItDown gives you clean, fast PDF **text**; it does not give you the PDF's **structure**. If headings/tables must survive, a layout-model tool (Docling/Marker) is the right layer.*

**FINDING-10 [single-observation] [EXCLUSIVE — minor]:** the DOCX path (via `mammoth`) **preserves Office Math (OMML) equations as LaTeX** — `equations.docx` converts `$$\frac{a}{λ}=\frac{m}{sin θ}=…$$` and inline `$θ=sin^{-1}(2.2×10^{-4})$`. Issue/SERP search surfaced no write-up of this specific behavior; it is a genuine, if narrow, strength for anyone converting math-heavy Word docs for an LLM. (DOCX/XLSX/PPTX all also kept every embedded UUID sentinel, i.e. **no silent content loss** on the maintainers' own regression fixtures.)

## C. Complex-table structural matrix (13 pre-registered cases)

Each case is a single `<table>` converted in isolation and scored against `manifest.json`: did every pre-registered `must_contain` token survive, and does the pipe-column arity match what a correct GFM grid needs? "col arity" = the distinct interior-column counts across the case's emitted pipe rows (a single value means every row has the same width — a well-formed grid). Scorer: [deep_convert.py](tests/deep_convert.py) → `run_tables`; per-case Markdown in `artifacts/raw/md_outputs/table_*.md`. Data: [deep_convert.json](artifacts/raw/deep_convert.json) → `tables`.

| Case | what it stresses | tokens kept | pipe-col arity | expected cols | grid verdict |
|---|---|:--:|:--:|:--:|---|
| t01_plain | baseline 3×3 | 6/6 | [3] | 3 | faithful |
| t02_colspan_header | header colspan=2 | 9/9 | [3] | 3 | faithful (spanned header → one blank cell, arity holds) |
| t03_rowspan_col | first-col rowspan=2 | 7/7 | [2, 3] | 3 | **ragged — misaligns** (FINDING-07a) |
| t04_colrowspan | merged 2×2 block | 7/7 | [2, 4] | 4 | ragged |
| t05_nested | table inside a `<td>` | 9/9 | **[2, 14]** | 2/2 | **broken** (inner table dumped raw) |
| t06_wide24 | 24 columns | 6/6 | [24] | 24 | faithful |
| t07_headerless | no `<th>` at all | 6/6 | [3] | 3 | faithful (synthesizes a blank header, keeps all 3 rows) |
| t08_ragged | rows of 2/4/3 cells | 9/9 | [2, 3, 4] | ragged | ragged (mirrors malformed source) |
| t09_empty_cells | empty + whitespace cells | 6/6 | [3] | 3 | faithful (blanks preserved) |
| t10_block_in_cell | `<ul>`/`<br>`/link in cell | 8/8 | [2] | 2 | faithful (list flattened to `* a * b`, link kept, arity holds) |
| t11_rtl | Arabic, dir=rtl | 6/6 | [2] | 2 | faithful (RTL text intact, logical order) |
| t12_pipe_in_cell | literal `\|` in cells | 2/2 | **[2, 3, 4]** | 2 | **broken** (in-cell pipe not escaped) |
| t13_caption_tfoot | caption + multi-row thead + tfoot | 9/9 | [2, 3] | 3 | **fragments into 2 tables** |

**FINDING-07 [multi-run] [KNOWN-ISSUE (design limitation): [#1211](https://github.com/microsoft/markitdown/issues/1211), [#1248](https://github.com/microsoft/markitdown/issues/1248)]:** MarkItDown never *loses table content* — **all 13 cases keep 100% of their pre-registered tokens** — but *structural* fidelity splits three ways: **7/13 produce a well-formed GFM grid** (plain, header-colspan, wide-24, headerless, empty-cells, block-in-cell, RTL); **4/13 go ragged** because Markdown has no span concept, so rowspan/colspan/malformed sources emit short rows (t03, t04, t08, t13); and **2/13 are structurally broken** (t05 nested, t12 in-cell pipe). The picture is consistent with the target-format limitation the maintainers themselves track in #1211/#1248: a flat GFM pipe grid cannot represent spans or nesting, so the converter trades structure for content-completeness. Notable good behaviors: **headerless tables get a synthesized blank header row** (so no data is silently promoted into a header and lost — t07), **empty cells are preserved** as empty pipe cells (t09), and **`<caption>` survives** as a text line above the table (t13).

**FINDING-07a [multi-run] [EXCLUSIVE — subtle data-integrity]:** the **rowspan** case (t03) does not just go ragged — it **silently misaligns data**. A `rowspan=2` label ("Fruit") is emitted **once**, and the row beneath it becomes a short 2-column row (`| Banana | 8 |`), so "Banana" lands under the **Group** column instead of **Item**. Content is all present, but a naive `read the 2nd column` consumer gets the wrong value. Issue/SERP search found the *span limitation* documented generically (#1211) but not this specific **column-shift-on-rowspan** behavior on the HTML path. It is the kind of bug that passes a "did the text survive?" check and fails a "is the data in the right column?" check.

**FINDING-08 [multi-run] [KNOWN-ISSUE (class): [#2019](https://github.com/microsoft/markitdown/issues/2019)]:** a literal `|` inside an HTML table cell is **not escaped** (t12: cell text `a | b` becomes two columns; `x || y` becomes three), so a 2-column table emits rows of 2/3/4 columns and any downstream Markdown table parser reads the wrong cell boundaries. **In-cell `*asterisks*` and `` `backticks` `` are** escaped (`\*bold\*`), but pipes are not. Root cause: MarkItDown's HTML path uses the **markdownify** library's default `convert_td`, which does not escape pipes; MarkItDown's `_CustomMarkdownify` subclass overrides links/images/headings but not table cells. The identical bug class is an open BUG for MarkItDown's **CSV** converter (#2019, with several competing fix PRs), but those do not touch the HTML/markdownify path exercised here — so this is a reproduction of the known class, extended to the HTML input and traced to the upstream dependency. **Nested tables** (t05) are the other break: the inner `<table>` is flattened inline, dumping its own pipes and separator row into the parent cell (`| Specs | | Key | Val | | --- | --- | | CPU | 8 core | … |`), a 14-"column" garbage row.

## D. Deep-nesting recursion fallback

Probe: convert HTML consisting of N-deep nested `<div>` wrappers around a heading + paragraph, varying N, recording whether the intentional `RecursionError` fallback fires and whether Markdown structure survives. Script: [deep_convert.py](tests/deep_convert.py) → `run_recursion`; data: [deep_convert.json](artifacts/raw/deep_convert.json) → `recursion`.

| nesting depth | fallback fires? | `## H` heading survives? |
|---:|:--:|:--:|
| 50–450 | no | **yes** (real Markdown) |
| 500 | **yes** | **no** (collapses to plain `H`) |
| 2,000 / 6,000 | yes | no (text kept, structure gone) |

**FINDING-09 [multi-run] [KNOWN-ISSUE (by-design): source `_html_converter.py`]:** HTML nested beyond ~**500 levels** trips markdownify's recursive traversal into a `RecursionError`, which MarkItDown **catches by design** and falls back to BeautifulSoup's iterative `get_text()` — emitting a `"too deeply nested … Falling back to plain-text extraction"` warning. The measured threshold is sharp: at depth **400** the output is real Markdown (`## H` preserved); at depth **500** the same content collapses to plain text (heading marker gone). Content is never lost and the process never crashes, but **all Markdown structure disappears** for pathologically nested pages. The threshold tracks Python's default recursion limit (1000) minus markdownify's per-level frames. This is safer than lxml's silent depth-truncation, but a developer should know that a deeply-nested page yields structure-free text, not an error.

## E. Scale / stress

Each subject run in its **own process** so `ru_maxrss` peak RSS is not contaminated by a prior heavy stage. Timings are a distribution over N runs (min / median / max). Peak-RSS delta = `ru_maxrss` after the first convert minus the pre-convert baseline in that process. Data: [scale_bench_all.json](artifacts/raw/scale_bench_all.json) (merged) and per-subject `scale_bench_*.json`.

| Subject | input | out chars | runs | **median s** | min–max s | **peak RSS Δ** | crashed |
|---|---:|---:|---:|---:|---:|---:|:--:|
| NIST SP 800-53r5 (492-page PDF) | 5.9 MB | 1,625,365 | 3 | **192.5** | 176.7–201.6 | +40 MB | no |
| XLSX 50,000 rows × 8 cols | 2.1 MB | 3,722,955 | 3 | **62.1** | 60.9–100.1 | **+374 MB** | no |
| arXiv 1706.03762 (~15-page PDF) | 2.2 MB | 40,174 | 3 | **12.6** | 9.8–13.5 | +25 MB | no |
| XLSX 200 rows × 64 cols | 46 KB | 120,129 | 5 | **2.9** | 1.7–5.9 | +22 MB | no |

**FINDING-11 [multi-run]:** MarkItDown **did not crash on any scale subject**, but the time cost is dominated by the **PDF path's per-page work, not raw byte size**. The 492-page NIST PDF took a **median of 192.5 s (~3.2 min)** — roughly **0.39 s/page** — because pdfplumber runs word-position form-detection on every page; peak RSS stayed low (+40 MB), so it is CPU-bound, not memory-bound. Even the ~15-page arXiv PDF took **~12.6 s** (not the sub-second the tiny-fixture tests implied), confirming the per-page cost is the driver. The **spreadsheet path is the memory hotspot**: a **2.1 MB / 50k-row XLSX ballooned to +374 MB peak RSS** (and 3.7 M output chars) because the converter loads the whole sheet and builds one large Markdown string. So the practical scale guidance is: **large PDFs → budget minutes of CPU** (or reach for a faster extractor if you don't need form-detection); **large spreadsheets → budget hundreds of MB of RAM**. These are single-machine numbers (macOS arm64 / Python 3.14) and the per-page/per-row constants are implementation- and platform-specific; the *shape* (PDF = CPU-bound and slow, XLSX = memory-heavy, no crashes) is the transferable part.

## Install friction (deep-dive)

**FINDING-01 [multi-run] [KNOWN-ISSUE: [#2179](https://github.com/microsoft/markitdown/issues/2179)]:** `pip install 'markitdown[all]'` **silently backtracks to markitdown 0.0.2** (a 2-year-old release) on Python 3.14 — reproduced live in a clean venv on **2026-07-13** via `pip install --dry-run` (`Would install … markitdown-0.0.2 …`). Pinning exposes the exact cause: `pip install 'markitdown[all]==0.1.6'` errors with

```
ERROR: Could not find a version that satisfies the requirement
       youtube-transcript-api~=1.0.0; extra == "all"
```

The `[all]` extra pins `youtube-transcript-api~=1.0.0` (i.e. `>=1.0.0,<1.1.0`). On current PyPI, every 1.0.x–1.2.2 build of that package is **Python-gated `<3.14`**, so on Python 3.14 pip ignores them, and the only ≥3.14-compatible builds (1.2.3, 1.2.4) fall **outside** the `~=1.0.0` range — the pin is unsatisfiable, so the unpinned command backtracks all the way to 0.0.2 (the last release whose deps it *can* satisfy). This matches upstream issue #2179 verbatim (which notes the standalone `[youtube-transcription]` extra is already unpinned and works). **Correction of the 2026-07-10 draft:** that draft blamed `magika~=0.6.1`; direct resolver output shows magika resolves fine to 0.6.3, and the true blocker is the youtube pin. Logs (live 2026-07-13, clean venv): [pip-install-markitdown-all-dryrun-2026-07-13.log](artifacts/logs/pip-install-markitdown-all-dryrun-2026-07-13.log) (shows `Would install … markitdown-0.0.2`), [pip-install-markitdown-all-pinned-error-2026-07-13.log](artifacts/logs/pip-install-markitdown-all-pinned-error-2026-07-13.log) (the unsatisfiable-pin error); original 2026-07-10 log: [pip-install-markitdown-all.log](artifacts/logs/pip-install-markitdown-all.log).

**The fix** is to pin the version and install extras individually — `pip install 'markitdown==0.1.6'` then `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6'`, each of which resolves cleanly. Only the combined `[all]` bundle carries the stricter youtube pin.

**FINDING-02 [multi-run] [EXCLUSIVE]:** even after a clean install, **`import markitdown` costs ~2.5 s** (measured 2.37 s; median-of-7 subprocess import 3.09 s cold), while constructing the engine (`MarkItDown()`) is only **36 ms**. The cost is at import: `markitdown._markitdown` eagerly imports the **entire converter registry** (`markitdown.converters`, 1.71 s cumulative), which pulls **pandas (779 ms, via the XLSX converter)**, **requests (333 ms)**, **magika (279 ms)**, and **python-pptx (231 ms)** — whether or not you convert any of those formats. Profiled with `python -X importtime`; raw in [importtime.txt](artifacts/logs/importtime.txt). Issue-tracker + SERP search for this returned **zero MarkItDown-specific hits** (only generic "pandas import is slow" threads). For a long-running service the 2.5 s is amortized, but for a CLI invocation or a serverless/Lambda cold start it is a real per-process tax that a "lightweight utility" framing does not lead you to expect.

**FINDING-03 [multi-run] [KNOWN-ISSUE (magika-optional): [#1234](https://github.com/microsoft/markitdown/issues/1234)]:** the **core** install is **161 MB** (empty venv 13 MB → +148 MB), of which **onnxruntime (73 MB) + numpy (34 MB) = 107 MB, i.e. 66% of the entire core footprint**, are dragged in by a single hard dependency: **`magika`** (Google's ML file-type detector, 3.3 MB itself). So a *text converter* ships a **73 MB ONNX inference runtime** in its base install before any document extra is added. With document extras (pandas, lxml, pdfminer/pdfplumber, Pillow, python-pptx, mammoth) the venv reaches **310 MB**. Making magika optional is an open request (#1234). This is much lighter than a browser-download stack, but readers expecting a `pip install`-and-done micro-utility should know an ONNX runtime rides along. Freeze: [pip-freeze.txt](artifacts/logs/pip-freeze.txt).

## Provisional scorecard

**Provisional**, scored **through the lens of a document/HTML→Markdown converter** (crawl/JS dimensions are scored low because the tool genuinely does not do them — which matters for anyone shopping for a "scraper"). Weights mirror the rest of the series for cross-tool comparability; this is not a final article rating and should be reweighted for a "converter" category before publishing.

| Dimension | Weight | Score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **5** | core+HTML works instantly, but `[all]`→0.0.2 (FINDING-01); 161 MB core w/ 73 MB onnxruntime (FINDING-03); ~2.5 s cold import (FINDING-02) |
| Static extraction | 12 | **11** | 4/4 pages full body recall; headings + links faithful; GFM tables clean on well-formed input (FINDING-04) |
| Dynamic extraction | 12 | **1** | no JS rendering at all; out of scope by design |
| Crawl control | 10 | **1** | no crawling, link-following, or pagination |
| Output quality | 14 | **9** | excellent text + Office fidelity + LaTeX equations; but no boilerplate stripping (FINDING-04a), tables break on spans/nesting/pipes (FINDING-07/08), PDF has 0 heading structure (FINDING-06) |
| Scale and reliability | 12 | **7** | no crash on any scale subject; but 492-page PDF ~3.2 min (~0.39 s/page), 50k-row XLSX +374 MB RSS, and scanned PDF → silent empty (FINDING-05, FINDING-11) |
| Developer experience | 10 | **8** | trivial CLI + `convert()` + stdin; clear extras; version/import pitfalls cost points |
| Operations | 8 | **6** | CLI + Python + optional MCP server documented; MCP/Azure/plugins untested here |
| Maintenance and ecosystem | 7 | **7** | active Microsoft repo, recent v0.1.6, huge star base, responsive issue tracker |
| License/compliance fit | 5 | **5** | MIT; pure converter, no stealth/anti-bot surface |
| **Total** | **100** | **60** | provisional material score, not a final article rating |

The low total vs a crawler is **expected and not a knock** — it is an artifact of scoring a converter on a scraper-shaped rubric. On its own turf (HTML/PDF/Office → Markdown), its per-dimension text-fidelity scores are high; its weaknesses are structural (tables, PDF headings) and packaging (footprint, import, `[all]`).

## vs Firecrawl — positioning difference (for the writer)

- **Firecrawl** = a hosted/OSS **scraping+crawling service** that *fetches* pages (renders JS, follows links, crawls a site) and returns LLM-ready Markdown as the output of that pipeline. You point it at a URL; it does the network + rendering + cleaning, and markets **clean main-content** Markdown.
- **MarkItDown** = a local **format converter** with no network-crawler and no JS. You already have the bytes; MarkItDown standardizes them (including PDF/DOCX/XLSX/PPTX) into Markdown, **whole document including nav/footer** (FINDING-04a).
- Overlap is only the *output* ("LLM-ready Markdown"); the *job* differs. Firecrawl answers "get me this website's content"; MarkItDown answers "turn this file/document into Markdown." They are **complementary, not substitutes**. A realistic stack uses **both**: fetch/crawl with Firecrawl (or Thunderbit), then normalize mixed document types (PDFs, decks, spreadsheets) with MarkItDown.
- If "clean article only" matters → a readability/Firecrawl-style tool. If "faithful full-fidelity conversion of arbitrary file types" matters → MarkItDown. If "PDF structure (headings/tables) must survive" matters → **neither is ideal**; that is Docling/Marker territory (FINDING-06).

## Suggested blog material angles

- Frame MarkItDown honestly as **"the last mile" of a scraping pipeline** — the thing that turns fetched HTML/PDF/Office files into LLM-ready Markdown — not a scraper competing on fetching.
- Positive evidence (highest-scoring dimensions): **full body recall + clean HTML/Office table→GFM on well-formed input**, **fast PDF/DOCX text** (arXiv 7/7 probes in ~0.9 s; DOCX equations→LaTeX), and **no silent content loss** on the maintainers' own fixtures.
- Must-tell caveats, each with a number: **keeps boilerplate** (Wikipedia 12.4% chrome lines); **tables break on spans/nesting/in-cell pipes** (2/13 broken, 4/13 ragged, and the rowspan **column-shift** in FINDING-07a); **scanned PDF → silently empty, no OCR** (FINDING-05); **PDF has zero heading structure** (FINDING-06, and it agrees with public benchmarks); the **`[all]`→0.0.2** install trap (FINDING-01) and the **~2.5 s cold import** (FINDING-02).
- The install gotcha is genuinely useful, practical content: **don't `pip install markitdown[all]`** — pin the version + install extras individually.

## Gaps before final blog draft

- **Image OCR / LLM captioning and audio transcription** paths not tested (require OCR engine / model / API keys). The scanned-PDF empty result (FINDING-05) is the *default-install* behavior; the Azure Document Intelligence / plugin OCR paths are untested.
- **Azure Document Intelligence backend** and the **MCP server / plugin system** not tested.
- **Cross-platform**: all numbers are macOS arm64 / Python 3.14.2. The `[all]`→0.0.2 backtrack is **Python-version-dependent** — on a supported Python (≤3.13) the youtube-transcript-api Python gate may not bite, so `[all]` could resolve differently. The import time and footprint are also platform/wheel-specific.
- **YouTube / EPub / ZIP / RSS / Outlook .msg** converters not exercised.
- **Multi-hour soak / true batch** (thousands of files) not run — only the 492-page PDF and 50k-row XLSX single-file scale points.
- No side-by-side numbers vs Firecrawl/Docling on the *same* fixtures yet (only the published-benchmark corroboration in FINDING-06) — produce those once each tool has its own pack on the shared corpus.

## Raw Artifact Index

Scripts (`tests/`): [make_fixtures.py](tests/make_fixtures.py), [deep_convert.py](tests/deep_convert.py), [scale_bench.py](tests/scale_bench.py), [run_markitdown_material_tests.py](tests/run_markitdown_material_tests.py) (the original smoke-test runner, kept for provenance).

Results (`artifacts/raw/`): [deep_convert.json](artifacts/raw/deep_convert.json), [scale_bench_pdf_nist_492p.json](artifacts/raw/scale_bench_pdf_nist_492p.json) / [scale_bench_xlsx_50k.json](artifacts/raw/scale_bench_xlsx_50k.json) / [scale_bench_xlsx_wide64.json](artifacts/raw/scale_bench_xlsx_wide64.json) / [scale_bench_pdf_arxiv.json](artifacts/raw/scale_bench_pdf_arxiv.json), per-case + per-doc Markdown under [md_outputs/](artifacts/raw/md_outputs/), GH/PyPI snapshots (`*_2026-07-13.json`).

Logs (`artifacts/logs/`): [pip-install-markitdown-all.log](artifacts/logs/pip-install-markitdown-all.log), [pip-install-markitdown-core.log](artifacts/logs/pip-install-markitdown-core.log), [pip-freeze.txt](artifacts/logs/pip-freeze.txt), [importtime.txt](artifacts/logs/importtime.txt).

Fixtures (`artifacts/fixtures/`): 4 shared web HTML; `tables/` (13 cases + `manifest.json`); `docs/` (arXiv PDF, Bitcoin PDF, scanned PDF, NIST 492-page PDF, DOCX/XLSX/PPTX, equations.docx, large/wide XLSX).

## Complete Source Index

- [MarkItDown GitHub repository](https://github.com/microsoft/markitdown) — Tier 1 (README, extras, source: `_html_converter.py`, `_pdf_converter.py`, `_markdownify.py`)
- [MarkItDown on PyPI](https://pypi.org/project/markitdown/) — Tier 1 (versions, `requires_python >=3.10`)
- GitHub REST API `repos/microsoft/markitdown` + `/releases/latest` — Tier 1 (metadata snapshot as-of 2026-07-13)
- Upstream issues: [#2179](https://github.com/microsoft/markitdown/issues/2179) (`[all]`/youtube pin), [#2019](https://github.com/microsoft/markitdown/issues/2019) (CSV pipe escaping), [#1268](https://github.com/microsoft/markitdown/issues/1268) (OCR for scanned PDFs), [#1211](https://github.com/microsoft/markitdown/issues/1211) / [#1248](https://github.com/microsoft/markitdown/issues/1248) (HTML/nested table structure), [#1234](https://github.com/microsoft/markitdown/issues/1234) (magika optional)
- Independent benchmarks: [MarkItDown vs Docling vs Marker — danilchenko.dev](https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/), [PDF-to-Markdown deep dive — jimmysong.io](https://jimmysong.io/blog/pdf-to-markdown-open-source-deep-dive/), [READoc benchmark (arXiv 2409.05137)](https://arxiv.org/pdf/2409.05137)
- Fixtures: [Books to Scrape](https://books.toscrape.com/), [Quotes to Scrape](https://quotes.toscrape.com/), [Scrape This Site — Forms](https://www.scrapethissite.com/pages/forms/), [Web scraping — Wikipedia](https://en.wikipedia.org/wiki/Web_scraping), [arXiv 1706.03762](https://arxiv.org/pdf/1706.03762), [Bitcoin whitepaper](https://bitcoin.org/bitcoin.pdf), [NIST SP 800-53r5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf); DOCX/XLSX/PPTX from [markitdown test_files](https://github.com/microsoft/markitdown/tree/main/packages/markitdown/tests/test_files) (MIT)
