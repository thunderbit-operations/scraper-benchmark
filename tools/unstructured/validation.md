# unstructured — Independent Audit (validation)

**VERDICT: PASS WITH FIXES.** Every numeric headline reproduced independently on a clean
re-run of the pack's own harness (unstructured **0.24.1** / Python **3.12.13**, macOS
arm64, pack `.venv`). The fixtures are code-generated (deterministic, byte-identical), the
classification metrics are computed-not-hardcoded and reproduce byte-for-byte, the BLOCKED
PDF/OCR paths are honestly labeled with **no faked numbers**, the H5 docx-bullet refutation
is real, and both self-reported harness fixes are correct and non-inflating. **One
required fix is NOT cosmetic:** FINDING-02's *mechanism* (the "12-word Title cliff") is
**misattributed** — the measured phenomenon and the 0.833 Title-recall number are correct,
but the stated cause is wrong (it is the verb requirement, not the word-count limit). That
touches a headline + an EXCLUSIVE novelty tag, so it is **routed back to the worker**, not
edited here. Two further cosmetic flags. Nothing auto-edited; original artifacts restored;
`.venv`/`.docx` not shippable.

Reproduction environment: pack `.venv` (Python 3.12.13, unstructured 0.24.1, python-docx
1.2.0, Python-Markdown 3.10.2, lxml 6.1.1; standalone `nltk` **not** installed — vendored
`unstructured/nlp/tokenize.py` used, matching the metadata claim). tesseract / poppler
(`pdftoppm`) / libmagic all confirmed **absent** on this host, exactly as the pack states.

---

## Independent reproduction (my re-runs)

I re-ran the full pipeline in the pack's layout: `build_fixtures.py` → `run_partition.py`
→ `metrics.py`. (`resource_cost.py` was not re-run — its committed numbers already round
to the reported table and re-running only perturbs timing; the RSS band is the stable
signal.) Then I restored the four original artifact JSONs from backup.

### Fixture determinism (code-generated ground truth) — CONFIRMED
`build_fixtures.py` regenerated all 17 committed text/JSON fixtures **byte-identical** to
the committed copies (`diff -q` clean on every `*.html`/`*.md`/`*.txt` and
`ground_truth.json`). The ground truth is emitted with the bytes in one deterministic pass
— there is no room for a hand-tuned label that drifts from the rendered document. The 7
`.docx` are regenerated (zip-internal timestamps vary; gitignored; only extracted elements
are asserted) — correct as documented.

### Classification metrics (anti-hardcoding split) — CONFIRMED byte-identical
After my fresh `run_partition.py` + `metrics.py`:
- `cross_format.json` — **byte-for-byte identical** to committed.
- `metrics.json` — **identical modulo the `computed_at` timestamp**.
- `partition_raw.json` — element streams `(category, class, text)` + determinism
  **identical** (modulo per-run `elapsed_ms`/timestamps).

Every headline value re-derived from the raw stream matches the research tables exactly:

| Format | Title | NarrativeText | ListItem | Table |
|---|---|---|---|---|
| html | 1.000 (6/6) | 0.857 (6/7) | 1.000 (10/10) | 1.000 (1/1) |
| md | 1.000 (6/6) | 0.857 (6/7) | 1.000 (10/10) | 1.000 (1/1) |
| txt | **0.833 (5/6)** | 0.857 (6/7) | 1.000 (10/10) | **0.000 (0/1)** |
| docx | 1.000 (6/6) | 0.833 (5/6) | 1.000 (5/5) | 1.000 (1/1) |

Cross-format agreement reproduced: d1_canonical **1.000 (11 elements identical across all
four carriers)**, d2_table 0.667 (txt outlier, 5 vs 3 elements), d3_adversarial 0.800
agree / 0.600 match-intent, d4_shortlist_mdblank 1.000, d7_large 1.000 (660 each). Directly
from the raw stream I confirmed: d3-over → Title in html/md/docx, NarrativeText in txt;
d3-verbless → UncategorizedText in **all four**; d2-tab → Table in html/md/docx, **Title**
in txt (the row `zztblcell alpha  120`).

**Anti-hardcoding lint: PASS.** `run_partition.py` emits only raw category/class/text +
counts + a 3-rep determinism check — grep finds no recall/precision/confusion logic in it.
`metrics.py` computes every P/R/agreement value from raw category vs labels; no metric
constant is written by hand. The runner/metrics scripts contain **no** `0.833`/`0.857`/
`1.000`-type result literals.

### Determinism (FINDING-08) — CONFIRMED
All **23** (doc, format) runs returned an identical `(category, text)` sequence across 3
reps (`all_identical == true` for every entry; 0 non-deterministic).

### H5 docx-bullet refutation — CONFIRMED REAL (honest falsification)
Re-derived from raw: `List Bullet` **style**, `numPr`-only, and manual `"- "` dash
authorings **all** yield ListItem recall **1.000 (5/5)**. The historical #768/#1320
"docx bullets → NarrativeText" complaint genuinely does **not** reproduce on 0.24.1. This
is a real measured refutation of a KNOWN-ISSUE, not powder — correctly reported as
`[refuted]`.

---

## BLOCKED honesty (four-class leak: BLINDED-INSTRUMENT / SCOPE) — HONEST

Verified on-host, not taken on faith:
- `tesseract` and `pdftoppm` (poppler) → **not found**; `magic.Magic()` → "failed to find
  libmagic". Exactly as the pack records.
- `partition_pdf` is **unimportable** here: I reproduced `ModuleNotFoundError: No module
  named 'unstructured_inference'` at module load — so even `strategy="fast"` cannot run.
  `unstructured_inference` and `torch` are both absent. The pack's core claim (the whole
  PDF/OCR/hi_res surface is BLOCKED) is **true and reproduced**.
- **No PDF/OCR performance number exists anywhere** in the pack — grep confirms only
  BLOCKED/absent statements. Scope (HTML/md/txt/docx only) is stated prominently in
  README, scorecard, metadata, research, and pretest. This is a model BLOCKED-honesty case.

**Cosmetic caveat (COS-1):** the *pretest* (pretest-information-gain.md ~L39) cites the
module-load import as `from unstructured_inference.inference.layout import DocumentLayout`,
"pdf.py ~L84." That specific line is under `if TYPE_CHECKING:` and does **not** execute at
runtime. The real runtime failure is pdf.py L55 → `pdf_image/pdfminer_processing.py` L11
(`from unstructured_inference.config import inference_config`). The **conclusion is
unaffected** (partition_pdf still hard-imports unstructured_inference at module load), and
metadata/research do not cite the wrong line — only the pretest's line reference is off.

---

## The two self-reported harness fixes — BOTH CORRECT AND NON-INFLATING

1. **Zero-padded prefix-free sentinels (false SPLIT/MERGE).** d7_large sentinels are
   `{base}z{r:03d}` (e.g. `zztitle1z000`). I verified: 660 sentinels, **0 substring
   collisions**, and d7_large per-doc outcomes contain **no** DROPPED/MERGED/SPLIT in any
   format (recall 1.000 for Title/NarrativeText/ListItem). The fix works and does not mask
   a real error — d7 is a genuine canonical×60 clean doc, so 1.000 is the correct answer.

2. **Case-insensitive sentinel match (ALL-CAPS blindness).** `_contains` lowercases both
   sides. I confirmed the **only** uppercased sentinel occurrence in any fixture is
   `ZZCAPS` (d3-caps). So the relaxation changes exactly one match, and it is a **true**
   match — the element genuinely *is* the caps heading `SYSTEM ZZCAPS CONFIGURATION GUIDE`.
   It cannot inflate recall (sentinels are unique disjoint tokens; no block's text contains
   another's sentinel even case-folded), and it applies uniformly to all four formats —
   without it, d3-caps would be DROPPED **everywhere**, understating Title recall in every
   carrier, not just txt. The fix corrects a real blindness fairly, in neither direction
   favouring a particular format.

---

## Annotation fairness spot-check (the audit core) — FAIR, tilted harsh-on-tool

Labels are code-generated (audited via the generator, which reproduces byte-identical).
Spot-checked 6 blocks against `ground_truth.json`:
- **d3-verbless** (verbless noun phrase) labeled **NarrativeText** (its human intent) →
  tool returns UncategorizedText → **counted as a MISS** (NarrativeText 6/7). Harsh on the
  tool, not lenient.
- **d3-over** (heading) labeled **Title** → txt returns NarrativeText → **counted as a
  MISS** (txt Title 5/6). Harsh.
- **d2-tab** labeled **Table** → txt returns Title → **counted as a MISS** (txt Table 0/1).
  Harsh.
- **d3-nonalpha** (`… 12.5% :: 40/60 >> $$$ …`) labeled **UncategorizedText** → matches.
  This is the one label that *helps* the tool, but it is genuinely non-prose (non-alpha
  ratio > 0.5) so UncategorizedText is the defensible type, and the pack **discloses** the
  choice ("not scored as a NarrativeText miss"). Not gaming.
- **d1 canonical** titles/narratives/bullets carry their obvious intended types; narratives
  are real verb-bearing English so NarrativeText is earned, not gamed by gibberish.
- **d3-caps** labeled Title, correct everywhere.

No block is mislabeled to inflate recall; the one generous label is defensible and
disclosed. **Ground truth is fair and, on the adversarial axis, tilted against the tool.**

---

## REQUIRED FIX (non-cosmetic, routed to worker)

### FIX-1 — FINDING-02 mechanism is MISATTRIBUTED ("12-word Title cliff" is not what fires)

**The number and the phenomenon are correct; the stated cause is wrong.** FINDING-02 /
the README Title bullet / the scorecard Title note all claim d3-over is demoted to
NarrativeText in txt **because it exceeds `title_max_word_length = 12`** ("the 12-word limit
demotes it," "located exactly at the documented boundary"). It is not.

In the pure-heuristic txt path, `_text_to_element` (installed text.py) evaluates
`is_possible_narrative_text` at **L149** *before* `is_possible_title` at **L155** — the very
dispatch order the pack's **own** `metadata-snapshot.md` documents. d3-over's sentence
("This … heading deliberately **contains** … words **exceeding** the configured limit")
carries finite verbs, so it satisfies `is_possible_narrative_text` and is typed
**NarrativeText** — the 12-word title check is never reached. I verified directly (pack
`.venv`):
- d3-over fixture (13w, has verbs) → **NarrativeText** (`narr=True`, `title=False`).
- a **5-word** heading *with* a verb → **NarrativeText** (well under 12 words — the word
  limit is irrelevant).
- a **verbless** 13-word noun-pile → **UncategorizedText** (`narr=False`, `title=False`) —
  i.e. the *actual* over-12 path lands in UncategorizedText, **not** NarrativeText.
- truncating the fixture to 12 or 11 words still → **NarrativeText** (verb still fires).

So the finding is internally self-refuting: if the 12-word limit were the cause, the result
would be **UncategorizedText**, not NarrativeText. The NarrativeText outcome *proves* it is
the verb path. FINDING-02 is therefore a corollary of **FINDING-04's verb requirement**
(applied to a heading) plus the structural tag/style override — **not** an independent
"12-word cliff." The chosen fixture never isolates the word-count boundary (the pretest's
planned test #6 "word 12/13 boundary" and #21 "env override" were not actually delivered).

**What must change (worker, not me):**
1. Rewrite the txt mechanism in FINDING-02, the README Title bullet, and the scorecard
   Title-recall note: the txt demotion of this heading is driven by the **verb requirement**
   (narrative-before-title ordering), not the word-count limit; structural carriers hold
   Title because the `<h1>`/Heading style short-circuits the heuristic.
2. Reconsider the **EXCLUSIVE** tag on "12-word Title cliff (tag-suppressed)." The
   surviving, real contribution is the **structural-override** demonstration (same block
   types differently by carrier) + the verb effect — the word-count cliff is not shown.
   Either rebuild a verbless heading that crosses 12→13 words (Title→UncategorizedText) to
   actually demonstrate the cliff, or drop the "12-word" framing.

The Title-recall table (txt 0.833) and the cross-format numbers **stand** — only the causal
prose and one novelty tag need correction.

---

## COSMETIC FLAGS (writer, not blocking)

- **COS-1** — pretest PDF module-load line citation (pdf.py "~L84" is `TYPE_CHECKING`; real
  chain is L55 → pdfminer_processing.py L11). Conclusion unaffected. Details above.
- **COS-2** — self-eval-word lint surfaces only neutral usages: "format-independent"
  (a technical descriptor), README "Independent, reproducible tests" (methodology label),
  and "honest/honestly" section labels (process transparency). **No quality adjective is
  awarded to unstructured.** Same non-blocking posture as the reference pack; neutralize the
  transparency labels in the final blog draft.

---

## Other gates

- **Novelty three-classification — mostly disciplined, one tag affected by FIX-1.**
  Existence claims (heuristic typing, per-format mechanism, constants) → DOCUMENTED
  (correct); md short-list → KNOWN-ISSUE #3280; docx bullets → KNOWN-ISSUE→REFUTED (real,
  verified). EXCLUSIVE items are quantifications/demonstrations (confusion matrix,
  cross-format agreement, verb-requirement in all formats, md 6→1 collapse+blank-line
  isolation, RSS band) — all legitimately scoped, **except** the "12-word Title cliff"
  EXCLUSIVE, which FIX-1 requires reframing.
- **H4 attribution (md collapse = Python-Markdown, not unstructured) — CORRECT, not
  scapegoating.** I ran Python-Markdown directly on the lazy fixture: it folds the list into
  one `<p>` (**0 `<li>`**) before unstructured sees it; the blank-line variant recovers 5
  `<li>`. The root-cause attribution is backed by both the in-pack blank-line control and
  this direct upstream reproduction.
- **D1 self-contradicting winner — PASS.** No unqualified "unstructured classifies
  accurately" claim exists; the clean-content 12/12 is scoped to "structured and idiomatic,"
  NarrativeText precision is docked to 6/10 for the verbless limit, Table to 7/8 for the txt
  loss. Scorecard weights sum to **100**, scores to **80** (re-added). No sentence is
  contradicted by txt Table 0.0 / verbless-Uncat.
- **D2 blinded instrument — PASS.** The metric registers presence (recall 1.0) and absence
  (txt Table 0.0, md collapse 0.0), and the outcome flips across the constructed boundaries;
  sentinels are runtime-unique disjoint tokens, so a match requires the real extracted text.
- **Secret / abspath / cleanliness scan — CLEAN.** Zero `/Users/richardli` in any
  publish-bound file; the only `/var/folders` strings are in redaction *code*/prose;
  artifact JSONs and fixtures contain no host path (redaction effective); no
  `sk-`/`ghp_`/`AKIA`/`Bearer`/private-key patterns. `.venv/` (354M) and the 7 `.docx` are
  gitignored and were never in the publish set (no git repo under the pack — evidence phase).

---

## Residual gaps the writer must keep (the pack lists these)
1. All numbers are controlled synthetic fixtures, single machine / one version (0.24.1).
2. PDF / OCR / hi_res / `partition()` auto-sniff are BLOCKED and unscored — never imply
   otherwise.
3. Table *structure* (cell grid) is not measured — only `Table` presence.
4. Timing is not a cross-format race (single session, sibling-worker contamination) — the
   pack correctly refuses a faster/slower verdict; keep it that way.

---

_Audit re-ran `build_fixtures` → `run_partition` → `metrics` in the pack's own `.venv` on
2026-07-24; text fixtures + ground_truth rebuilt byte-identical, `cross_format.json`
byte-identical, `metrics.json` identical modulo `computed_at`, raw element streams
identical. Original artifact JSONs and `.docx` restored from backup afterward; `__pycache__`
removed; no stray files left._

**Net status: PASS WITH FIXES.** All numeric headlines reproduce; ground truth is
code-generated and fair (harsh-on-tool, not lenient); H5 refutation is real; BLOCKED
honesty holds with no faked PDF/OCR numbers; both harness fixes are correct and
non-inflating; H4 attribution is sound; anti-hardcoding, secret and abspath scans clean.
The one required change is **FINDING-02's mechanism misattribution** (measured phenomenon
correct, stated cause wrong — verb requirement, not the 12-word cliff), which touches a
headline and an EXCLUSIVE novelty tag and is **returned to the worker**, plus two cosmetic
writer-notes. Honesty over release.
