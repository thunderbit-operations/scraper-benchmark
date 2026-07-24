# apache-tika — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design + decision only.
Decision: **PROCEED** — a measurable, mechanism-tied gap exists that public write-ups
describe qualitatively but do not quantify: (1) how Tika's content-type **detection** holds
up when the filename extension contradicts (or is stripped from) the true content, split by
whether the format carries magic bytes; (2) per-format **content-extraction recall** against
labeled ground truth; (3) per-field **metadata** recovery; (4) failure signaling on
empty / corrupt inputs. The divergence is already visible in a smoke test (a `.pdf`-named
Markdown file detects as `text/plain`, a `.txt`-named PDF detects as `application/pdf`).

Broad keyword: **`apache-tika`** (the Java toolkit that detects a file's media type and
extracts text + metadata from ~1000+ formats via bundled parsers: PDFBox, POI, jsoup, …).
Article boundary: Tika ingests a byte stream, **detects** its media type (magic → XML root →
filename glob → supplied type), then dispatches to a parser that emits **flattened plain
text + a metadata key/value map**. This pack judges, on documents whose every block is
pre-labeled with a unique sentinel and whose metadata is embedded with known values:
(1) **content-extraction recall** — does every authored block's text survive `--text`, across
HTML / Markdown / plain-text / DOCX / PDF(text-layer) / RTF / ODT / XML / CSV; (2) **metadata
behavior** — does Tika surface embedded author / title / created, and under which normalized
keys; (3) **content-type detection under adversarial extension–content mismatch** — magic vs
extension, with and without a filename hint; (4) **robustness** — empty / truncated / non-ASCII
inputs.

It is **NOT** an OCR / scanned-document evaluation (tesseract absent → BLOCKED), **NOT** an
element-type classification benchmark (Tika does not label Title / NarrativeText / ListItem —
that is the sibling `unstructured` / `docling` axis), **NOT** a layout / table-structure
recovery evaluation, and **NOT** a real-corpus accuracy benchmark.

## System-dependency reality (scoping, up front)

- **JDK 26.0.1** (Homebrew OpenJDK) — Tika 3.3.2 runs cleanly (`--version`, `--text`,
  `--metadata`, `--json`, `--detect` all exit 0 on well-formed input). **No older LTS
  needed.**
- **PDFBox / POI / jsoup are bundled in `tika-app.jar`** — so PDF **text-layer**, DOCX, ODT,
  RTF, HTML all parse with **no external system dependency**. This is a material contrast
  with the sibling `unstructured` pack, whose electronic-PDF path was BLOCKED (it pulls
  `unstructured_inference` / torch at import).
- **tesseract ❌ / poppler ❌** on this host → every **OCR / scanned-image PDF** path is
  **BLOCKED_SYSTEM_DEP** and produces **no numbers** here. Only the **electronic text layer**
  of PDFs is in scope (PDFBox, pure Java).

## SERP / official / issue scan (≈20 results, docs, source)

### What the sources repeat (consensus — documented / qualitative)

- **Detection order is documented**: magic bytes on the file start, then XML root element,
  then filename/extension glob, then any supplied content type
  ([detection.html](https://tika.apache.org/3.0.0/detection.html)). "Wrong extensions should
  only confuse detection when the extension is all it has to go on"
  ([Open Preservation Foundation](https://openpreservation.org/blogs/apache-tika-file-mime-type-identification-and-importance-metadata/)).
  → the magic-vs-extension precedence is **DOCUMENTED**; no public source gives a quantified
  adversarial accuracy matrix.
- **Markdown is a subtype of plain text**: `text/markdown` (older `text/x-web-markdown`) has
  super-type `text/plain` and is recognized via the `.md` extension; with no magic bytes,
  detection of Markdown depends on the filename
  ([search consensus](https://ciam-tika.straumann.com/mime-types/text/x-web-markdown)).
  → **DOCUMENTED** hierarchy; the *collapse pattern* (what exactly it degrades to under a
  lying / absent extension) is not quantified publicly.
- **CSV uses a statistical parser** (`TextAndCSVParser`): looks for column-count regularity /
  quoted cells, else falls back to `text/plain`
  ([javadoc](https://tika.apache.org/2.7.0/api/org/apache/tika/parser/csv/TextAndCSVParser.html)).
  → **DOCUMENTED** mechanism.
- **Metadata extraction** (author / title / created / content-type) across PDF / DOCX is
  **DOCUMENTED** capability in every tutorial; none quantify per-field, per-format recall on
  known-embedded values.
- **`ZeroByteFileException`** is a documented Tika class for empty input. Behavior of the
  **CLI exit code** on empty / corrupt files is not tabulated in the write-ups.

### Where the information gain is (net-new = quantification + adversarial edges)

No public source provides, on **controlled ground truth**: (a) a magic-bearing vs magic-less
**detection accuracy matrix** across {correct, lying, absent} extension × {filename present,
filename-less stream}; (b) a per-format **content-recall** table proving zero silent text
drop (or finding the drops); (c) a per-field / per-format **metadata recall** table with the
normalized key mapping; (d) an **exit-code triage table** distinguishing empty vs corrupt vs
valid, and showing detection is decoupled from parsing. These are the pack's deliverables.

## Hypotheses (≥1 adversarial)

- **H1 (adversarial — MIME sniffing under extension–content mismatch).** Magic-bearing
  formats (PDF / DOCX / RTF / HTML / XML) detect to their **true** media type regardless of a
  lying extension, a stripped extension, or a filename-less stream; magic-**less** text
  formats (Markdown / plain-text / CSV) depend entirely on the extension and **collapse to
  `text/plain`** once it is absent or lies. Metric: exact-match rate per cell of the 8-type ×
  {correct, lying, no-ext} × {filename, stream} matrix vs true type.
- **H2 (multi-format content-extraction recall).** Tika's `--text` recovers **~100%** of
  authored block text on every text-bearing carrier (it is a faithful flattener), **but
  discards all structure** (element types, list markers, table grid). Metric: sentinel
  survival fraction per carrier; structure recorded qualitatively.
- **H3 (metadata behavior).** Tika surfaces embedded author / title on every carrier that
  stores them (HTML / DOCX / PDF / ODT) under normalized keys (`dc:creator` / `dc:title`),
  and an exact **created** timestamp where the format embeds one (DOCX / ODT). Metric:
  per-field recovery vs known-embedded values.
- **H4 (adversarial — degradation & error signaling).** On empty / truncated / non-ASCII
  inputs Tika is **process-safe** (no hang / segfault) but the extraction path throws an
  **uncaught exception → non-zero exit + empty stdout**; **detection** (`--detect`) stays
  exit 0 and correct on truncated binaries (header intact); charset detection recovers UTF-8
  on a no-BOM multibyte file. Metric: exit codes + exception class + detected charset.

## Test matrix

- **Formats (Tika-native, dependency-free):** HTML, Markdown, plain-text, DOCX, PDF
  (text-layer), RTF, ODT, XML, CSV.
- **Content + metadata (H2/H3):** one canonical logical doc (11 sentinel blocks) rendered
  across 8 carriers + one table doc (3 blocks) across 6; known author/title/created embedded
  where supported.
- **Adversarial MIME (H1):** 8 true types × {correct ext, lying ext, no ext} × {filename,
  filename-less stream}.
- **Adversarial robustness (H4):** empty file, truncated PDF (512 B), truncated DOCX
  (1024 B), non-ASCII UTF-8 no-BOM.
- ≥20 distinguishing observations; ≥1 scale item (11-block doc across 8 binary+text carriers);
  ≥2 adversarial families (H1 mismatch matrix, H4 malformed).

## Information-gain verdict

**PROCEED.** The mechanisms are documented; the **quantified adversarial matrices** and the
**pipeline-relevant exit-code triage** are not. Every finding is tagged DOCUMENTED (mechanism)
vs EXCLUSIVE-QUANTIFICATION (net-new measurement) in `research-materials.md`; nothing is
crowned "undocumented".

## Parity (same-testbed contrast, noted for the parent)

The repo already has `unstructured` / `docling` / `markitdown` packs — other document →
structure converters — tested on the same sentinel-fixture design. This pack's fixtures mirror
that design so the contrast is direct: **`unstructured` measures element-type CLASSIFICATION
fidelity (and loses on it: verbless prose → UncategorizedText, md lazy-list collapse); Tika
measures CONTENT fidelity and has zero classification because it flattens** — content-complete
but structure-blind. And where `unstructured`'s PDF path was BLOCKED (torch), Tika parses the
PDF text layer natively. Cross-tool synthesis is out of scope here; flagged for the parent.
