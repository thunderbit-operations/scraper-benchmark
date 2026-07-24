# apache-tika — Independent Audit (validation)

**VERDICT: PASS.** Every numeric headline reproduced independently on a clean re-run of the
pack's own harness (Apache **Tika 3.3.2**, jar sha256 `71ca551380e5eab1…`, **OpenJDK 26.0.1**,
macOS arm64, pack `.venv` = reportlab 5.0.0 / python-docx 1.2.0 / odfpy 1.4.1). The text
fixtures + ground-truth JSONs are code-generated and rebuild **byte-identical**; every recall /
MIME / metadata / robustness number is computed-not-hardcoded and reproduces byte-for-byte
(modulo the `computed_at` timestamp and one embedded log-clock string inside a POI exception
line — not a metric). The core H1 MIME-adversarial headline holds under an **independent**
from-scratch test. The worker's self-reported **D3 fix (CSV recall)** is correct and fair — it
corrects a fixture-coverage artifact, and I verified it does **not** mask any real Tika content
loss. No secret/abspath leak, no self-eval adjectives, jar/venv/binaries correctly excluded
(publish-bound set = 139,664 bytes ≈ 140 KB). **No required fixes; three cosmetic writer-notes
below.** Nothing edited in the pack; my re-run artifacts were restored to the committed copies.

Reproduction environment confirmed on-host, not taken on faith: `java -version` → OpenJDK
26.0.1; jar sha256 + size (66,978,444 B) match `metadata-snapshot.md` exactly; **tesseract /
poppler absent** (the BLOCKED OCR paths, correctly unscored — no faked OCR numbers appear
anywhere in the pack).

---

## Independent reproduction (my re-runs)

Ran the full pipeline in the pack's layout: `build_fixtures.py` → `run_tika.py` (131 JVM
cold-start invocations, ~61 s) → `metrics.py`, then restored the two committed artifact JSONs
from backup.

### Fixture determinism (code-generated ground truth) — CONFIRMED
`build_fixtures.py` regenerated all committed **text** carriers (`.html/.md/.txt/.xml/.rtf/
.csv`) and all three truth JSONs (`ground_truth.json`, `mime_truth.json`,
`robustness_truth.json`) **byte-identical** to the committed copies (`diff -q` clean on every
one). Ground truth is emitted together with the bytes in one deterministic pass — no room for a
hand-tuned label that drifts from the rendered document. The `.docx/.pdf/.odt` binaries and the
`mime/`+`robust/` adversarial trees are regenerated (non-deterministic zip/pdf internal
timestamps; gitignored; only their extracted text/metadata/detected-type is asserted) — correct
as documented.

### All derived numbers (anti-hardcoding split) — CONFIRMED byte-identical
After my fresh `run_tika.py` + `metrics.py`, `metrics.json` is **identical to committed except**
(a) the `computed_at` timestamp and (b) one embedded wall-clock inside the POI FATAL string
(`14:03:38,381` → `14:17:06,397`) — a log timestamp captured in raw stderr, not a computed
metric. Every recall/MIME/metadata/robustness value matched exactly:

| Arm | Reproduced result |
|---|---|
| Content recall | **1.000 on all 14 carriers**, `missing_sentinels = []` everywhere (incl. CSV 1/1) |
| MIME magic-bearing | **30/30 exact** (rate 1.000) |
| MIME magic-less | **10/18 collapsed to `text/plain`** (5 md + 5 csv; 6 txt cells never collapse, txt's true type *is* text/plain) |
| Metadata | author+title on 4/4 metadata-bearing carriers; `created` exact on DOCX+ODT |
| Robustness | empty + both truncated → exit 1 uncaught, empty stdout; `--detect` → exit 0 correct type on all three |
| Determinism | `determinism_text_identical = true` on all 14 carriers (3 reps byte-identical) |

**Anti-hardcoding lint: PASS.** `run_tika.py` dumps only raw observations (extracted text,
metadata dict, detected type, exit codes, exception line, 3-rep determinism flag). `metrics.py`
computes every recall/MIME/robustness value from that raw output vs the `*_truth.json` labels.
Grep for result-value literals (`0.833`/`0.667`/`30/30`/`10/18`/`= 1.0`) in either script →
**none**; the only numeric literals are structural (`range(3)`, `[:19]` ISO-compare, `round(…,4)`).

---

## H1 MIME-adversarial — INDEPENDENTLY REPRODUCED (the core headline)

Beyond re-running the harness, I built a **fresh** PDF from scratch (not the pack's fixture,
new sentinel `AUDIT_SENTINEL_9931`), copied its bytes under a **lying `.txt` extension** and a
**no-extension** name, and drove `java -jar tika-app --detect` directly:

- PDF renamed **`.txt`**, `--detect` **with filename** → `application/pdf` ✅
- PDF renamed **`.txt`**, `--detect` **from a filename-less stream** → `application/pdf` ✅
- PDF **no extension**, `--detect` with filename → `application/pdf` ✅

The lying `.txt` extension is ignored; magic bytes win. I also confirmed the magic-less
counterpart independently: the `.md` fixture detects `text/markdown` **with** its extension, but
**collapses to `text/plain`** the moment it is renamed `.pdf` or fed as a stream; and a DOCX
renamed `.jpg` stays the OOXML type. This is exactly the two-regime split the pack reports.

**Structure-blind / content-complete (H2) — CONFIRMED:** `--text` on the HTML carrier drops all
list markers and element typing (list items emerge as bare tab-indented text, no `- `/`1.`, no
Title/ListItem labels) while every sentinel survives (recall 1.000). Content-complete, structure
fully discarded — as claimed.

**H4 truncation reality — CONFIRMED genuine:** `truncated.pdf` is 512 B starting `%PDF-1.3`;
`truncated.docx` is 1024 B starting `PK\x03\x04`; `empty.txt` is 0 B. These are real truncations,
and `--detect` still returns the correct type on the two truncated binaries (header/magic
intact) while `--text` throws uncaught (`ZeroByteFileException` / `TIKA-198` / POI FATAL). The
detection-decoupled-from-parsing triage signal is real.

---

## D3 correction (CSV recall) — FAIR, and NOT masking a real loss (the audit core)

The worker self-reported fixing D3: an earlier CSV content-recall of **0.333** was a
**fixture-coverage artifact**, corrected via `blocks_by_format` rather than falsely accusing
Tika of dropping content. I scrutinized this specifically for reverse-masking (i.e., excusing a
genuine Tika loss as a "fixture artifact"). It is fair:

1. **The CSV fixture physically carries only the grid.** `render_csv` emits nothing but the
   table rows — I read the bytes: `Tool,Throughput` / `zztblcell_alpha,120` / `zztblcell_beta,95`.
   The title (`zztbltitle`) and narrative (`zztblnarr`) sentinels are **genuinely absent** from
   the CSV input (grep count 0). They were never rendered into a CSV, so scoring the CSV against
   them would penalize Tika for content that does not exist in the input — a fixture artifact,
   not a parser loss.
2. **The fix is narrowly scoped and disclosed.** `blocks_by_format["csv"] = ["t-tab"]` (table
   block only); **every other** carrier (html/md/txt/docx/xml) is still scored against all three
   blocks. The special-case is CSV-only and documented in `build_fixtures.py` + `metadata-snapshot.md`.
3. **It does not hide a real Tika drop.** I confirmed Tika's `--text` on the CSV genuinely
   emits both `zztblcell_alpha` and `zztblcell_beta` — so the 1/1 recall is a **true positive**.
   Had Tika dropped the grid, recall would read 0/1, not 1/1; the table block is still fully in
   scope. The correction removes phantom denominator entries, it does not paper over a loss.

This is the correct parallel to the methodology's D3 (soupsieve-type misattribution): the low
number was attributed to the harness/fixture only **after** verifying the tool actually extracts
what is present in the input. `metrics.py`'s recall alignment (`authored_ids =
blocks_by_format.get(fmt, …)`, scored by unique-sentinel substring membership) is fair to the
tool and consistent across carriers.

---

## Four-class leak review

- **Misattribution / blinded instrument — CLEAN (D3 above is the one at risk, and it is fair).**
  The recall metric registers both presence (1.0) and absence (it would show 0 for a missing
  sentinel — the robustness rows exercise the absent path). Sentinels are runtime-unique disjoint
  tokens, so a match requires the real extracted text. No instrument blindness.
- **Annotation fairness — FAIR, tilted honest/harsh-on-tool.** Ground truth is code-generated
  (rebuilt byte-identical). Metadata applicability is honest: PDF `created` is scored
  **presence-only, not exact**, because reportlab stamps `created = now` — I confirmed the raw
  PDF `dcterms:created` is this run's date (`2026-07-24T06:16:00Z`), **not** the embedded
  `2021-03-15`, and the pack does **not** claim PDF `created` recovery. DOCX/ODT `created` are
  the exact embedded 2021 value and score exact. txt/md/csv/rtf/xml carry no metadata layer and
  are marked non-applicable (a miss there would be asking for a field never written). No sample
  was cherry-picked for parse-friendliness beyond the disclosed synthetic scope (the PDF is a
  simple single-column text layer — explicitly scoped as "PDF text-layer", with real-corpus
  accuracy and OCR listed under Gaps).
- **Parity honesty — HONEST, appropriately deferred.** The Tika pack reuses the sibling
  `unstructured` sentinel-fixture design and contrasts qualitatively (Tika flattens → zero
  classification to lose, content-complete/structure-blind; `unstructured` classifies → loses on
  it; `unstructured`'s PDF path was torch-BLOCKED, Tika parses the PDF text layer natively via
  PDFBox). It does **not** fabricate a head-to-head number and explicitly flags "cross-tool
  synthesis is out of scope here; flagged for the parent." The `unstructured` torch-BLOCKED claim
  is corroborated by that pack's own validation. Honest contrast, no invented parity race.
- **No-artifact claim / self-contradicting winner — CLEAN.** Every "I verified/reproduced"
  statement maps to an executable script + committed raw JSON. The 83/100 is internally
  consistent: each strength is paired with its documented limit (magic-less docked 5/8, structure
  2/6, robustness 7/10). No "Tika parses perfectly" sentence exists that magic-less collapse or
  structure-blindness would contradict.

---

## Other gates

- **Novelty three-classification — CORRECT.** Every finding is tagged **DOCUMENTED
  mechanism/capability + EXCLUSIVE-QUANTIFICATION** (net-new measurement), and **nothing is
  crowned "undocumented"/独家 as a behavior**. The mechanisms are cited (detection order →
  detection.html; `text/markdown ⊂ text/plain`; `TextAndCSVParser` fallback → javadoc;
  `ZeroByteFileException`). The EXCLUSIVE tag is applied only to the quantified matrices /
  exit-code triage — a measurement-novelty claim, not a mechanism-exclusivity claim. This is the
  correct split; a documented capability is **not** miscast as exclusive.
- **Secret / abspath / cleanliness — CLEAN.** Zero `/Users/richardli` in any publish-bound file.
  The only `/var/folders`/`/private/var` hits are inside the **redaction code** (`run_tika.py`,
  `metrics.py`) and the redaction prose in `metadata-snapshot.md` — not leaked paths. Tika's
  `resourceName` in the artifacts is **basename-only** (`canonical.html`, …), confirming the
  pack's note that no absolute path appeared to begin with (redaction applied defensively, `<TMP>`
  never triggered). No `sk-`/`ghp_`/`AKIA`/`Bearer`/private-key patterns.
- **Self-eval adjective lint — CLEAN (cleaner than the sibling packs).** Grep for
  `honest|independent|strongest|trustworthy|flawless|perfect|best-in-class` across publish-bound
  md/py → **zero hits**. No quality adjective is awarded to Tika.
- **jar / venv / binaries excluded — CONFIRMED.** `.gitignore` excludes `vendor/`, `*.jar`,
  `.venv/`, the `.docx/.pdf/.odt` binaries, and the `mime/`+`robust/` trees. Publish-bound set =
  **139,664 bytes (~140 KB)**; no stray jar outside `vendor/`; the 67 MB jar is reproduce-only
  (URL + sha256 pinned). Evidence phase — no git repo under the pack, same as the `unstructured`
  pack.

---

## COSMETIC FLAGS (writer, non-blocking)

- **COS-1 — issue-tracker leg of novelty gate 1 is thinly evidenced.** The pretest's SERP/official
  scan cites documentation (detection.html, OPF blog, mime-type page, javadoc) but no explicit
  Apache Tika JIRA/GitHub **issue-tracker** search link. This does **not** rise to a required fix
  because no finding claims mechanism-exclusivity ("undocumented"); the strong "no public source
  tabulates this" quantification claim is self-evident by construction (a controlled ground-truth
  matrix is net-new). Still, add an issue-tracker zero-hit line to fully satisfy the three-source
  rule before the "no public source tabulates" phrasing goes to blog.
- **COS-2 — "list markers → literal `- `" is carrier-dependent.** Accurate for txt/md/rtf/pdf
  (where `- `/`1.` are authored as literal characters and survive), but in HTML/DOCX the `<li>` /
  List-Bullet style flattens to tab-indented text with **no** `- ` marker at all. Content survival
  (recall 1.0) is unaffected; only the parenthetical is imprecise. Tighten in the writeup.
- **COS-3 — magic-less denominator.** "10/18 magic-less cells collapse" counts 6 plain-text cells
  in the denominator that can *never* collapse (txt's true type **is** `text/plain`). FINDING-01
  discloses this explicitly ("Plain-text is `text/plain` everywhere — never a 'collapse'"), so it
  is honest, but a reader skimming the scorecard should note the 10 collapses come entirely from
  md (5) + csv (5). Consider stating "10/12 non-txt magic-less cells" alongside for clarity.

---

## Residual gaps the writer must keep (the pack lists these)
1. All numbers are controlled synthetic fixtures, single machine, one version (3.3.2 on JDK 26.0.1).
2. OCR / scanned-image PDF is BLOCKED (tesseract+poppler absent) and **unscored** — never imply otherwise.
3. Structure / table-grid / element-type classification is **not** a Tika capability and is out of scope (that is the `unstructured`/`docling` axis); Tika is scored on content survival + metadata + detection only.
4. CSV statistical detector tested only on a minimal 2×3 grid (FINDING-05 single-observation caveat); encrypted/recursive/huge-file/resource-cost axes not measured.

---

_Audit re-ran `build_fixtures` → `run_tika` → `metrics` in the pack's own `.venv` on 2026-07-24;
text fixtures + all three truth JSONs rebuilt byte-identical, `metrics.json` identical modulo
`computed_at` + one embedded log-clock string; the H1 PDF-renamed-`.txt` headline reproduced from
a fresh PDF outside the harness; the D3/CSV correction verified fair and non-masking. Original
committed `tika_raw.json` + `metrics.json` restored from backup; `__pycache__` and scratch test
files removed; the 67 MB jar left untouched and un-committed._

**Net status: PASS.** All numeric headlines reproduce; fixtures are code-generated and fair
(harsh-on-tool on metadata, honest on BLOCKED OCR); the MIME two-regime split is independently
confirmed; the D3/CSV fix is correct and hides no real loss; novelty tags are correctly scoped
(documented mechanism + net-new quantification, nothing miscast as exclusive); anti-hardcoding,
secret, abspath, and adjective scans are clean; jar/venv excluded (~140 KB pack). No required
fixes — three cosmetic writer-notes only. Honesty over release.
