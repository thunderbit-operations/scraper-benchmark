# apache-tika — file-type extraction fidelity & metadata behavior (evidence pack)

Evidence-only evaluation of **Apache Tika 3.3.2** (CLI fat jar) on **OpenJDK 26.0.1**, focused
on the queue question: *measure file-type extraction fidelity and metadata behavior in a
web-data pipeline.* Controlled synthetic ground truth, 9 dependency-free file types. No blog,
not published, evidence phase only.

## What this pack measures (and does not)

Tika **detects** a byte stream's media type (magic → XML root → filename glob → supplied type),
then extracts **flattened plain text + a metadata key/value map**. This pack quantifies, on
documents whose every block is sentinel-labeled and whose metadata is embedded with known
values:

- **H1 — content-type detection under adversarial extension–content mismatch** (magic vs
  extension, with/without a filename hint).
- **H2 — multi-format content-extraction recall** (does every block's text survive `--text`).
- **H3 — metadata behavior** (author / title / created recovery + normalized keys).
- **H4 — robustness** on empty / truncated / non-ASCII inputs.

**Not** measured: OCR / scanned-PDF (tesseract absent → **BLOCKED**), element-type
classification (not a Tika capability — that is the `unstructured`/`docling` axis), layout /
table-structure recovery, real-corpus accuracy, resource cost. See `research-materials.md →
Gaps`.

## Headline results (all derived by `tests/metrics.py`)

- **Detection splits into two regimes.** Magic-bearing formats (PDF/DOCX/RTF/HTML/XML) detect
  to the **true** type in **30/30** adversarial cells — a PDF renamed `.txt` is still
  `application/pdf`, even from a filename-less stream. Magic-**less** text formats
  (Markdown/CSV) depend entirely on the extension: **10/18** cells collapse to `text/plain`
  once the filename is absent or lies. *(A pipeline that strips filenames silently loses
  Markdown/CSV identity but keeps every binary/markup format.)*
- **Content recall = 1.000 on all 14 carriers** — Tika drops no text (all table cells + list
  items survive), but discards **all structure** (content-complete, structure-blind).
- **Metadata:** author→`dc:creator` + title→`dc:title` recovered on 4/4 metadata-bearing
  carriers; `created` exact on DOCX+ODT.
- **Robustness:** empty and truncated inputs throw **uncaught** (exit 1, empty stdout —
  `ZeroByteFileException` / `TikaException` / POI FATAL); **`--detect` stays exit 0 and correct**
  on truncated binaries (a reliable triage signal); no-BOM UTF-8 is decoded correctly.
- **Scorecard: 83/100** (provisional, research-material only).

Full numbers + novelty tags: `research-materials.md`. Weights + scores: `scorecard.md`.
Versions, commands, key mapping, redaction: `metadata-snapshot.md`.

## Reproduce

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk && export PATH="$JAVA_HOME/bin:$PATH"
cd tools/apache-tika

# tika jar is gitignored (67 MB) — fetch it (URL + sha256 in metadata-snapshot.md)
mkdir -p vendor && curl -L -o vendor/tika-app-3.3.2.jar \
  https://repo1.maven.org/maven2/org/apache/tika/tika-app/3.3.2/tika-app-3.3.2.jar

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python reportlab python-docx odfpy

.venv/bin/python tests/build_fixtures.py   # fixtures + ground-truth JSONs
.venv/bin/python tests/run_tika.py         # drive the jar -> artifacts/raw/tika_raw.json
.venv/bin/python tests/metrics.py          # derive every number -> artifacts/raw/metrics.json
```

`run_tika.py` finds the jar via `$TIKA_JAR` (default `vendor/tika-app-*.jar`) and java via
`$JAVA`/`$JAVA_HOME`.

## Layout

```
tests/build_fixtures.py   single source of truth: 9-carrier sentinel fixtures + adversarial
                          MIME matrix + robustness cases + {ground,mime,robustness}_truth.json
tests/run_tika.py         extraction arm — drives tika-app.jar, dumps ONLY raw observations
tests/metrics.py          derives content recall / metadata recall / MIME matrix / robustness
tests/fixtures/           committed text carriers + truth JSONs (binaries/adversarial regenerated)
artifacts/raw/            committed evidence: tika_raw.json, metrics.json
vendor/                   tika-app jar (gitignored, reproduce from metadata-snapshot.md)
```

## Parity (same-testbed contrast)

Fixtures mirror the sibling `unstructured`/`docling`/`markitdown` packs. Where **`unstructured`
measures element-type CLASSIFICATION** (and loses on it), **Tika measures CONTENT fidelity** and
has none to lose because it flattens — content-complete but structure-blind. And where
`unstructured`'s PDF path was torch-BLOCKED, Tika parses the PDF text layer natively (PDFBox).
Cross-tool synthesis is out of scope here; flagged for the parent.
