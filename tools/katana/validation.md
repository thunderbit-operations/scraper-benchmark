# katana — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

Every headline claim reproduced independently in the pack's own `.venv` (katana
**v1.6.1** / Go 1.26.5 / Chromium build 1228 / Python 3.14.2 / macOS arm64). I
re-ran **all four harnesses** from scratch — including **both headless discovery
legs the worker admitted it did not re-run this session** — and the coverage split
reproduces exactly. No leak-class (D1–D4) issue, no evidence-integrity issue.
Novelty labeling is accurate and conservatively hedged. Secret scan is clean. The
only issues are **cleanliness/cosmetic** (absolute home-path leaks + missing
`.gitignore` + a pre-final-draft self-praise word) and **none of them touches a
headline number**. I fixed the abspath leaks in place; the rest is flagged below.

---

## Required fixes before publishing (all cosmetic — no headline affected)

1. **Absolute home-path leak — SCRUBBED by auditor; harness re-introduces it.**
   Every `artifacts/raw/discovery_*.json` recorded `cmd[0]` as
   `/Users/richardli/go/bin/katana`, and `resume-summary.json` +
   `artifacts/logs/run_resume.out` recorded `/Users/richardli/.config/katana/...`
   (leaks the macOS username). I rewrote all publish-bound files (raw JSON + logs)
   `/Users/richardli/ → ~/`; a full-tree sweep is now clean. **Durable fix still
   owed to the worker:** `run_discovery.py` writes the absolute `KATANA` path into
   `cmd`, and `run_resume.py` writes the absolute `KATANA_CONFIG_DIR` into
   `resume_file_location` — so the next re-run re-adds the leak. Record a sanitized
   copy (e.g. `KATANA.replace(os.path.expanduser("~"), "~")`) and/or add a
   `.gitignore`.
2. **No `.gitignore` in the pack.** Add one for `__pycache__/` and either exclude
   `artifacts/logs/` or keep it scrubbed (benchmark convention; matches the A-1
   pack's fix). Note: unlike A-1, `.venv` here is only **76K** (harnesses are
   stdlib-only), so there is **no** 200 MB-venv problem — this is hygiene only.
3. **Pre-final-draft self-praise lint.** `research-materials.md:325` contains
   "**strongest** information-gain items" (the worker already self-flagged this in
   its Part-6 check). Neutralize to "best-supported" per Part 4 / D12 before any
   final draft. Several "honest/honestly/independent" occurrences in notes and code
   comments are borderline-descriptive (they describe disclosure discipline, not a
   self-awarded quality) — evidence-phase only, so not a blocker, but zero the
   adjectives in the final draft.

Non-fix caveat for the writer (leave as-is): the novelty table tags "resume writes
`~/.config/katana/resume-<xid>.cfg`" as **DOCUMENTED**. The upstream README only
says `-resume string  resume scan using resume.cfg` (implies a `resume.cfg` in cwd)
and the docs page does not mention a path at all. The pack's measured actual
location is really a **correction** to the docs, which *strengthens* the finding —
frame the location as measured, not doc-sourced.

---

## Independent reproduction (my re-runs, pack's own `.venv`)

I ran `run_discovery.py` (all 4 modes + known-files), `run_scope.py`, and
`run_resume.py` fresh. Cost was verified for self-consistency only (see below), per
the task's "cost re-run optional" allowance.

### Discovery coverage matrix — **independent re-run, headless included**

| Mode | A html | A depth | B js-literal | C runtime-DOM | my elapsed | pack elapsed |
|---|---:|---:|:--:|:--:|---:|---:|
| `standard` | 4/4 | 3/3 | **0/2** | **no** | 15.12s | 14.53s |
| `standard -jc` | 4/4 | 3/3 | **2/2** | **no** | 14.36s | 14.48s |
| `-headless` | 4/4 | 3/3 | **0/2** | **yes** | 69.14s | 69.31s |
| `-headless -jc` | 4/4 | 3/3 | **0/2** | **yes** | 68.61s | 68.05s |

- `B_js_literal_found_by = ["standard_jc"]`, `C_runtime_dom_only_found_by =
  ["headless","headless_jc"]`, `headless_alone_misses_B = true`,
  `standard_jc_misses_C = true`, **`headless_jc_covers_both = false`** — reproduced
  identically.
- My headless run **fetched** `/runtime-only/endpoint42` (server-side hit = 1) and
  emitted **no** `/api/js-endpoint-7,8`; my `headless -jc` run likewise found C and
  still **0/2** on B. **The "headless leg" the headline rests on is not blind — I
  supplied the missing re-run and it holds.**
- Known-files: `sitemap_requested/robots_requested = true`, **loc recall 0.0**
  (`/sitemap/hidden-1,2` missing) — reproduced.

**Independent reproduction: CONSISTENT (headline coverage split fully reproduced).**

### Scope discipline — independent re-run

| Config | `page_out_hits` | out-of-scope host fetched? |
|---|:--:|:--:|
| default | 0 | no |
| `-fs fqdn` | 0 | no |
| `-cs localhost` | 0 | no |
| `-fs '(127.0.0.1\|localhost)'` | **1** | **yes** |

`cs_regex_alone_includes_it = false`, `custom_field_scope_includes_it = true` —
reproduced (server-side hit truth). **Consistent.**

### Resume — independent re-run

Baseline **11** distinct paths; SIGINT after 3s; resume file written to
`~/.config/katana/resume-<xid>.cfg` (fresh `resume-d9h29km…cfg`); contents =
`InFlightUrls.Map` holding **only the seed URL**; interrupted run fetched 10 before
SIGINT; **resume re-fetched all 11** including **10** already-completed pages;
`checkpoint_granularity = per-input-seed`. **Consistent** — resume reaches the same
final set but re-crawls completed pages.

### Cost — self-consistency verified (not independently re-run)

`cost-summary.json` is internally coherent: `standard` [13.17, 13.08, 13.07] →
p50 13.08; `headless` [67.68, 66.78, 66.82] → p50 66.82; `ranges_overlap = false`
(std max 13.17 < hl min 66.78); ratio 66.82/13.08 = 5.108 → **5.1×**. My
non-isolated discovery elapseds (~69s headless vs ~15s standard ≈ 4.6×) corroborate
the order of magnitude and the non-overlap. Verdict stands.

---

## Leak-class findings (Part 6)

**D1 — self-contradicting winner sentence: PASS.**
The only bolded comparative is cost (headless ~5.1× standard) with **non-overlapping**
ranges — legitimate. `standard` vs `standard_jc` wall time (14.53 vs 14.48) is
within noise and is **not** called a win. The scorecard total **77/100** is
self-consistent with its own evidence: it *marks down* mode-selection (6/10),
known-files (4/10), resume (6/10), and JS-endpoint (9/12), and the headline itself
states the limitation ("no single command covers both B and C"). No "katana covers
everything" sentence contradicted by the matrix. Weights sum to 100; scores sum to 77.

**D2 — blind instrument: PASS (this was the worker's buried mine; defused).**
The headline's headless leg was the risk — the worker discloses *honestly* in
`research-materials.md` ("Headless coverage not re-run this session … a fresh
headless discovery re-run timed out under transient load. Numbers stand but note the
source") and in the Gaps list. The caveat is **disclosed, not whitewashed into a
clean result.** It is also artifact-backed (`discovery_headless.json` server-side
hit for the runtime-DOM path), and I **independently re-ran both headless legs** —
they reproduce. Recall is measured against a pre-registered `ground_truth.json`;
scope/resume use fixture **server-side hit counters** (fetch-truth, independent of
katana's stdout). Instrument is not blind.

**D3 — mis-attribution: PASS.**
Known-files 0.0 recall is root-caused to katana source (empty `RootHostname` in
`sitemapxml.go` → `ValidateScope` in `base.go` → the IP-literal branch of
`validateDNS` in `scope.go` comparing loc-host to an empty root). The pack ruled out
depth (`-d 3/4/5`), flag choice (`all/sitemapxml/robotstxt`), and `-jc` first, and
attributes the intermittent dial-stall to the **environment** (katana's separate
known-files client), explicitly separated from the recall conclusion. **The `-fs`
rescue is labeled a HYPOTHESIS "not directly measured against `-kf`"** in the body,
the Gaps list, the scorecard, *and* the D4 self-check — it is **never** written as
"just add a flag and it works." Measured recall (0.0) is real (I reproduced it) and
not adjusted. No mis-attribution.

**D4 — claim-without-artifact: PASS.**
Spot-checked 5 headline numbers, all resolve to a JSON field:
`headless_jc_covers_both:false` → `discovery-summary.json.coverage_contrast`;
`resume_refetched_count:10` → `resume-summary.json.analysis`; `page_out_hits:1` →
`scope-summary.json.configs.fs_custom_both`; `5.1×` → `cost-summary.json.verdict`;
`loc recall 0.0` → `discovery-summary.json.known_files`. The one un-artifacted item
(the `-fs` rescue) is explicitly a hypothesis — the pack's own D4 self-check flags
it. No unbacked "cross-verified" prose.

---

## Novelty classification (three-gate) + evidence

Verified against the live upstream README, the docs "Running Katana" page, and the
issue tracker. Classifications are **accurate**:

- **Modes exist / headless "finds more" / `-kf` needs depth ≥3 — DOCUMENTED.**
  Confirmed: docs describe standard vs `-headless` ("better coverage") and `-jc`
  ("JavaScript file parsing"); README states verbatim "a **minimum depth of 3 is
  required** to ensure all known files are properly crawled." The pack's value is the
  *per-class quantification*, correctly not claimed as new capability.
- **B/C coverage split — EXCLUSIVE (quantification).** Docs say headless gives
  "better coverage" but nowhere measure per-endpoint-class recall or show the B/C
  disjointness; the docs' "better coverage" is even *contradicted* for class B
  (headless finds fewer JS-file literals than `standard -jc`). Zero issue-tracker
  hit. Defensible EXCLUSIVE.
- **`-jc` inert under `-headless` — EXCLUSIVE (candidate).** Docs are silent on `-jc`
  behavior under headless. The cited adjacent issue **#1324 is a macOS-ARM segfault
  with `-hl -jc`**, not a JS-recall report (I read it) — the pack correctly calls its
  own finding a "candidate, single observation, mechanism not instrumented," which is
  the right hedge. Worth noting: the pack ran the exact `-hl -jc` combo that #1324
  crashed on and it completed rc=0 on v1.6.1.
- **Resume re-crawls completed pages / known-files drops loc for IP targets —
  EXCLUSIVE.** Measured + source-grounded; no prior public record. Correct.
- **`-cs` can't add a host, custom `-fs` can — DOCUMENTED mechanism / EXCLUSIVE
  demonstration.** Both flags are documented; the measured demonstration is the
  pack's. Correct.

No novelty inflation. The headline is framed as a *measurement/quantification of
documented modes*, not a brand-new capability — matching the pack's own statement.

---

## Hardcoding lint: PASS

All conclusion fields are computed from run output:
- `recall()` = set difference of emitted paths vs pre-registered ground truth.
- `coverage_contrast` derived from `has_B`/`has_C` lambdas over measured recall.
- cost `ratio = p50_hl / p50_std`, `ranges_overlap` from min/max comparison.
- resume `checkpoint_granularity` computed from baseline/interrupted/resume set logic.
No literal result constant (`5.1`, `0.0`, `2/2`, `13.08`, `66.82`) is written into
the harness. The endpoint sets (`HTML_ENDPOINTS`, `JS_LITERAL_ENDPOINTS`, …) are
legitimately **pre-registered ground truth** (methodology Part 3 endorses writing
the expected set before running), not hardcoded results. The only `== 1.0` is a
threshold in `has_B`, not a stored outcome.

---

## Secret / cleanliness scan

- **Credentials: CLEAN.** No `sk-or-`, `sk-ant-`, `OPENROUTER`/`OPENAI`, `API_KEY`,
  `ghp_`, `xox*`, AWS keys, or private-key blocks in any publish-bound file
  (`*.md`, `tests/*.py`, `artifacts/raw/*.json`), excluding `.venv`/`__pycache__`.
- **Absolute home paths: HIT → fixed by auditor.** `/Users/richardli/...` appeared
  in 6 raw JSONs + `run_resume.out`; scrubbed to `~/`; full-tree sweep now clean.
  Durable harness fix still owed (fix #1).
- **Large/vendored files: none.** `.venv` = 76K (stdlib-only). Add `.gitignore`
  anyway (fix #2).

---

## Residual gaps the writer must not overclaim

1. **`-fs` rescue of known-files recall is a hypothesis, not measured.** The pack
   says so; keep it that way (the known-files client dial-stalled during
   confirmation). Do not write "add `-fs` and known-files works."
2. **All numbers are single-machine macOS arm64, local fixture.** No claim may extend
   past the local ground-truth graph. Cost is 3 isolated runs on one host; present
   the 5.1× as distributional/non-overlapping, not an exact universal constant.
3. **Resume "skip completed seeds" for the multi-seed case is source-inferred**, only
   single-seed resume is measured. `-jsluice` (`-jsl`) and isolated depth-cutoff
   tests are untested — the pack lists these; keep them out of any claim.
4. **Frame headless's value precisely:** it buys runtime-DOM (class C) at ~5× wall
   time but *loses* JS-file literals (class B) — "just use headless" is incomplete;
   full coverage needs the union of `standard -jc` + `-headless`.

---

_Audit re-ran `run_discovery.py`, `run_scope.py`, `run_resume.py` on 2026-07-23 in
the pack's own `.venv/bin/python`; cost verified for self-consistency. The pack's
artifact JSONs were overwritten by the reproduction runs (expected) and remain
consistent with the numbers above. Auditor-generated resume `.cfg` files were
auto-cleaned by the harness; no lingering processes._

## Fixes applied (post-audit, 2026-07-23)

- **Absolute home-path leak — RESOLVED in committed files.** Rewrote
  `/Users/richardli/ → ~/` across `artifacts/raw/*.json` and `artifacts/logs/*`;
  all JSONs re-validated as parseable; full-tree `/Users/richardli` sweep is clean.
  **Not durable until the worker sanitizes the two harness scripts and/or adds a
  `.gitignore`** (fix #1/#2) — a re-run currently re-emits the absolute paths.

Left for the worker (headline-safe, not applied by auditor): harness path
sanitization, `.gitignore`, and the "strongest" → "best-supported" wording — none
alter a measured value.

**Net status: PASS WITH FIXES.** All headlines reproduced by the independent audit
(including the headless legs the worker did not re-run); the only open items are
cleanliness/cosmetic and one is already applied.
