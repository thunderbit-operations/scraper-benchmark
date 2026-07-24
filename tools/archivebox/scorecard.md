# ArchiveBox — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing a run. ArchiveBox is scored on **redundant-output preservation coverage and
failure honesty**, not on crawl breadth or structured-data extraction (out of
scope). All findings are on **v0.7.4 with every dependency valid**.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 8 | 7 | one image, `init --setup` clean; all deps valid; but `-e SAVE_*` ignored, only `config --set` persists (`metadata`) |
| Runtime-content capture (RUNTIME) | 14 | 12 | 5/8 outputs get JS-injected token; wget+mercury miss it (`full-matrix.json`) |
| Byte-level preservation (JSLIT/WARC) | 10 | 9 | wget/WARC uniquely preserves the `app.js` literal the rendered captures drop |
| Article-text extraction | 10 | 6 | readability keeps runtime; mercury drops it (re-fetches URL) — same tool, inconsistent (`mercury-isolation.json`) |
| Redundancy independence | 12 | 6 | chrome-off collapses runtime from 4 outputs at once; readability/htmltotext coverage is inherited (`nochrome.json`) |
| Static-page redundancy | 8 | 8 | wget/singlefile/dom identical `{STATIC,BOILER}` on `/static` (`full-matrix.json`) |
| Visual outputs (pdf/screenshot) | 8 | 7 | pdf carries extractable text layer (pypdf); screenshot visual-only |
| Failure honesty | 12 | 7 | 500 exits cleanly + marks wget/mercury failed, but chrome extractors report `succeeded` on the error page — status≠content (`robustness.json`) |
| Status/journaling integrity | 6 | 4 | htmltotext produces output but `history` entry is `[]` (status-invisible) |
| Cost transparency | 6 | 4 | ~8× origin fetch per archived page, undisclosed by the "redundant copies" framing (`server_hits`) |
| Determinism | 6 | 6 | token matrix identical across 3 runs (`token_matrix_identical_across_runs: true`) |
| **Total** | **100** | **76** | provisional research-material score only |

Scoring notes:

- **Runtime-content capture (12/14)**: five outputs capture the JS-materialised
  token; the deduction is that the two *article* extractors split — one of the two
  reader outputs (mercury) silently misses dynamic content.
- **Article-text extraction (6/10)**: readability is correct (reads the rendered
  capture) but mercury re-fetches the raw URL and misses runtime content; two
  outputs sold as equivalent are not, and the deprecated mercury is still default-on.
- **Redundancy independence (6/12)** — the lowest-but-one: the "multiple redundant
  copies" promise is weaker than it reads. readability/htmltotext do not
  independently render; they consume the chrome capture, so one chrome failure
  removes dynamic content from four outputs simultaneously, leaving only static wget
  bytes. Genuine independence exists only between the byte-mirror (wget) and the
  chrome layer.
- **Failure honesty (7/12)**: the run does not abort on a 500 (good), but a
  `succeeded` extractor status can mean "faithfully archived the error page," so
  status alone is not a preservation guarantee.
- **Cost transparency (4/6)** and **journaling (4/6)** capture the two undisclosed
  costs: ~8× origin fetches per page, and an output (htmltotext) that never appears
  in the status ledger.
- Scores reflect **preservation coverage + failure honesty** only; ArchiveBox's
  crawl/scheduling/search/UI are not scored here.
