# apache-tika — research materials (evidence, not prose)

Scope: element-free **content extraction fidelity, metadata behavior, and content-type
detection** of Apache **Tika 3.3.2** (CLI fat jar) on **JDK 26.0.1**, over 9 file types on
controlled synthetic ground truth. **OCR / scanned-PDF paths are BLOCKED** (tesseract/poppler
absent) and produce no numbers. All figures are computed by `tests/metrics.py` from
`artifacts/raw/tika_raw.json` vs `tests/fixtures/*_truth.json` — no metric is hand-written.

Findings are numbered + confidence-tagged (three-rep / single-observation) + novelty-tagged
(DOCUMENTED mechanism vs EXCLUSIVE-QUANTIFICATION of net-new measurement). No finding is
tagged "undocumented".

---

## FINDING-01 — content-type detection splits into two regimes under extension–content mismatch (H1)

**Result (EXCLUSIVE-QUANTIFICATION; DOCUMENTED mechanism).** Over an 8-type × {correct ext,
lying ext, no ext} × {filename present, filename-less stream} matrix (`metrics.json →
mime_detection`):

- **Magic-bearing formats — PDF, DOCX, RTF, HTML, XML — detect to the true type in
  30 / 30 cells (rate 1.000).** A PDF renamed `.txt` → `application/pdf`; a DOCX renamed
  `.jpg` → the OOXML type; both hold even from a **filename-less stream** (magic alone
  suffices). The lying extension is ignored.
- **Magic-less text formats — Markdown, plain-text, CSV — depend entirely on the filename.**
  10 / 18 magic-less cells **collapse to `text/plain`**. Markdown resolves to `text/markdown`
  **only** with the `.md` extension present (`correct_ext/with_filename`); the moment the
  filename is absent (stream) or lies, it degrades to `text/plain`. Plain-text is `text/plain`
  everywhere (its true type — never a "collapse"). CSV yields `text/csv` **only** from the
  `.csv` extension glob (see FINDING-05).

**Mechanism (DOCUMENTED, cited):** detection order is magic → XML root → filename glob →
supplied type ([detection.html](https://tika.apache.org/3.0.0/detection.html)); magic-less
formats have nothing but the glob to go on, and `text/markdown` is a documented subtype of
`text/plain`. **Net-new = the quantified 30/30 robustness + the exact collapse count/pattern**;
no public source tabulates this.

**Pipeline implication (in-scope, the queue focus):** a web-data pipeline that normalizes or
strips filenames (HTTP streams, blob-store keys, content-addressed storage) **silently loses
Markdown / CSV identity but keeps every binary/markup format** — routing logic keyed on the
detected type must not assume the extension is present for text formats.

Evidence: `artifacts/raw/metrics.json` (`mime_detection.rows`, `.summary`),
`artifacts/raw/tika_raw.json` (`mime`). Reproduce: `tests/run_tika.py` + `tests/metrics.py`.

---

## FINDING-02 — content-extraction recall is 1.000 on every text-bearing carrier; structure is fully discarded (H2)

**Result (EXCLUSIVE-QUANTIFICATION; DOCUMENTED capability).** Across all **14 carrier
renderings** (canonical doc × HTML/MD/TXT/DOCX/PDF/RTF/ODT/XML + table doc ×
HTML/MD/TXT/DOCX/CSV/XML), the only distinct content-recall value is **1.000** — every
authored block sentinel survives into `--text`, including **all table cells** (flattened to
tab/space-joined rows) and list items (bullets flatten to literal `- ` in txt/md/rtf, to indented text with no marker in HTML/DOCX). Recall is scored
against the blocks **actually authored into each carrier** (a CSV carries only the grid, so it
is scored 1/1 on the table block, not penalized for lacking the title/narrative blocks).

**Interpretation (mechanism, DOCUMENTED):** Tika is a **faithful flattener** — it emits text +
metadata and performs **no element-type classification**, so it has **zero classification
loss** but also **zero structure**: no Title/NarrativeText/ListItem labels, list markers and
table grids are gone. Content-complete, structure-blind.

Evidence: `metrics.json → content_and_metadata` (all `content_recall = 1.0`, `missing_sentinels
= []`). Determinism: all 23 `--text` reps (14 carriers, 3 reps each after warm-up) returned
byte-identical output before any number was used (`tika_raw.json →
determinism_text_identical = true` on every carrier).

---

## FINDING-03 — metadata recovery: author/title on every metadata-bearing carrier; exact created where the format embeds it (H3)

**Result (EXCLUSIVE-QUANTIFICATION; DOCUMENTED capability).** Known values embedded, then
recovered vs Tika's normalized keys (`metrics.json → metadata_fields`):

| Carrier | author (`dc:creator`) | title (`dc:title`) | created (`dcterms:created`) |
|---|---|---|---|
| HTML (`<meta name=author>`, `<title>`) | ✅ | ✅ | not embedded |
| DOCX (core properties) | ✅ | ✅ | ✅ exact `2021-03-15T09:30:00Z` |
| PDF (reportlab info dict) | ✅ | ✅ | present but not our known value → presence-only, not scored |
| ODT (`meta.xml`) | ✅ | ✅ | ✅ exact `2021-03-15T09:30:00Z` |

Author is normalized to **`dc:creator`** across formats (HTML `<meta name=author>`, DOCX/ODT
creator, PDF `/Author` all map to it); title to **`dc:title`**; created to **`dcterms:created`**.
Formats with no document-metadata layer (TXT / MD / CSV / RTF / XML here) surface none — Tika
does not fabricate. **Net-new = the per-field, per-format recall + the key mapping.**

Evidence: `metrics.json → content_and_metadata.*.metadata_fields`; raw dicts in
`tika_raw.json → content.*.metadata`.

---

## FINDING-04 — empty and corrupt inputs throw (exit ≠ 0, empty stdout); detection stays robust; charset detection recovers UTF-8 (H4, adversarial)

**Result (EXCLUSIVE-QUANTIFICATION; DOCUMENTED exception classes).** `metrics.json →
robustness`:

| Case | extraction (`--text`/`--json`) | exception | detection (`--detect`) |
|---|---|---|---|
| `empty.txt` (0 B) | **exit 1, empty stdout** | `org.apache.tika.exception.ZeroByteFileException: InputStream must have > 0 bytes` | **exit 0** — `text/plain` (filename) / `application/octet-stream` (stream) |
| `truncated.pdf` (512 B of a valid `%PDF`) | **exit 1, empty stdout** | `org.apache.tika.exception.TikaException: TIKA-198: Illegal IOException from PDFParser` | **exit 0** — `application/pdf` (header intact) |
| `truncated.docx` (1024 B of the zip) | **exit 1, empty stdout** | POI `FATAL … XML document structures must start and end within the same entity` | **exit 0** — OOXML type |
| `utf8_nobom.txt` (multibyte, no BOM/decl) | **exit 0** | — | **exit 0** — `text/plain` |

Key net-new facts for a pipeline:

1. **Empty and corrupt are indistinguishable by the extraction call alone** — both exit 1 with
   empty stdout via an **uncaught** exception (the CLI does not swallow it into a clean empty
   result). Triage requires the **separate, robust `--detect`** call.
2. **Detection is decoupled from parsing** — `--detect` returns the correct type (exit 0) on
   truncated binaries because it only needs the intact header/magic, whereas the parser throws
   on the broken body.
3. **Charset detection works** — the no-BOM, undeclared UTF-8 file was decoded as **UTF-8**
   (`Content-Type: text/plain; charset=UTF-8`) and `日本語テスト` survived intact.
   (Caveat: the pure-ASCII canonical carriers report `charset=ISO-8859-1`, which is
   indistinguishable from UTF-8 on ASCII bytes — not a mis-detection.)

Process-safe (no hang/segfault) but **not** silently graceful: corruption is signaled loudly.

Evidence: `metrics.json → robustness.rows` (`extraction_exit_zero`, `detection_exit_zero`,
`text_exception`, `detected_encoding`); `tika_raw.json → robustness`.

---

## FINDING-05 — CSV identity is extension-driven at detection; the statistical parser resolved a small regular grid to text/plain (H1 supporting, caveated)

**Result (single-observation, DOCUMENTED mechanism).** `text/csv` surfaced **only** from the
`.csv` extension glob at detection time. From a filename-less stream, and at **parse time**,
Tika's `TextAndCSVParser` (confirmed in `X-TIKA:Parsed-By`) resolved the fixture's small
2-column × 3-row grid to **`text/plain`** — its documented fallback when column-regularity /
quoting signal is insufficient.

**Scope caveat:** this is a **small-fixture** observation. A larger or quoted CSV may trip
the statistical detector; this pack does not claim CSV content-detection is broken, only that
on a minimal grid the extension is what produced `text/csv`. Tagged single-observation.

Evidence: `tika_raw.json → content.table.csv.metadata` (`Content-Type: text/plain`,
`X-TIKA:Parsed-By` includes `TextAndCSVParser`); `metrics.json → mime_detection` (csv row).

---

## Novelty ledger (gate 1)

| Finding | Mechanism | Net-new (this pack) | Tag |
|---|---|---|---|
| F01 magic vs magic-less detection | detection order documented (detection.html); md⊂text/plain documented | 30/30 magic robustness + magic-less collapse count/pattern on ground truth | DOCUMENTED mech + **EXCLUSIVE quantification** |
| F02 content recall 1.0 / structure-blind | Tika = flattener (documented) | per-format recall table proving zero silent drop; parity vs unstructured classification loss | DOCUMENTED cap + **EXCLUSIVE quantification** |
| F03 metadata recovery | metadata extraction documented | per-field/per-format recall + normalized key map | DOCUMENTED cap + **EXCLUSIVE quantification** |
| F04 empty/corrupt exit behavior | `ZeroByteFileException`/`TikaException` are documented classes | exit-code triage table; detection-decoupled-from-parse; UTF-8 charset recovery | DOCUMENTED classes + **EXCLUSIVE quantification** |
| F05 CSV extension-driven | `TextAndCSVParser` fallback documented | observed on a minimal grid (caveated) | DOCUMENTED, single-observation |

## Gaps / not evaluated (explicit)

- **OCR / scanned-image PDF** — BLOCKED (tesseract + poppler absent). No numbers.
- **Real-corpus accuracy** — out of scope (synthetic ground truth only), consistent with the
  sibling `unstructured` pack; the pack measures fidelity vs known labels, not field accuracy
  on messy real documents.
- **Encrypted / password-protected files, embedded/recursive documents (`-J` recursion),
  huge-file throughput / peak-RSS** — not measured here (the queue focus is fidelity +
  metadata + detection, not resource cost). Flagged for a follow-up if the parent wants a
  cost axis.
- **CSV statistical detector at scale** — only a minimal grid tested (FINDING-05 caveat).
- **1000+ formats** — 9 representative, dependency-free types tested; the long tail is not.
