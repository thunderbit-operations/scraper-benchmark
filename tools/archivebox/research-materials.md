# ArchiveBox — evidence & research materials

Tool: **ArchiveBox v0.7.4** (`archivebox/archivebox:latest`,
`sha256:1a5a3733…`), self-hosted web archiver. Queue focus (verbatim): *"Measure
which redundant preservation outputs are useful and where they fail."*

Every number below traces to a script in `tests/` and a JSON artifact under
`artifacts/raw/`. Confidence is tagged per finding. Findings use neutral IDs; no
self-evaluative adjectives. Novelty is classified against the ArchiveBox source
(read inside the image) and public docs.

---

## Design in one paragraph

A local fixture serves two structurally identical pages with four planted,
greppable tokens whose *visibility* differs: **STATIC** (`STATICTOKENq7w8e9`,
visible article text in the initial HTML of both pages), **RUNTIME**
(`RUNTIMETOKENr4t5y6`, injected into the article DOM by JS — assembled from
fragments so the contiguous string appears in **zero** served bytes; verified
`contiguous_runtime_token_count=0` on `/dynamic`, `/static`, `/static/app.js`),
**JSLIT** (`JSLITTOKENu1i2o3`, a literal inside `app.js` — in the JS bytes, never
rendered), and **BOILER** (`BOILERTOKENa1s2d3`, in nav/aside/footer). A contiguous
match on RUNTIME therefore *proves* the output captured the JS-materialised DOM.
ArchiveBox archives each page with all extractors; the harness reads each output
file and records which tokens survived.

---

## FINDING-01 — the redundant outputs do NOT preserve the same content (capture matrix)

**Confidence: triple-run reproduced** (`token_matrix_identical_across_runs: true`,
3 runs). Source: `artifacts/raw/full-matrix.json`.

`/dynamic` page, all extractors on, per-output token capture (`Y`=token present in
that output's file, `.`=absent):

| output | ArchiveBox status | STATIC | RUNTIME | JSLIT | BOILER | bytes | kind |
|---|---|:--:|:--:|:--:|:--:|--:|---|
| wget (mirror+WARC) | succeeded | Y | **.** | **Y** | Y | 8504 | byte mirror |
| singlefile | succeeded | Y | **Y** | . | Y | 1071 | rendered HTML |
| dom | succeeded | Y | **Y** | . | Y | 1131 | rendered HTML |
| pdf | succeeded | Y | **Y** | . | Y | 34546 | visual + text layer |
| screenshot | succeeded | — | — | — | — | 40346 | pixels (not text-greppable) |
| readability | succeeded | Y | **Y** | . | . | 144 | article text |
| mercury | succeeded | Y | **.** | . | . | 80 | article text |
| htmltotext | *(history `[]`)* | Y | **Y** | . | Y | 281 | page text |

The outputs split into distinct preservation classes and **no single output
captures all four token classes** — `wget` (the byte-mirror) is the only one that
keeps `JSLIT` while missing `RUNTIME`. (At this 4-token granularity
`{dom, singlefile, pdf, htmltotext}` share the same set `{STATIC, RUNTIME, BOILER}`;
they still diverge in byte content — script inlining, `kind`, size.) Reading the
column, on a dynamic page:

- **RUNTIME** (JS-injected content) is preserved by `{singlefile, dom, pdf,
  readability, htmltotext}` and **missed by `{wget, mercury}`** (screenshot renders
  it visually but is not text-recoverable here).
- **JSLIT** (a URL/string that only lives in `app.js`) is preserved **only by
  wget/WARC** — the one output everyone assumes is the "weakest". The rendered
  captures (singlefile/dom) drop it because SingleFile/Chrome-DOM don't serialise
  the fetched script body as text.
- **BOILER** separates whole-page captures (`wget/singlefile/dom/pdf/htmltotext`
  keep it) from article extractors (`readability/mercury` strip it).

So "redundant copies" is misleading: each output has a *different* preservation
profile. The two you'd expect to be interchangeable article extractors
(readability, mercury) disagree on the exact content that matters on a dynamic
page.

**Novelty:** `DOCUMENTED` that wget is static and chrome renders JS (common
knowledge / docs). `EXCLUSIVE` = the quantified per-output × per-token-class matrix
on controlled ground truth (no published measurement plants static/runtime/js-literal/
boilerplate tokens and reports which output keeps which).

---

## FINDING-02 — mercury ≠ readability because mercury re-fetches the URL (article extractors diverge)

**Confidence: reproduced + source-cited + server-side attribution.** Sources:
`full-matrix.json`, `mercury-isolation.json`, image source
`/app/archivebox/extractors/{mercury,readability,title}.py`.

Both are "reader-friendly article text" extractors, yet on `/dynamic` readability
keeps RUNTIME and mercury drops it (FINDING-01). Root cause, from source (v0.7.4):

- `readability.save_readability()` calls `document = get_html(link, out_dir)` and
  pipes the **local saved capture** into Mozilla Readability. `get_html()` in
  `title.py` reads, in order, `sources = [dom_path, singlefile_path, wget_path]` —
  the recorded `readability` command confirms it reads a local temp file (a copy of
  the DOM/singlefile capture), so it inherits the rendered DOM including the
  injected node.
- `mercury.save_mercury()` builds `cmd = [MERCURY_BINARY, link.url, ...]` — it hands
  the parser the **URL**, and `@postlight/parser` fetches it itself over plain HTTP
  (no JS).

Server-side fetch attribution (single-extractor configs, hits on `/dynamic`):

| config (only this extractor on) | `/dynamic` fetches |
|---|:--:|
| `mercury_only` | **2** |
| `readability_only` (+wget as its input) | 1 (the wget input fetch; readability itself = 0) |
| `wget_only` | 1 |

`mercury_only` hits `/dynamic` twice with nothing else enabled → mercury does its
own fetching, independent of ArchiveBox's rendered captures. `readability_only`
produces no fetch of its own (its single hit is wget fetching the input).

**Novelty:** the mechanism (input paths) is `DOCUMENTED-in-source`; the measured
behavioural divergence on dynamic content + the fetch-count attribution is
`EXCLUSIVE` quantification.

---

## FINDING-03 — the redundancy is a dependency tree, not N independent copies (inherited coverage)

**Confidence: reproduced (adversarial config).** Source: `nochrome.json` vs
`full-matrix.json`.

Because readability / htmltotext / title all read `get_html()` (dom > singlefile >
wget), their dynamic-content coverage is **inherited** from whichever chrome-based
capture succeeded — not their own. Disabling all chrome extractors
(`SAVE_DOM/SINGLEFILE/PDF/SCREENSHOT=False`) makes them silently fall back to the
wget HTML:

| output | RUNTIME with chrome ON | RUNTIME with chrome OFF | bytes ON→OFF |
|---|:--:|:--:|:--:|
| readability | Y | **.** | 144 → 95 |
| htmltotext | Y | **.** | 281 → 230 |
| mercury | . | . | 80 → 80 |
| wget | . | . | (mirror) |

With chrome off, **no** output captures the runtime content — readability and
htmltotext degrade silently (still `succeeded`, smaller file, missing content).
Their apparent independence in FINDING-01 was borrowed from the chrome layer. This
is the sense in which "if one method fails, another preserves it" is only partly
true: the article/text extractors do not independently re-render — they consume the
chrome capture, so a chrome failure removes dynamic content from *four* outputs at
once (dom, singlefile, readability, htmltotext), leaving only the static wget bytes.

**Novelty:** `DOCUMENTED-in-source` mechanism (`get_html` precedence, with an inline
comment even explaining the dom-over-singlefile ordering); `EXCLUSIVE` = the
demonstrated silent degradation + which outputs collapse together.

---

## FINDING-04 — static vs dynamic: same tool, opposite redundancy verdict

**Confidence: reproduced.** Source: `full-matrix.json` (`static` vs `dynamic`).

On the **static** page the whole-page captures are genuinely redundant — `wget`,
`singlefile`, `dom`, `pdf`, `htmltotext` all capture exactly `{STATIC, BOILER}`
(and readability/mercury `{STATIC}`). On the **dynamic** page the same set diverges
precisely at the JS boundary: `wget = {STATIC, JSLIT, BOILER}` vs `singlefile/dom =
{STATIC, RUNTIME, BOILER}`. So the "how many redundant copies do I have" answer is
page-dependent: near-total overlap on static pages, and a three-way split
(byte-mirror vs rendered vs article-text) on dynamic pages.

---

## FINDING-05 — redundancy has a fetch cost: the same page is fetched ~8× per archive

**Confidence: measured (server-side counter).** Source: `full-matrix.json`
`server_hits`.

Archiving one URL with all extractors on fetched `/static` **8×** and `/dynamic`
**8×** (plus `app.js` 5×) from the origin — each fetching extractor (wget + the four
chrome renders + mercury + headers + a probe) pulls the page independently; the
non-fetching extractors (readability/htmltotext/title) reuse the local capture. So
"redundant preservation" also means ~8× origin load per archived page, a cost not
usually stated alongside the "multiple copies" selling point.

**Novelty:** `EXCLUSIVE` quantification (the per-archive origin fetch multiplier).

---

## FINDING-06 — PDF preserves runtime content as an extractable text layer; screenshot is visual-only

**Confidence: measured (pypdf).** Source: `full-matrix.json` `pdf.text_method:
pypdf`.

`output.pdf` (Chrome print-to-PDF) carries a real text layer: pypdf extracts
`STATIC`, `RUNTIME`, `BOILER` (not `JSLIT` — scripts aren't printed). So PDF is a
full-page **and** text-recoverable capture of the rendered DOM. `screenshot.png` is
pixels — it renders the same content visually but is not machine-recoverable text
(OCR is out of scope here); the harness records it as visual-only rather than
claiming a false miss.

---

## FINDING-07 — robustness on HTTP 500: clean exit, but "succeeded" ≠ content preserved

**Confidence: measured.** Source: `robustness.json`.

Archiving the intentional `/failure/500` route exits cleanly (`add` rc=0, snapshot
created) and does not abort. Per-extractor: `wget`, `mercury`, `archive_org`
**failed**, while `dom`, `singlefile`, `pdf`, `screenshot`, `readability`, `title`,
`favicon`, `headers` **succeeded** — because Chrome renders the 500 *error body* as
a page and those extractors capture it. So an extractor status of `succeeded` on a
snapshot does not mean the intended content was preserved; it can mean the error
page was faithfully archived. Status is a run-outcome, not a content-validity
signal.

---

## Minor observation (not a headline) — htmltotext is not journaled

`htmltotext.txt` is produced with correct content on every page, but the snapshot's
`index.json["history"]["htmltotext"]` is an empty list `[]` (no run record) in
v0.7.4 — so an index/history-based status check reports htmltotext as never-run
while its output exists. Flagged as an observation only; **not** verified against the
upstream issue tracker, so no novelty claim.

---

## Default extractor set (v0.7.4)

`artifacts/raw/defaults.json`: on a plain `init`, **all** content extractors are
default-ON — `SAVE_WGET/SINGLEFILE/DOM/PDF/SCREENSHOT/READABILITY/MERCURY/
HTMLTOTEXT/TITLE/FAVICON/HEADERS/GIT/MEDIA = True` (`SAVE_ARCHIVE_DOTORG` reads
empty but ran in the smoke add). Several older guides list `pdf`/`screenshot` as
off-by-default; in v0.7.4 they are on. (`DOCUMENTED` — current config, noted because
common guidance is stale.)

---

## Novelty summary

| Finding | Mechanism | Measurement |
|---|---|---|
| F01 capture matrix | DOCUMENTED (wget static / chrome renders) | **EXCLUSIVE** (4-token × 8-output matrix on ground truth) |
| F02 mercury re-fetches | DOCUMENTED-in-source (`mercury.py` passes URL) | **EXCLUSIVE** (divergence + fetch attribution) |
| F03 inherited coverage | DOCUMENTED-in-source (`get_html` precedence) | **EXCLUSIVE** (silent degradation, which outputs collapse) |
| F04 static vs dynamic | — | **EXCLUSIVE** (opposite redundancy verdict) |
| F05 ~8× fetch cost | — | **EXCLUSIVE** (origin fetch multiplier) |
| F06 pdf text layer / screenshot visual | DOCUMENTED (chrome outputs) | measured (pypdf) |
| F07 500 = clean but status≠content | — | **EXCLUSIVE** (status semantics) |

---

## Part-6 self-check (worker, pre-audit)

1. **Winner sentences vs own table** — no "best output" is crowned; F01 is a
   per-token profile, not a ranking. Byte sizes are reported without faster/bigger
   value language.
2. **Claimed verifications have artifacts** — every table cites a
   `artifacts/raw/*.json`; the mercury/readability mechanism cites the in-image
   source files by path; fetch attribution is a counter in `mercury-isolation.json`.
3. **Instrument calibrated first** — the RUNTIME token was verified absent from all
   served bytes (`contiguous_runtime_token_count=0`) *before* trusting a match as
   proof of runtime capture. The PDF path was cross-checked: stdlib zlib could not
   decode the CID-font text, so pypdf is used and disclosed.
4. **Attribution ruled out fixture/harness** — the first matrix falsely showed wget
   capturing RUNTIME; root-caused to a JS **comment** that contained the token
   contiguously (a fixture bug), fixed, re-verified zero served bytes. The
   `htmltotext not-run` reading was checked against the raw history (`[]`, genuine)
   before reporting, and kept out of the headline.
5. **Novelty tags + adjective lint** — every finding carries a novelty class;
   mechanisms that come from source are labelled DOCUMENTED-in-source, not exclusive.
   No `honest/independent/strongest/trustworthy` self-adjectives in this pack.

## Gaps / not tested

- No public real-world target (local fixture only, by design/compliance); the
  runtime-capture boundary is corroborated only on the controlled fixture.
- Screenshot content verified only as "rendered a non-trivial image" (40 KB), not
  OCR'd.
- Timing is observational single-run, not a distribution; not used for any claim.
- `media` (yt-dlp), `git`, `archive_org` not exercised for content (disabled /
  offsite); only their run-status appears (robustness run).
- htmltotext journaling quirk not confirmed against the upstream issue tracker.
