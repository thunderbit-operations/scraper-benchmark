# ArchiveBox evidence pack — independent validation

**Auditor:** independent Fable-role reviewer (Opus, fresh context, adversarial /
default-skeptical). **Date:** 2026-07-24. **Scope:** ArchiveBox v0.7.4
(`archivebox/archivebox:latest`, digest `sha256:1a5a3733…`), Docker 29.2.1 on
colima, macOS arm64. Only the source pack under `tools/archivebox/` was touched;
the re-run ran in an isolated `$HOME` copy and was deleted afterward.

## Verdict: **PASS-WITH-FIXES**

Every headline in the pack **reproduces exactly** on an independent, clean re-run
(new container spawns, new fixture port, no cached data). The measured matrices,
fetch counters, statuses and origin-hit counts are byte-for-byte identical to the
committed artifacts (only volatile PDF/screenshot/wget byte-sizes wobble, none of
which supports a claim). Novelty tags are disciplined, nothing is hardcoded, and the
publish-bound files carry no secrets or host paths. **One required fix** (a
self-contradictory sentence in FINDING-01) was found and **has been applied** — see
below. With that correction the pack is sound.

---

## Independent reproduction (I re-ran the harness myself, did not trust self-report)

Method: copied `tests/{fixture_server,run_matrix}.py` into `~/archivebox-audit-rerun`
(colima shares `$HOME`, not `/private/tmp`), fresh `.venv` + `pypdf 6.14.2`, ran
`run_matrix.py --repeat 0` against the stock image. Compared token booleans /
statuses / server-hit counters to the pack's `artifacts/raw/*.json`.

### Capture matrix (H1) — reproduced identically

`/dynamic`, all extractors on, token+status **identical to `full-matrix.json`**
(both `/dynamic` and `/static`). Independent-run token-set groups on `/dynamic`:

| token set captured | outputs |
|---|---|
| `{STATIC, RUNTIME, BOILER}` | dom, singlefile, pdf, htmltotext |
| `{STATIC, JSLIT, BOILER}` | wget (byte-mirror) |
| `{STATIC, RUNTIME}` | readability |
| `{STATIC}` | mercury |
| `{}` (visual-only) | screenshot |

Confirmed: RUNTIME kept by `{singlefile, dom, pdf, readability, htmltotext}`, missed
by `{wget, mercury}`; JSLIT kept **only** by wget; BOILER separates whole-page from
article extractors. `server_hits` `/dynamic:8 /static:8 app.js:5 favicon:6` —
identical. **No single output captures all four token classes** (max = 3).

### RUNTIME token = 0 served bytes (instrument calibration) — verified

I started the fixture on a private free port and fetched every route directly. The
contiguous `RUNTIMETOKENr4t5y6` appears **0 times** in `/static`, `/dynamic`, and
`/static/app.js`; only the fragments (`RUNTIME`, `r4t5`, `fromCharCode(54)`) appear,
and only on `/dynamic`. `JSLIT` lives solely in `app.js`. → a contiguous RUNTIME
match genuinely **proves** JS-DOM capture; wget cannot have "falsely captured" it.
The worker's self-reported JS-comment-leak fix is **real** — the current fixture is
clean.

### mercury ≠ readability fetch attribution (H2) — reproduced + source-verified

Fetch counters **identical** to `mercury-isolation.json`: `mercury_only /dynamic=2`,
`wget_only /dynamic=1`, `readability_only /dynamic=1`. With nothing else enabled,
mercury hits the origin itself (2×) → it re-fetches the raw URL over plain HTTP (no
JS), which is why it misses RUNTIME; readability adds **0** fetches beyond its wget
input. Source read from inside the image confirms the mechanism:
`mercury.py` L65-67/L82-84 `cmd = [MERCURY_BINARY, link.url, …]`; `readability.py`
L57 `document = get_html(link, out_dir)` piped through a local temp copy; `title.py`
`get_html` L71 `sources = [dom_path, singlefile_path, wget_path]` with the documented
dom-over-singlefile comment. The counter directly supports the attribution.

### Inherited coverage (H3) & robustness (H4/500) — reproduced identically

NOCHROME: readability `144→95` and htmltotext `281→230` bytes, both **lose RUNTIME**
(still `succeeded`), dom/singlefile/pdf not-run — identical to `nochrome.json`. 500
route: `rc=0`, snapshot created, wget/mercury/archive_org `failed` while chrome
extractors `succeeded` on the error body — extractor-status maps identical to
`robustness.json`. defaults.json also reproduced byte-identical (all extractors,
incl. pdf/screenshot, default-ON).

---

## Four miss-classes (adversarial sweep)

**1. Blind instrument / mis-attribution.** *Cleared.* The single biggest risk —
wget "falsely" showing RUNTIME via a token leak in served bytes — is closed: I
independently measured 0 contiguous RUNTIME bytes across all routes, and wget's
RUNTIME=false reproduces. The mercury re-fetch attribution is backed by a
server-side counter (2 vs 1), not narration.

**2. Self-contradictory winner sentence.** *One found → fixed.* FINDING-01 stated
"**No two outputs have the same token set**", but its own table (and my re-run) shows
`{dom, singlefile, pdf, htmltotext}` all capturing the identical set
`{STATIC, RUNTIME, BOILER}`. The substantive thesis (outputs are *not*
interchangeable; three-way byte-mirror/rendered/article split; no output keeps
everything) is true and unaffected, but that specific sentence was false. **Applied
fix** (see Required fixes). No "full-redundancy" overclaim exists to be punished —
the pack argues the opposite, and correctly: no output holds `RUNTIME`+`JSLIT`
together.

**3. Claim without artifact.** *Cleared.* Sampled claims all trace to a field:
wget-misses-RUNTIME → `full-matrix…wget.tokens.RUNTIME=false`; mercury-2× →
`mercury-isolation…mercury_only["/dynamic"]=2`; readability 144→95 →
`full-matrix` vs `nochrome`; 500 statuses → `robustness.extractor_statuses`; ~8×
fetch → `full-matrix…server_hits./dynamic=8`. The source-mechanism claims cite exact
file+line, which I verified in the image.

**4. Over-reaching attribution.** *Minor, acceptable.* The "~8× = wget + 4 chrome +
mercury + headers + probe" per-extractor split is an explanation, not a per-extractor
measurement (the counter only proves the total 8); it is framed as explanation and
the number is measured. The htmltotext "not journaled" quirk is explicitly **not**
given a novelty claim and kept out of the headline — appropriately conservative.

---

## Novelty (Gate 1)

Correctly classified. Mechanisms that come from docs/source are labelled
`DOCUMENTED` / `DOCUMENTED-in-source` (wget-static/chrome-renders; mercury passes
URL; `get_html` precedence — all three I confirmed in the image). Only the
*quantifications* are `EXCLUSIVE`: the 4-token × 8-output ground-truth matrix, the
fetch-count attribution, silent chrome-off degradation, the static-vs-dynamic
reversal, and the ~8× origin multiplier — these are genuine measurements no public
source reports. Note: I did not re-verify the cited GitHub issue numbers (#1689 etc.)
via web, but the EXCLUSIVE claims rest on measurements, not on those issues.

## Anti-hardcoding (Gate 3)

Passes, and now empirically: every result field is computed at runtime
(`_grep_tokens` = `token.encode() in data`, statuses from `index.json["history"]`,
sizes from `os.path.getsize`, fetches from a server-side `Counter`,
`token_matrix_identical_across_runs` from `all(m==base …)`). An independent process
produced identical numbers — proof they are measured, not baked-in conclusion
strings.

## Secret / abspath scan

Clean. No `/Users/richardli`, no `/home/`, no host paths in artifacts (redacted to
`~`; `/var/folders` appears only inside the redaction regex, `/private/tmp` only in
prose explaining the colima constraint). No token/key/password/secret material.
Pack = **100K**, exactly `{README, 3 briefs, scorecard, 5 JSON, 2 test .py,
.gitignore}` — **no `data/`, no `archive/`, no image, no `.venv`** committed
(`.gitignore` covers them). Note (cosmetic): artifact snapshot paths read
`~/Documents/claude/scraper-benchmark/…` (project since renamed) — harmless,
already redacted.

---

## Required fixes

1. **[APPLIED] FINDING-01 false sentence.** "No two outputs have the same token set"
   contradicts its own table (`{dom, singlefile, pdf, htmltotext}` all =
   `{STATIC, RUNTIME, BOILER}`). Replaced with an accurate statement: the outputs
   split into distinct preservation classes, **no single output captures all four
   token classes**, wget uniquely keeps JSLIT while missing RUNTIME, and the four
   coinciding outputs still diverge in byte content. Thesis and score unchanged; only
   the over-general wording was corrected. (Edit made in
   `research-materials.md`; headline/scorecard untouched — they never contained the
   claim.)

## Not re-verified (disclosed)

- GitHub issue numbers in the pretest (no web fetch performed in this audit).
- The `-e SAVE_*` ignored / `config --set` persists reproducibility note (a
  disclosed caveat, not a scored claim).
- Screenshot content (visual-only, correctly recorded as non-greppable, not a miss).
