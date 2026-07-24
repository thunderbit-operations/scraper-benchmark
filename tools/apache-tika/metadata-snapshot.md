# apache-tika — metadata snapshot

Fetched / tested: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Project | [apache/tika](https://github.com/apache/tika) — "detects and extracts metadata and text from over a thousand file types" |
| License | **Apache-2.0** |
| Version tested | **3.3.2** (latest stable; 4.0.0 is alpha/beta as of test date) |
| Distribution tested | `tika-app-3.3.2.jar` (CLI fat jar — bundles all parsers) |
| Download URL | `https://repo1.maven.org/maven2/org/apache/tika/tika-app/3.3.2/tika-app-3.3.2.jar` |
| jar sha256 | `71ca551380e5eab1add99101f4597a8a49a6a18c6143d6874ee9599ca10ae00e` |
| jar size | 66,978,444 bytes (~67 MB) — **gitignored, not shipped** |

Environment actually used:

| Item | Value |
|---|---|
| Apache Tika | **3.3.2** (`java -jar tika-app-3.3.2.jar --version` → `Apache Tika 3.3.2`) |
| JDK | **OpenJDK 26.0.1** (Homebrew, 2026-04-21) — **runs Tika 3.3.2 with no compatibility issue**; no older LTS required |
| Bundled parsers exercised | PDFBox (PDF), Apache POI (DOCX/OOXML), jsoup/`JSoupParser` (HTML), `TextAndCSVParser` (TXT/CSV), ODF (ODT), RTF |
| Fixture-gen Python | **3.12** (uv venv) + reportlab 5.0.0 + python-docx 1.2.0 + odfpy 1.4.1 (used **only** to author fixtures, not part of the tool under test) |
| Platform | **macOS 26.5.2 arm64** |
| Test date | **2026-07-24** |

## System dependencies — ABSENT on this host (→ BLOCKED paths, not tested)

| Dependency | Status | Gated paths |
|---|---|---|
| **tesseract** | **ABSENT** | all OCR; text from scanned/image PDFs and images |
| **poppler** | **ABSENT** | PDF rasterization for OCR |

**In scope (no external dep needed):** PDF **text-layer** extraction (PDFBox, pure Java),
DOCX, ODT, RTF, HTML, XML, plain-text, Markdown, CSV. All ran on this host with **no**
tesseract/poppler. That is the entire scope. **Note the contrast** with the sibling
`unstructured` pack, whose electronic-PDF path was BLOCKED because it imports
`unstructured_inference`/torch at module load — Tika needs none of that for the PDF text layer.

## Exact commands run

Everything is offline (fixtures are local, self-authored). Prefix every shell with:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk && export PATH="$JAVA_HOME/bin:$PATH"
cd tools/apache-tika

# 0) obtain the tika jar (gitignored; reproduce from the URL above) + fixture-gen venv
mkdir -p vendor && curl -L -o vendor/tika-app-3.3.2.jar \
  https://repo1.maven.org/maven2/org/apache/tika/tika-app/3.3.2/tika-app-3.3.2.jar
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python reportlab python-docx odfpy

# 1) build the annotated fixtures (9 carriers) + ground-truth JSONs
.venv/bin/python tests/build_fixtures.py    # -> tests/fixtures/* + {ground,mime,robustness}_truth.json

# 2) drive tika-app.jar (raw text / metadata / detection; NO metrics computed here)
.venv/bin/python tests/run_tika.py          # -> artifacts/raw/tika_raw.json   (TIKA_JAR / JAVA overridable)

# 3) derive content recall + metadata recall + mime matrix + robustness from raw vs labels
.venv/bin/python tests/metrics.py           # -> artifacts/raw/metrics.json
```

The Tika CLI invocations used: `--text <f>` (flattened text), `--json <f>` (metadata dict),
`--detect <f>` (content type with filename glob), and `cat <f> | … --detect` (content type
from a filename-less stream — isolates magic vs extension).

## Metadata key mapping observed (H3)

| Logical field | Tika key(s) observed | Formats |
|---|---|---|
| author | `dc:creator` (also `author` for HTML) | HTML, DOCX, PDF, ODT |
| title | `dc:title` | HTML, DOCX, PDF, ODT |
| created | `dcterms:created` (+ `pdf:docinfo:created`, `meta:creation-date`) | DOCX, ODT exact; PDF presence-only |
| detected type | `Content-Type` | all |
| charset | `Content-Encoding` / `X-TIKA:detectedEncoding` | text carriers |

## Reproducibility notes

- **Anti-hardcoding split.** `run_tika.py` writes only raw observations (extracted text, the
  metadata dict, detected content type, exit codes, exception line). **Every** recall / accuracy
  number is derived in `metrics.py` from that raw output vs the `*_truth.json` labels. No metric
  constant is hand-written.
- **Ground truth is generated with the bytes.** `build_fixtures.py` emits all carrier renderings
  and the truth JSONs together; each block carries a unique sentinel, so "survived / dropped" is
  exact case-insensitive substring membership. Content recall is scored against the blocks
  actually authored into each carrier (`blocks_by_format`), so a CSV is not penalized for
  lacking non-grid blocks.
- **Detection isolation.** Magic-vs-extension is separated by running `--detect` **with** the
  filename (glob active) and **from a filename-less stdin stream** (magic/content only) — the
  clean 2×2 with the {correct, lying, no-ext} extension conditions.
- **Determinism** asserted (3 reps byte-identical `--text` on all 14 carriers) before any
  single number is used.
- **Redaction.** `$HOME`→`~`, `$TMPDIR` and `/var/folders`→`<TMP>` applied to every written
  JSON. Verified: **0** host-path hits in `artifacts/` (Tika's `resourceName` reported only the
  basename on this host, so no absolute path appeared to begin with; redaction is applied
  defensively regardless).
- **Not shipped (gitignored):** the **tika-app jar** (67 MB — reproduce from the URL+sha256
  above), the fixture-gen `.venv/`, the regenerated **binary fixtures** (`.docx`/`.pdf`/`.odt`
  have non-deterministic internal timestamps; only their extracted text/metadata is asserted),
  and the regenerated **adversarial fixture trees** (`fixtures/mime/`, `fixtures/robust/`). The
  text carriers (`.html/.md/.txt/.xml/.rtf/.csv`), the `*_truth.json`, and the raw evidence
  JSONs under `artifacts/raw/` **are** committed.
- **Version pin note:** this pack tests **3.3.2** specifically on **JDK 26.0.1**; behavior on
  Tika 2.x or other JDKs is not claimed.
