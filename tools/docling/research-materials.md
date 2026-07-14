# Docling Review Research Materials

Date: 2026-07-10 (HTML smoke pass) · **deepened 2026-07-13 with the PDF / TableFormer / OCR path under methodology v3**

Status: source material for a future Thunderbit blog article. This is **not** a final blog draft and should not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **Docling** (`docling-project/docling`, from IBM Research, now an LF AI & Data Foundation project). Docling is a **document-conversion / document-understanding** toolkit — "get your documents ready for gen AI" — not a web crawler. It parses PDF, DOCX, PPTX, XLSX, HTML, images and more into a unified `DoclingDocument` and exports Markdown / HTML / JSON. Its headline capability is the **PDF/image path**: an RT-DETR layout model + the **TableFormer** table-structure model (+ optional VLM), which recover page layout, reading order, and table structure.

The earlier version of this pack tested **only the HTML path** and explicitly deferred Docling's actual main event to Gaps. This version closes that gap. It contains, all measured on one machine:

- an **install-weight** breakdown and a **first-run model-download measurement** (the friction the HTML-only pass could not see);
- a **TableFormer cell-fidelity** benchmark on **7 synthetic PDFs with machine-generated ground truth** (bordered / borderless / colspan header / rowspan / span+borderless / blank-column financials / wide-12-col), scored cell-by-cell with no human judgement;
- a **scripted controlled A/B** ([pdf_sparse_page_ab.py](tests/pdf_sparse_page_ab.py)) isolating *why* two of those tables failed (it is not what it looks like — see FINDING-D3);
- a **real-PDF** pass (two arXiv papers, 9pp + 15pp: reading order, table detection, per-page timing);
- a **scanned/OCR** pass (two genuine scanned PDFs with a **measured 0-character text layer** via `pypdfium2`, recorded in the artifact) exercising the default OCR engine;
- a **multi-format** pass (DOCX / XLSX / PPTX with ground-truth probes + a **lossless-JSON round-trip** check);
- an **HTML boilerplate-residue** quantification (Docling does no main-content extraction — how much chrome survives, as a number);
- and README/model-card **claim verification** against the official TEDS figures.

All measurements are on macOS arm64 / Python 3.14.2 and reproducible from the scripts in `tests/`. Failures are recorded as failures. Untested areas are in **Gaps**. Every number in `artifacts/raw/docling-deep-summary.json` is computed by `tests/build_summary.py` from run outputs, not hand-written — including the on-disk model size (`hf_on_disk_mib`), which is the `du`-matching symlink-de-duplicated figure; the raw `os.walk` field that double-counts snapshot symlinks is carried alongside it and explicitly labeled, so the headline is never the doubled number.

### How to read the findings

Findings are numbered `FINDING-DN` (D = the deep PDF-path round) and carry two tags:

- a **confidence** tag — `[reproduced]` (held across a re-run / a controlled A/B / a ≥3-run warm distribution), `[single-observation]` (measured once — e.g. the download-bound 224 s first conversion and the CPU per-page OCR/real-PDF timings), or `[hypothesis]` (mechanism proposed, no attribution experiment). Warm-conversion timings for the cheap fixtures carry a 3-run spread ([warm_timing_repeats.json](artifacts/raw/warm_timing_repeats.json)); the two ~90-135 s real arXiv PDFs and the one-shot model download are **not** repeated and stay `[single-observation]`. And
- a **novelty** tag from the pre-registration search (§Novelty verification) — `[KNOWN-ISSUE: link]`, `[DOCUMENTED]`, or `[NO-PUBLIC-HIT]`.

No finding is dressed up with self-evaluative adjectives; novelty is decided by the search table, not by adjective.

## Source Snapshot

Docling's tagline is literally *"Get your documents ready for gen AI."* It converts many formats into a unified `DoclingDocument` and exports Markdown, HTML, DocTags, and lossless JSON. Source: [Docling GitHub README](https://github.com/docling-project/docling) (Tier 1). License is **MIT** (individual model licenses vary).

Point-in-time repo metadata fetched from the GitHub API + PyPI on **2026-07-13** (refresh within 48h of publication):

| Field | Value |
|---|---|
| Repo | [docling-project/docling](https://github.com/docling-project/docling) |
| Stars | **63,069** |
| Forks | **4,449** |
| Open issues | **938** |
| License | **MIT** (model licenses vary) |
| Default branch | **main** |
| Created | **2024-07-09** |
| Last push (activity) | **2026-07-13** (same-day as snapshot) |
| Latest GitHub release | **v2.112.0**, published **2026-07-11** |
| PyPI version tested | **2.111.0** (latest is 2.112.0; tested one minor behind) |
| PyPI Python requirement | **`<4.0,>=3.10`** |
| Governance | LF AI & Data Foundation (originated at IBM Research Zurich) |

Raw snapshots: [github_repo_snapshot_2026-07-13.json](artifacts/raw/github_repo_snapshot_2026-07-13.json), [github_release_snapshot_2026-07-13.json](artifacts/raw/github_release_snapshot_2026-07-13.json), [pypi_snapshot_2026-07-13.json](artifacts/raw/pypi_snapshot_2026-07-13.json). The repo is **extremely active** (938 open issues, pushed the same day as the snapshot, weekly-ish releases) — treat any issue-count / release number as volatile.

### Packaging nuance worth a callout (`docling` vs `docling-slim`)

Since our first pass, the project shipped **`docling-slim`** (on PyPI, v2.112.0, *"Modular version of the Docling package"*) — a ~50 MB core that lets you `pip install docling-slim[format-html]` for HTML **without** torch. So the "1.3 GB install even for HTML" friction below is real for the **default `docling` metapackage** but **is now addressable** by choosing `docling-slim`. The article must not present the heavy install as an unaddressed flaw — the modular fix exists (tracking issue [#2535](https://github.com/docling-project/docling/issues/2535), lightweight-install discussion [#2393](https://github.com/docling-project/docling/issues/2393)). We tested the default `docling` package because that is what `pip install docling` still gives you.

## Novelty verification (pre-registration search)

Before write-up, each candidate was searched against three sources: the Docling GitHub issue tracker (via `gh`), the official docs / model card, and general web results. The query strings and per-candidate outcomes are persisted in [novelty_search.json](artifacts/raw/novelty_search.json) (so the "zero-hit" claims are re-checkable; issue existence/open-closed state is re-verified at fresh-clone time — see Gaps). The load-bearing links:

| Candidate finding | Verdict | Prior record |
|---|---|---|
| Heavy torch/opencv/transformers deps for HTML-only use (1.3 GB) | **KNOWN-ISSUE + partly solved** | [#2393](https://github.com/docling-project/docling/issues/2393) (lightweight install, open), [#3100](https://github.com/docling-project/docling/issues/3100) (a CPU-only box pulled **7.4 GB** via nvidia wheels), and **`docling-slim` already ships** ([#2535](https://github.com/docling-project/docling/issues/2535)). Our contribution is the **measured** on-disk breakdown, not the complaint. |
| `import docling` has no `docling.__version__` (AttributeError) | **KNOWN-ISSUE** | [#3733](https://github.com/docling-project/docling/issues/3733) (open, 2026-07-02, exact repro). We reproduce + give the `importlib.metadata` workaround. |
| HTML runs a BeautifulSoup backend, **not** the layout/TableFormer models | **DOCUMENTED (architecture), not spelled out in one place** | [architecture docs](https://docling-project.github.io/docling/concepts/architecture/) map format→backend→pipeline; no official page states plainly "HTML never touches TableFormer." We confirm it by measurement. |
| No main-content/boilerplate extraction (keeps nav/footer) | **KNOWN-ISSUE** | HTML: [#1865](https://github.com/docling-project/docling/issues/1865) (closed, "Nav and Footer not excluded"), [#1930](https://github.com/docling-project/docling/issues/1930) (open). Our contribution: a **residue percentage** on real pages. |
| TableFormer misses **borderless** tables | **KNOWN-ISSUE (conditional)** | [#3749](https://github.com/docling-project/docling/issues/3749) (open, 2026-07-03, "fails on borderless tables with whitespace-delimited columns"), [#3495](https://github.com/docling-project/docling/issues/3495) (borderless double-detected as Table+Picture). **Our data qualifies it**: a borderless table with a header rule + aligned columns was recovered perfectly (T2). |
| TableFormer mishandles **merged / spanning cells** | **KNOWN-ISSUE** | [#3698](https://github.com/docling-project/docling/issues/3698) (open, 2026-06-25, "V1 & V2 mishandling merged rows and columns"), [#207](https://github.com/docling-project/docling/issues/207). **Our data qualifies it**: colspan headers and rowspan labels were flattened *correctly* to GFM when the table was detected (T3/T4b) — see FINDING-D2. |
| Isolated small table on a sparse page classified as a **Picture** and dropped | **KNOWN-ISSUE (adjacent)** | [#3495](https://github.com/docling-project/docling/issues/3495) is the closest (table detected as Table **and** Picture). The **page-sparsity trigger** we isolate in FINDING-D3 (same table drops when alone, converts when surrounded by text) is not stated in that issue. |
| First-run PDF model **download size** in MB | **NO-PUBLIC-HIT for the byte size** | The official [model catalog](https://docling-project.github.io/docling/usage/model_catalog/) names models but publishes **no MB/GB**. Our **~506 MiB on-disk HF models + ~40 MB first-run RapidOCR download (~75.6 MB resident)** measurement is an undocumented number. Accuracy (TEDS) *is* published (below). |
| Default OCR engine is now **RapidOCR** (not EasyOCR) | **DOCUMENTED but widely mis-stated** | Current `pyproject.toml` bundles `feat-ocr-rapidocr` in core; EasyOCR is an extra ([#3227](https://github.com/docling-project/docling/issues/3227)). Most existing blogs/FAQ still say "EasyOCR default" — **stale**. We confirm RapidOCR by watching the download. |
| `import docling` ≈ 30 s cold (torch/transformers) | **NO-PUBLIC-HIT for Docling specifically** | No Docling issue targets import wall-clock; the ~15-45 s cost is a known [transformers](https://github.com/huggingface/transformers/issues/16863) property. Undocumented *as a Docling fact*; don't imply the transformers slowness itself is undiscovered. |

**Consequence for the writer:** almost every *behavioral* finding here is a **reproduction + quantification of an already-open issue**, and must be framed that way with the link. The undocumented numbers are (a) the **measured model-download size**, (b) the **cell-level fidelity table** with the page-sparsity trigger, and (c) the **Docling-specific cold-import time**. Frame those as "measured, not previously published," not as "bugs nobody knew about."

## Official Capability Claims to Verify

From the README / model card (Tier 1):

- **"Advanced PDF understanding incl. page layout, reading order, table structure, code, formulas…"** — the PDF/image path (ML models). Tested here (§PDF, §Tables, §OCR).
- **Multi-format** parsing (PDF/DOCX/PPTX/XLSX/HTML/EPUB/audio/images) — tested DOCX/XLSX/PPTX/HTML/PDF/scans here.
- **Unified `DoclingDocument`** + **lossless JSON** export — tested via round-trip (§Multi-format).
- **Official TableFormer accuracy** (HF [model card](https://huggingface.co/ds4sd/docling-models)): **TEDS simple 95.4 / complex 90.1 / all 93.6**, above Camelot (73.0) and EDD (88.3). Layout model = **RT-DETR**. We compare our own cell-recall to this in §Tables.

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (arm64, Apple Silicon), **CPU-only** (no CUDA/MPS forced) |
| Python | **3.14.2** |
| Docling | **2.111.0** (docling-core 2.86.0, docling-ibm-models 3.13.3, docling-parse 7.7.0) |
| ML stack | torch 2.13.0, transformers 5.8.1, opencv-python 5.0.0.93, rapidocr 3.9.1 |
| Install method | fresh dedicated venv + `pip install docling` (the default metapackage) |
| HTML backend (per architecture docs) | `HTMLDocumentBackend` + `SimplePipeline` (BeautifulSoup-based, **no ML model**) — from the format→backend→pipeline map; confirmed indirectly by the HTML path pulling no model download and by the boilerplate residue (FINDING-D6), not by a logged backend-name assertion |
| PDF pipeline (observed via model download) | layout (`docling-layout-heron`) + TableFormer (`docling-models`) + RapidOCR — the three model sets whose weights downloaded on first PDF run (`pdf_coldstart.log`) |
| Scripts | `tests/` (see Raw Artifact Index) |
| Summary artifact | [docling-deep-summary.json](artifacts/raw/docling-deep-summary.json) (generated, not hand-authored) |

### Setup notes (the real friction, now measured)

- **`pip install docling` succeeded on Python 3.14.2** in a fresh venv; the resulting venv is **1.3 GB**. Docling pulls the full ML stack as **hard dependencies** even to convert HTML:

  | Dependency | On-disk size (MiB, `du`) |
  |---|---:|
  | torch (2.13.0) | **536** |
  | opencv (cv2) | **119** |
  | transformers (5.8.1) | **101** |
  | scipy | **99** |
  | sympy | **76** |
  | pandas | **72** |
  | rapidocr (+ bundled models) | **75.6** |
  | docling_parse | **30** |

  (Sizes are `du` MiB — 1024-based; the RM's other model figures are the same unit. The RapidOCR row is the full `site-packages/rapidocr/` dir = 73,840 KiB = 75.6 MB decimal / 72.1 MiB, of which the model weights are ~70 MiB — corrected from an earlier "~100 MB".) For an HTML-only user this is far heavier than a pure-Python converter — but see the `docling-slim` nuance above; the heaviness is now opt-out.

- **`docling.__version__` raises `AttributeError`.** `import docling; docling.__version__` → `AttributeError: module 'docling' has no attribute '__version__'`. The working probe is `importlib.metadata.version("docling")` → `'2.111.0'`. **FINDING-D0 [reproduced] [KNOWN-ISSUE: [#3733](https://github.com/docling-project/docling/issues/3733)]** — a small DX papercut, open upstream since 2026-07-02. *(This corrects the earlier pack, which recorded the version as "unknown" — it is not unknown, the module attribute is simply missing; use `importlib.metadata`.)*

## PDF-path first run — model download + cold cost (the headline friction)

Measured with a **fresh, isolated HF cache** (`HF_HOME` pointed at an empty dir so the download is cleanly attributable; the system cache was untouched). Script: [pdf_coldstart_download.py](tests/pdf_coldstart_download.py) → [pdf_coldstart_download.json](artifacts/raw/pdf_coldstart_download.json).

| Phase | Measurement |
|---|---:|
| `import docling` (warm disk, cold process) | ~5 s here (torch/transformers already imported once); ~30 s on a truly cold first import (earlier pass, `first-html-smoke.log`) |
| `DocumentConverter()` init | 0.018 s |
| **First PDF conversion (incl. model download)** | **223.9 s** |
| Model files → **HF cache** (`docling-models` TableFormer + `docling-layout-heron`) | **~506 MiB on disk** (342 MiB TableFormer + 164 MiB layout; `du`-verified) |
| RapidOCR weights → **venv site-packages** | **~40 MB downloaded at first run** (PP-OCRv4), **~75.6 MB resident** total (bypasses `HF_HOME`) |
| **Second PDF conversion (warm)** | **0.55 s** |

**A note on the "1060 MB" the script prints (measurement reconciliation).** The script's `model_download_mb` field reads **1060.2** — do not use that as the footprint. It comes from `os.walk` + `os.path.getsize` over `HF_HOME`, and `os.path.getsize` **follows symlinks**: the HuggingFace cache stores each model file once under `blobs/` and re-exposes it as a `snapshots/` symlink, so the walk counts the 14 model files **twice**. Skipping symlinks (or `du -sh HF_HOME/hub`) gives the real on-disk figure: **530 MB decimal = 505.5 MiB** (blobs-only 505.4 MiB). This is **not** an hf-xet transfer-cache artifact (the `xet/` staging dir is ~0.2 MB). The reconciliation and both instruments are recorded in [pdf_coldstart_download.json](artifacts/raw/pdf_coldstart_download.json) (`durable_hub_mib` vs `walk_follows_symlinks_mb`).

**FINDING-D1 [size reproduced / download timing single-observation] [NO-PUBLIC-HIT for the size]:** the PDF path's first run puts **~506 MiB of layout + TableFormer models on disk** (in the HuggingFace cache) plus RapidOCR weights in `site-packages`, and the **first conversion takes ~224 s** almost entirely because of that download; the **second conversion is ~0.55 s** (the warm-conversion side is corroborated by a 3-run distribution in [warm_timing_repeats.json](artifacts/raw/warm_timing_repeats.json); the 224 s first-download is single-observation and connection-dependent by nature). Three things a reader benchmarking Docling must know:

1. **Report download bytes and on-disk bytes separately.** On-disk HF model footprint is **~506 MiB** (`du`-verified, symlink-de-duplicated). RapidOCR **downloaded ~40 MB at first PDF run** (PP-OCRv4 `.pth` det/cls/rec + keys, summed from `pdf_coldstart.log`) and sits at **~75.6 MB resident** once the PP-OCRv6 `.onnx` files that arrive with the `pip install` are counted. So a fair "first-run download" is roughly **~506 MiB (HF) + ~40 MB (RapidOCR)**; a fair "resident model weight" is **~506 MiB + ~75.6 MB**. (Earlier drafts summed a symlink-doubled 1060 and a "~70 MB" resident into a "~576 MB" headline; both inputs were mis-scoped.)
2. **The weights split across two locations, on two schedules.** The layout + TableFormer models honor `HF_HOME` and download on the **first PDF conversion**; **RapidOCR's models do not honor `HF_HOME`** — they land in `…/site-packages/rapidocr/models/`. Per the download log, only the **PP-OCRv4 `.pth`** generation was fetched at first-run; the **PP-OCRv6 `.onnx`** files were already present with mtimes matching the `pip install` (they ship/pre-stage with the package), so "first run fetched two OCR generations" is **not** what the log shows. Anyone pre-baking or air-gapping a Docling image still has to handle both caches.
3. **No official page publishes the size.** The model catalog lists model names but no bytes (see Novelty). So "~506 MiB HF models on disk, ~224 s first PDF" is a measured, previously-unpublished figure. *(Single machine / warm pip cache / home-broadband; the 224 s is download-bound and varies with connection — the on-disk size is the stable part.)*

## Table fidelity — TableFormer on synthetic PDFs with known ground truth (the headline claim)

Seven table PDFs were **generated by us** ([gen_pdf_fixtures.py](tests/gen_pdf_fixtures.py)) so the ground-truth cell matrix is known by construction; each has a sidecar `*.groundtruth.json`. Docling converts each; [pdf_table_fidelity.py](tests/pdf_table_fidelity.py) parses the emitted Markdown table and scores it **cell-by-cell** against the truth. Two recall metrics are recorded and they are **not** the same: `cell_recall` = fraction of ground-truth non-empty values present **anywhere in the detected table**; `inrow_rate` = fraction present **in the correct row index**. (An earlier draft's prose conflated the two — it described `cell_recall` as "in the correct row," which is actually `inrow_rate`; the script computes both, see `pdf_table_fidelity.py:104-107`.) Results: [pdf_table_fidelity.json](artifacts/raw/pdf_table_fidelity.json).

| Table (stress) | Detected | Dims match | Cell recall | In-row rate | Convert s | Note |
|---|:--:|:--:|---:|---:|---:|---|
| **T1** simple **bordered** grid (5×8), alone on page | **No** | — | 0.0 | — | 12.1 | classified as `<!-- image -->`, all cells dropped |
| **T2** **borderless** (only a header rule) | Yes | Yes | **1.00** | **1.00** | 2.5 | perfect, exact grid |
| **T3** merged 2-level **colspan** header | Yes | Yes | **1.00** | **0.97** | 1.9 | all values found; a "Region" header value lands off its original row (shift) |
| **T4** merged **rowspan** row-label, alone on page | **No** | — | 0.0 | — | 0.5 | classified as `<!-- image -->` |
| **T5** colspan header **+ borderless** | Yes | Yes | **1.00** | **0.97** | 2.0 | all values found; same header-row shift as T3 |
| **T6** financials, **blank column**, right-aligned | Yes | Yes | **1.00** | **1.00** | 2.1 | blank "Adj." column preserved, not shifted |
| **T7** **wide** 12-column grid | Yes | Yes | **1.00** | **1.00** | 2.8 | no column shift on a wide table |

**FINDING-D2 [reproduced] [KNOWN-ISSUE qualified: [#3698](https://github.com/docling-project/docling/issues/3698) / [#3749](https://github.com/docling-project/docling/issues/3749)]:** on the **5 tables Docling detected, every ground-truth value was recovered (cell recall 1.00)**; on **3 of those 5 (T2/T6/T7) every value also landed in its correct row (in-row 1.00)**, while on the two 2-level-header cases (T3/T5) **one header value shifts off its original row** — all values are present but in-row drops to **0.97**. The hard structural cases still come through: the **2-level colspan header** (T3: "Q1 2026" repeated over its two spanned columns, occurrences=2, the correct way to flatten a colspan into GFM), a **borderless** grid (T2), a **12-column** grid (T7), and a **fully blank column** (T6, preserved as empty cells, not dropped or shifted). This is consistent with the official TableFormer TEDS (93.6 all-tables) and, on these fixtures, a real strength — **when a table is detected, its values come through; on multi-level headers the row assignment can slip by one.** *(Scope: 7 synthetic tables, clean digital PDFs, single machine — not a TEDS-scale corpus; a targeted structural probe, not an accuracy benchmark.)*

The **merged-cell** picture deserves care against the open issue [#3698](https://github.com/docling-project/docling/issues/3698) ("V1 & V2 mishandling merged rows/columns"): on **our** colspan (T3/T5) and rowspan (T4b, below) fixtures the values were flattened correctly, with the T3/T5 multi-level header inducing the one-row shift noted above. #3698's failing cases involve more irregular multi-row/multi-column merges and multi-page tables ([#3553](https://github.com/docling-project/docling/issues/3553)); our fixtures are the *simple* end of merging. So the accurate statement is **"simple colspan/rowspan values recovered here (multi-level headers can shift a row); complex/irregular merges are a documented open problem,"** not "merged cells work" or "merged cells are broken."

### FINDING-D3 — the "failure" is a layout-model image mis-classification of *isolated* tables, not a table-parsing weakness

T1 (a perfectly ordinary bordered grid) and T4 (a rowspan table) were **not detected at all** — Docling emitted `<!-- image -->` and dropped every cell. Before calling this a table weakness, we ruled out the fixture and isolated the trigger with a scripted A/B ([pdf_sparse_page_ab.py](tests/pdf_sparse_page_ab.py) → [pdf_sparse_page_ab.json](artifacts/raw/pdf_sparse_page_ab.json); every value below is a field in that artifact):

- **The text layer is intact.** `pypdfium2` reads **327 chars** of T1's text layer (**221** for T4) — these are real digital PDFs, not images (`isolated.text_layer_chars`).
- **`do_ocr=False` doesn't help** — the isolated tables still drop (`isolated_do_ocr_false.n_doc_tables == 0` for both), so it is not an OCR mis-route.
- **Inspecting the `DoclingDocument`:** for the isolated T1 and T4, `len(doc.tables) == 0`, `len(doc.pictures) == 1` — the **layout model classified the whole table region as a Picture** (`isolated_classified_as_picture: true`).
- **Controlled A/B (the decisive test):** the *same* T1 and T4 tables, re-rendered **surrounded by ordinary body paragraphs** (`table_t1b_grid_in_context` / `table_t4b_rowspan_in_context`, generated by the same `gen_pdf_fixtures.py`), **both convert correctly** — `len(doc.tables) == 1`, GFM tables emitted (`drops_when_isolated_converts_in_context: true`), and **T4b's rowspan "North" is repeated across its 3 rows** (`in_context_rowspan_repeats: 3`).

**FINDING-D3 [reproduced] [NO-PUBLIC-HIT for the page-sparsity trigger; KNOWN-ISSUE adjacent: [#3495](https://github.com/docling-project/docling/issues/3495)]:** Docling's RT-DETR **layout model uses page context**, and a **small table alone on an otherwise near-empty page** is liable to be classified as a **Picture** and dropped **with no error** — while the identical table **surrounded by text converts perfectly**. This is the real caveat, and it is easy to hit if you feed Docling **one-table-per-page** PDFs (invoices, spec sheets, cropped exports). It is adjacent to the open "table detected as Table *and* Picture" issue #3495, but the **page-sparsity trigger** — same table, drops when isolated, converts when embedded — is the part we add (searched, no public hit: [novelty_search.json](artifacts/raw/novelty_search.json)). *(The article should show the A/B: it reframes a scary "dropped my whole table" from "TableFormer is bad" to "give the layout model page context, or post-check `doc.tables`.")*

## Real PDFs — reading order, tables, per-page timing

Two real born-digital academic PDFs (2-column, tables, formulas). Script: [pdf_real_and_scanned.py](tests/pdf_real_and_scanned.py) → [pdf_real_and_scanned.json](artifacts/raw/pdf_real_and_scanned.json). Full Markdown: [real_arxiv_docling_report.md](artifacts/raw/real_arxiv_docling_report.md), [real_arxiv_attention.md](artifacts/raw/real_arxiv_attention.md).

| Real PDF | Pages | Convert s | **s/page** | MD tables | Content probes | Section order recovered |
|---|---:|---:|---:|---:|:--:|:--:|
| arXiv 2408.09869 (the Docling report) | 9 | 134.5 | **14.95** | 3 | **5/5** | 3/4 markers, **in order** (Abstract→Introduction→References; "Related Work" heading not matched) |
| arXiv 1706.03762 (Attention Is All You Need) | 15 | 89.9 | **5.99** | 4 | **5/5** | **in order, 5/5** (Abstract→Introduction→Background→Conclusion→References) |

**FINDING-D7 [single-observation] [DOCUMENTED capability, timing NO-PUBLIC-HIT]:** on real 2-column academic PDFs, Docling recovers **reading order correctly** — on the 15-page Attention paper all five section markers (Abstract → Introduction → Background → Conclusion → References) appear **in document order** in the linearized Markdown despite the two-column layout, and every content probe (Transformer, encoder, BLEU, multi-head) is present; the famous multi-column results tables register as **4 detected tables**. This is genuine reading-order / column-merge recovery — the core RAG-chunking value. **Per-page time is CPU-bound and content-dependent, not page-count-dependent:** the *denser* 9-page report (more tables/figures per page → more TableFormer/layout inference) ran **14.95 s/page**, *slower* per page than the 15-page paper at **5.99 s/page**. So "seconds per page" on CPU is driven by how much *structure* is on each page, not by length. *(Single run, CPU-only macOS arm64; GPU would cut these materially — this is a ceiling, not a typical production number. Reading-order "in order" is a marker-ordering signal, not a full linearization audit.)*

## Scanned / OCR — the default engine on genuine image PDFs

Two **scanned** PDFs with a **measured 0-character text layer** (`pypdfium2`, `text_layer_chars: 0` in [pdf_real_and_scanned.json](artifacts/raw/pdf_real_and_scanned.json); the two born-digital arXiv PDFs in the same run measure 48,969 and 40,407 chars, so the probe discriminates) exercise Docling's default OCR.

- **`ocr_test.pdf` (1 page, `text_layer_chars: 0`):** Docling's OCR recovered the full sentence — *"Docling bundles PDF document conversion to JSON and Markdown in an easy self contained package"* — cleanly, in **14.3 s** on CPU. Output: [real_ocr_test.md](artifacts/raw/real_ocr_test.md).
- **`nemotron_multipage.pdf` (4 pages, `text_layer_chars: 0`):** OCR fired on all four pages (**70.1 s total, 17.5 s/page**), emitting the repeated test sentence across pages (this Docling test fixture is intentionally the same sentence per page). Output: [real_nemotron_multipage.md](artifacts/raw/real_nemotron_multipage.md).

Because both scanned PDFs (from Docling's own `tests/data/scanned`) measure a **0-character text layer**, any recovered text is OCR output, not a hidden text layer.

**FINDING-D4 [reproduced] [DOCUMENTED but widely mis-stated]:** on a real scanned PDF with **no text layer**, Docling's **default OCR (RapidOCR, not EasyOCR)** fired automatically and recovered the text correctly. The engine identity matters: most existing write-ups (and older Docling FAQ text) say EasyOCR is the default; as of the tested build the default is **RapidOCR** (confirmed by watching the PP-OCRv4 weights download at first run in `pdf_coldstart.log` — note only the v4 `.pth` generation was fetched then; the PP-OCRv6 `.onnx` files ship with the pip install, see FINDING-D1). RapidOCR speed complaints are open upstream ([#1143](https://github.com/docling-project/docling/issues/1143)); our small scans were fast, but OCR is the slow path at scale.

## Multi-format — DOCX / XLSX / PPTX + lossless-JSON round-trip

Generated with known content + ground-truth probes ([gen_doc_fixtures.py](tests/gen_doc_fixtures.py)); scored by [multiformat_docs.py](tests/multiformat_docs.py) → [multiformat_docs.json](artifacts/raw/multiformat_docs.json). Each file is converted to Markdown (probes must appear) **and** exported via `export_to_dict()` (probes must survive the JSON — the lossless claim).

| File | Convert s | All MD probes found | Tables in MD | **All probes survive JSON** |
|---|---:|:--:|---:|:--:|
| `report.docx` (headings + merged-"Total" table + bullets) | 0.137 | **Yes (7/7)** | 1 | **Yes** |
| `workbook.xlsx` (2 sheets, blank column) | 0.016 | **Yes (6/6)** | 2 | **Yes** |
| `deck.pptx` (3 slides, bullets + table) | 0.038 | **Yes (6/6)** | 1 | **Yes** |

**FINDING-D5 [reproduced] [DOCUMENTED]:** the "unified multi-format" claim holds on DOCX/XLSX/PPTX — all content probes were found in the Markdown, tables were recovered (including a DOCX table with a merged "Total" row and both XLSX sheets), and **every probe also survived the `export_to_dict()` JSON**, supporting the lossless-`DoclingDocument` claim on these inputs. These formats go through **format-native backends** (not the ML models), so they are fast (tens of ms) and offline. *(Scope: one file per format, small/clean — substantiates breadth, not a stress test of pathological Office files.)*

## HTML — boilerplate residue quantified (raw conversion, no main-content extraction)

Docling converts the **whole** HTML document; it does **not** do readability-style main-content extraction. We measured how much site chrome survives ([html_boilerplate_quant.py](tests/html_boilerplate_quant.py) → [html_boilerplate_quant.json](artifacts/raw/html_boilerplate_quant.json)) by counting boilerplate-marker lines (nav/cookie/footer/legal/TOC) in Docling's own output.

| Page | Non-blank MD lines | Boilerplate-marker lines | % boilerplate | Real article starts at line |
|---|---:|---:|---:|---:|
| Wikipedia "Web scraping" | 255 | **34** | **13.3%** | **28** (chrome leads the doc) |
| scrapethissite/forms | 63 | 1 | 1.6% | — |
| books.toscrape | 65 | 0 | 0.0% | — |
| quotes.toscrape | 35 | 0 | 0.0% | — |

**FINDING-D6 [reproduced] [KNOWN-ISSUE: [#1865](https://github.com/docling-project/docling/issues/1865), [#1930](https://github.com/docling-project/docling/issues/1930)]:** on a chrome-heavy page (Wikipedia) **~13% of Docling's Markdown lines are nav/TOC/footer boilerplate and the real article doesn't begin until line 28** — the output *leads* with "move to sidebar / Contents / Toggle the table of contents" and *ends* with "CS1 maint… / Search Wikipedia." On clean content pages (books/quotes) there is ~0% chrome, so this is a **template-chrome** problem, not a per-page tax. Docling gives **faithful full-document Markdown**, not **clean main-article extraction** — the single most important caveat for "which tool for RAG." Upstream tracks HTML nav/footer furniture (#1865 closed, #1930 open); *note the PDF path does attempt header/footer furniture classification, so "no boilerplate removal at all" is too strong for PDF — it is the HTML backend specifically.*

## Positioning vs Firecrawl

The anchor tool for this category (LLM-ready Markdown) is Firecrawl. The comparison below is a **documentation-level positioning table, not a same-bench measurement** — Firecrawl was **not run on this machine or on these fixtures**. Only the **Docling** column's italicized figures are measured here (they carry the FINDING references); the Firecrawl column is from its public docs/positioning. A same-fixtures head-to-head (Docling vs MarkItDown vs Marker vs Firecrawl) does not appear to exist publicly and is the acknowledged Gap / natural next pack (see Gaps). Per methodology v3 Part 5 §17, treat the absence of a same-bench moat number as a known limitation of this pack, not a settled competitive claim.

| Axis | Firecrawl (per its docs) | Docling (measured here) |
|---|---|---|
| Core job | **Crawl + scrape the live web** → Markdown | **Convert a document you already have** → Markdown/JSON |
| Fetching / JS render / anti-bot | Yes (hosted browser) | **No** — you supply the file/HTML/PDF |
| Main-content extraction | Yes (`onlyMainContent`) | **No** — faithful full-document (13% chrome on Wikipedia, FINDING-D6) |
| **PDF table structure (ML)** | limited | **Yes — TableFormer** (TEDS 93.6 official; *cell-recall 1.00, in-row 0.97-1.00 on our detected fixtures*) |
| Scanned PDF / OCR | limited | **Yes — RapidOCR** by default (recovered a 0-text-layer scan, FINDING-D4) |
| Format breadth | web pages | **PDF/DOCX/PPTX/XLSX/HTML/EPUB/images/audio** |
| Deployment | hosted API (+ self-host) | **local pip library**, offline, no API key |
| Setup weight | API key / light client | **1.3 GB** default install + **~506 MiB** on-disk HF models (+~40 MB first-run RapidOCR) (or `docling-slim`) |
| License | AGPL-ish / commercial (verify in Firecrawl pack) | **MIT** |

**One-line takeaway:** Firecrawl is the tool when the data is *on the live web and needs crawling/JS/main-content cleanup*; Docling is the tool when you *already hold the document* — **especially PDFs, scans, and table-heavy Office files** — and want a faithful, offline, structure-preserving Markdown/JSON conversion with genuine table + OCR understanding. **Complements, not substitutes**: a realistic pipeline crawls with Firecrawl and converts documents with Docling.

## Key Findings for the Writer

1. **FINDING-D1** — PDF path first run puts **~506 MiB of HF models on disk** (342 MiB TableFormer + 164 MiB layout; `du`-verified) + **~40 MB RapidOCR downloaded** into site-packages (**two caches**, ~75.6 MB RapidOCR resident); first PDF **~224 s** (download-bound), warm **~0.55 s**. The script's raw 1060 MB is a symlink-double-count — see the reconciliation. Size is **unpublished** officially. (§first run)
2. **FINDING-D2** — on the 5 detected tables **cell recall 1.00** (every value found) across bordered/borderless/colspan-header/rowspan/blank-column/12-col; **in-row 1.00 on 3 of 5**, dropping to **0.97 on the two multi-level-header tables (T3/T5)** where one header value shifts a row. Matches the official TEDS 93.6 story on these fixtures. (§Tables)
3. **FINDING-D3** — a **small table alone on a sparse page is classified as a Picture and silently dropped**; the *identical table surrounded by text converts* (scripted controlled A/B, [pdf_sparse_page_ab.json](artifacts/raw/pdf_sparse_page_ab.json): isolated tables=0/pictures=1, in-context tables=1, drop survives `do_ocr=False`, rowspan repeats=3). Reframes a scary "dropped my table" as a layout-context effect; post-check `doc.tables`. Page-sparsity trigger is the added part (no public hit); adjacent to #3495. (§Tables)
4. **FINDING-D4** — **default OCR is RapidOCR, not EasyOCR** (common mistake); recovered a genuine 0-text-layer scan cleanly. (§OCR)
5. **FINDING-D5** — DOCX/XLSX/PPTX all convert, tables recovered, and **probes survive the JSON round-trip** (lossless claim holds on these inputs). (§Multi-format)
6. **FINDING-D6** — HTML is **raw full-document** conversion: **~13% boilerplate lines on Wikipedia**, article starts line 28; ~0% on clean pages. Not main-content extraction. Known issue #1865/#1930. (§HTML)
7. **FINDING-D0** — `docling.__version__` raises `AttributeError` (use `importlib.metadata`); open issue #3733. Corrects the earlier "unknown." (§Setup)
8. **Packaging** — `docling-slim` now exists (~50 MB, `[format-html]`), so the 1.3 GB heaviness is **opt-out**; don't frame it as unaddressed. (§Source Snapshot)
9. **On HTML specifically, Docling runs no ML models** — it's a BeautifulSoup backend (SimplePipeline). The "vision models on your webpage" story is PDF/image only. (Novelty §)

## Dimension-level evidence (no synthetic total)

Per methodology v3 Part 3, this pack does **not** publish a single weighted 0-100 score (the earlier "69/100" folded category penalties for "no crawler" that aren't comparable across tools). Evidence per dimension for the writer to weight:

| Dimension | Evidence (measured) | Reader caveat |
|---|---|---|
| Setup / first run | 1.3 GB venv; **~506 MiB** on-disk HF models + **~40 MB** first-run RapidOCR download across two caches; first PDF ~224 s, warm ~0.55 s | `docling-slim` opts out of the heavy path |
| PDF table fidelity | **cell recall 1.00** on 5/7 detected fixtures (values found); **in-row 1.00 on 3/5, 0.97 on T3/T5** (multi-level header shifts a row); official TEDS 93.6 | 7 synthetic tables, not a TEDS corpus |
| Table detection robustness | **isolated small table → dropped as Picture**; same table in context → converts (scripted A/B, `pdf_sparse_page_ab.json`) | layout-context effect; post-check `doc.tables` |
| Scanned / OCR | recovered a **0-text-layer** scan; default **RapidOCR** | OCR is the slow path at scale (#1143) |
| Multi-format | DOCX/XLSX/PPTX all probes found + **JSON round-trip survives** | one clean file per format |
| HTML fidelity vs cleanliness | faithful full-document; **~13% chrome on Wikipedia**, ~0% clean pages | no main-content extraction (#1865) |
| Reading order / structure | 15-pp 2-col paper: all 5 sections **in document order**; 5.99 s/pg (CPU); denser 9-pp report 14.95 s/pg | single run, CPU ceiling |
| Developer experience | 3-line API; clean `DoclingDocument`; lossless JSON | `__version__` missing (#3733) |
| Maintenance | v2.112.0 (2026-07-11), 63k stars, LF AI & Data governance, **938 open issues** | very high issue volume = very active + rough edges |
| License | MIT on code; model licenses vary | — |

## Gaps Before Final Blog Draft

- **VLM path (GraniteDocling) untested** — the optional vision-language pipeline is a separate model download and a separate quality/latency profile; not exercised here.
- **`docling-slim` not benchmarked** — we confirmed it exists on PyPI but did not install it to measure the actual slim footprint / HTML-only speed.
- **No GPU run** — all timing is CPU-only macOS arm64; OCR + TableFormer are much faster on CUDA/MPS, so per-page seconds here are a CPU ceiling, not a GPU number.
- **TEDS-scale table corpus** — our 7 synthetic + 2 real PDFs are a targeted probe, not the FinTabNet/PubTabNet-scale accuracy benchmark the official 93.6 comes from.
- **Complex/irregular merged cells + multi-page tables** (#3698 / #3553) — we tested simple colspan/rowspan (which passed); the documented hard cases were not constructed.
- **Formula / code fidelity** — the arXiv PDFs contain math; we measured reading order + tables, not formula-to-LaTeX accuracy.
- **Head-to-head with Marker / MarkItDown / Firecrawl** on these exact fixtures — third-party benchmarks exist (Docling ~0.887 vs MarkItDown ~0.844 vs Marker ~0.808 TEDS, via OpenDataLoader); a same-bench 4-way including Firecrawl does not appear to exist publicly and is the natural next pack. **The Positioning-vs-Firecrawl table above is documentation-level, not a same-machine measurement.**
- **Production-durability triad NOT tested (GIL / memory growth / object lifecycle).** For a converter positioned to batch thousands of PDFs this is a real gap: (a) **batch memory growth / leak** — we ran no long loop sampling current RSS across N conversions with a known-leak calibration (the selectolax pack's approach), so we cannot say whether repeated `convert()` calls hold a bounded working set or climb; (b) **thread scaling / GIL behavior** — no single-thread-vs-N-thread wall-clock probe of the CPU inference path, so we make no claim about parallel throughput of TableFormer/OCR; (c) **object lifecycle** — no stale-handle / converter-reuse-after-error probe. All three are untested here and should be built before any "production-ready at scale" framing; long-batch RSS growth in particular is the most likely real-world surprise.

## Raw Artifact Index

Scripts (`tests/`):
- Synthetic table PDF generator (+ ground truth): [gen_pdf_fixtures.py](tests/gen_pdf_fixtures.py)
- DOCX/XLSX/PPTX generator (+ ground truth): [gen_doc_fixtures.py](tests/gen_doc_fixtures.py)
- First-run model-download + cold/warm cost: [pdf_coldstart_download.py](tests/pdf_coldstart_download.py)
- **TableFormer cell-fidelity** (+ merged-cell handling): [pdf_table_fidelity.py](tests/pdf_table_fidelity.py)
- **Sparse-page A/B** (FINDING-D3: same table isolated vs in-context; pypdfium2 text-layer probe + `do_ocr=False` + `doc.tables`/`doc.pictures`): [pdf_sparse_page_ab.py](tests/pdf_sparse_page_ab.py)
- **Warm-conversion 3-run timing** (cheap fixtures): [warm_timing_repeats.py](tests/warm_timing_repeats.py)
- Real + scanned PDF (reading order / OCR / timing + text-layer-char probe): [pdf_real_and_scanned.py](tests/pdf_real_and_scanned.py)
- Multi-format + lossless-JSON round-trip: [multiformat_docs.py](tests/multiformat_docs.py)
- HTML boilerplate-residue quantification: [html_boilerplate_quant.py](tests/html_boilerplate_quant.py)
- Original HTML smoke runner (kept): [run_docling_material_tests.py](tests/run_docling_material_tests.py)
- **Summary generator (computes summary JSON from raw — no hand numbers):** [build_summary.py](tests/build_summary.py)

Raw results (`artifacts/raw/`): [pdf_coldstart_download.json](artifacts/raw/pdf_coldstart_download.json), [pdf_table_fidelity.json](artifacts/raw/pdf_table_fidelity.json), [pdf_sparse_page_ab.json](artifacts/raw/pdf_sparse_page_ab.json), [warm_timing_repeats.json](artifacts/raw/warm_timing_repeats.json), [pdf_real_and_scanned.json](artifacts/raw/pdf_real_and_scanned.json), [multiformat_docs.json](artifacts/raw/multiformat_docs.json), [html_boilerplate_quant.json](artifacts/raw/html_boilerplate_quant.json), [novelty_search.json](artifacts/raw/novelty_search.json), and the **generated** [docling-deep-summary.json](artifacts/raw/docling-deep-summary.json). Per-document Markdown outputs `real_*.md`, `doc_*.md`, plus the original HTML outputs `docling_{books,quotes,forms,wikipedia}.md`. Metadata: [github_repo_snapshot_2026-07-13.json](artifacts/raw/github_repo_snapshot_2026-07-13.json), [github_release_snapshot_2026-07-13.json](artifacts/raw/github_release_snapshot_2026-07-13.json), [pypi_snapshot_2026-07-13.json](artifacts/raw/pypi_snapshot_2026-07-13.json).

Fixtures (`artifacts/fixtures/`): `pdf/` (7 synthetic table PDFs + `*.groundtruth.json`, **2 in-context A/B variants `table_t1b_*`/`table_t4b_*` + their groundtruth — all generated by `gen_pdf_fixtures.py`**, 2 arXiv papers), `scanned/` (ocr_test.pdf, nemotron_multipage.pdf, old_newspaper.png, qr_bill_example.jpg — from Docling's own test suite), `docs/` (report.docx, workbook.xlsx, deck.pptx + ground truth), plus the original HTML fixtures. Note: `gen_pdf_fixtures.py` needs `reportlab` (a fixture-generation-only dependency, not part of the measured Docling stack).

Public reproducible copy: `github.com/thunderbit-operations/scraper-benchmark` → `tools/docling/`.

## Complete Source Index

- [Docling GitHub repository](https://github.com/docling-project/docling) — Tier 1 (tagline, formats, claims, MIT, IBM origin, LF AI & Data governance)
- [Docling documentation site](https://docling-project.github.io/docling) — Tier 1 (architecture, model catalog, installation)
- [ds4sd/docling-models model card](https://huggingface.co/ds4sd/docling-models) — Tier 1 (TableFormer TEDS 95.4/90.1/93.6; RT-DETR layout)
- GitHub REST API `repos/docling-project/docling` — Tier 1, metadata snapshot as-of 2026-07-13
- PyPI `docling` (2.112.0) and `docling-slim` (2.112.0) JSON metadata — Tier 1
- Docling issues cited: [#3733](https://github.com/docling-project/docling/issues/3733) (`__version__`), [#3749](https://github.com/docling-project/docling/issues/3749) (borderless), [#3698](https://github.com/docling-project/docling/issues/3698) (merged cells), [#3495](https://github.com/docling-project/docling/issues/3495) (table-as-picture), [#1865](https://github.com/docling-project/docling/issues/1865) / [#1930](https://github.com/docling-project/docling/issues/1930) (HTML nav/footer), [#2393](https://github.com/docling-project/docling/issues/2393) / [#2535](https://github.com/docling-project/docling/issues/2535) (lightweight/slim), [#3100](https://github.com/docling-project/docling/issues/3100) (7.4 GB), [#1143](https://github.com/docling-project/docling/issues/1143) (OCR speed) — all Tier 1
- Third-party table benchmarks (Tier 2, for the writer): OpenDataLoader-derived TEDS (Docling 0.887 / MarkItDown 0.844 / Marker 0.808); codecut.ai; procycons.com
- Test fixtures: 2 arXiv PDFs (2408.09869 = the Docling report; 1706.03762 = Attention Is All You Need); Docling's own `tests/data/scanned` (ocr_test, nemotron_multipage, old_newspaper, qr_bill_example); public HTML pages captured locally
