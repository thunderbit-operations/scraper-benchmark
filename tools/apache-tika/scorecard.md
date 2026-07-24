# apache-tika — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark and not a cross-tool ranking. Weights are pack-local and pre-registered
here; scores are evidence-anchored, each citing a run. All numbers are on controlled synthetic
fixtures (**Apache Tika 3.3.2**, **OpenJDK 26.0.1**, macOS arm64, 2026-07-24) across the
**HTML / Markdown / plain-text / DOCX / PDF-text-layer / RTF / ODT / XML / CSV** carriers only.
**OCR / scanned-image PDF paths are BLOCKED** (tesseract/poppler absent) and are **not scored**.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 8 | 7 | single `tika-app.jar`, `java -jar … --text/--metadata/--detect` runs on JDK 26 with no config; docked for 67 MB jar + per-invocation JVM cold start (no daemon in CLI mode) |
| MIME detection — magic-bearing robustness | 12 | 12 | **30/30 cells exact** for PDF/DOCX/RTF/HTML/XML under lying-ext, no-ext, and filename-less stream (`metrics.json → mime_detection.summary`) |
| MIME detection — magic-less / extension dependency | 8 | 5 | Markdown/CSV identity survives **only** with the extension present; **10/18** magic-less cells collapse to `text/plain` when the filename is absent or lies (FINDING-01) — a real pipeline gap, by design |
| Multi-format content-extraction recall | 14 | 14 | **content_recall = 1.000 on all 14 carriers**, all table cells + list text survive `--text`, `missing_sentinels = []` (`metrics.json`) |
| Structure preservation | 6 | 2 | Tika flattens: **no element types; list markers→literal `- ` in txt/md/rtf (indented text, no marker, in HTML/DOCX); table grid→tab-joined**; content-complete but structure-blind (by design, hence not zero) |
| Metadata extraction (author/title/created) | 12 | 11 | author→`dc:creator` + title→`dc:title` recovered on **4/4** metadata-bearing carriers; created→`dcterms:created` **exact** on DOCX+ODT; PDF created present but presence-only |
| Charset detection | 6 | 5 | no-BOM undeclared UTF-8 decoded as **UTF-8**, `日本語テスト` intact (FINDING-04); ASCII carriers report ISO-8859-1 (indistinguishable on ASCII, not a miss) |
| Adversarial robustness / error signaling | 10 | 7 | process-safe (no hang/segfault); **detection decoupled + robust** (exit 0, correct type on truncated binaries); but extraction throws **uncaught** on empty+corrupt (exit 1, empty stdout) — empty vs corrupt indistinguishable without `--detect` |
| Cross-format consistency | 10 | 8 | content 100% consistent across formats; detection consistent for magic formats, divergent for magic-less (extension-driven) |
| Determinism | 6 | 6 | all 14 carriers returned byte-identical `--text` across 3 reps before any number was used (`determinism_text_identical = true`) |
| Deployment surface | 8 | 6 | one fat jar bundles PDFBox/POI/jsoup → PDF/DOCX/ODT/RTF/HTML parse with **zero external deps** (contrast: sibling `unstructured` PDF path was torch-BLOCKED); docked because **OCR needs tesseract+poppler** (BLOCKED) and JVM footprint |
| **Total** | **100** | **83** | provisional research-material score only, not a final rating |

Scoring notes:

- **MIME detection is Tika's crown jewel and it earns full marks on magic-bearing formats
  (12/12):** a PDF renamed `.txt`, a DOCX renamed `.jpg`, and even a filename-less byte stream
  all resolve to the true type — the lying extension is ignored. This is exactly the axis where
  the sibling `unstructured` pack could do nothing (libmagic absent on that host).
- **The magic-less dimension is docked to 5/8 deliberately:** it is not a bug (Markdown/CSV
  have no magic bytes, and `text/markdown ⊂ text/plain` is documented), but it is a **genuine
  operational gap** — any pipeline that strips or normalizes filenames loses Markdown/CSV
  identity. Half credit reflects "correct with the extension, degraded without it."
- **Content recall (14/14):** Tika loses **no content** on any text-bearing carrier — the
  parity mirror of `unstructured`'s classification losses (verbless prose → UncategorizedText,
  md lazy-list collapse). Tika does not classify, so it cannot mis-classify; the cost is
  recorded separately under Structure preservation.
- **Structure preservation (2/6):** scored low **on purpose** — Tika emits flat text with no
  element typing, list, or table structure. This is by design and outside Tika's stated scope,
  so not zero; but a consumer needing typed elements/tables must pair Tika with something else.
- **Metadata (11/12):** strong and normalized — the single deduction is that `created` is not
  uniformly recoverable (PDF surfaced a generator timestamp, not our embedded value; TXT/MD/CSV
  carry none).
- **Robustness (7/10):** the good part — detection survives truncation and is a reliable triage
  signal; the docked part — the extraction CLI throws an **uncaught** exception on both empty
  and corrupt inputs (exit 1, empty stdout), so those two cases are indistinguishable from the
  extraction call alone.
- Scores reflect **content-extraction fidelity, metadata behavior, and content-type detection
  on controlled ground truth** for the 9 dependency-free carriers only; Tika is **not** scored
  on OCR/scanned PDF (BLOCKED), real-corpus accuracy, element-type classification (not a Tika
  capability), or resource cost (not measured — see Gaps).
