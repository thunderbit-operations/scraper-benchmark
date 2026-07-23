# chromedp — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

Every headline claim reproduced independently against the pack's own harness
(chromedp **v0.16.0** / Go **1.26.5** / Chrome for Testing **151.0.7922.10** headless
shell build 1232 / Python 3.14.2 / macOS arm64). I **rebuilt the Go probe from source**
and **re-ran all five harnesses** (`run_recall.py`, `run_waitsem.py`,
`run_lifecycle.py`, `run_concurrency.py`, `run_coldstart.py`). The H1 recall matrix, the
injection-timing gradient, the H2 wait-semantics table, the H3 cancel-reap / macOS
orphan process-truth, H4 cold-start, and H5 shared-vs-separate process counts all
reproduce. Anti-hardcoding lint is clean, secret/abspath scan is clean, and the
scorecard is arithmetically self-consistent (weights=100, scores=84).

**The single substantive fix is a Gate-1 novelty-labeling error**: the H3 macOS
orphan is tagged **"EXCLUSIVE macOS orphan measurement"** with a "no public macOS
orphan process-truth / zero-hit" framing, but the chromedp issue tracker directly
documents the same platform-scoped behavior. This does **not** change any measured
value, score, or the (correct, source-verified) attribution — but the EXCLUSIVE tag
must be downgraded and the prior issues cited before any final draft. Everything else
is PASS. I did **not** rewrite the novelty table (evidence-integrity item — flagged,
not silently changed).

---

## Required fixes before publishing

### 1. HEADLINE-ADJACENT (novelty integrity) — H3 macOS orphan is NOT zero-hit EXCLUSIVE

The novelty table (research-materials.md) tags the macOS orphan as **"DOCUMENTED reap
/ EXCLUSIVE macOS orphan measurement"** with the note *"godoc force-kill note is
Linux-scoped; no public macOS orphan process-truth."* A proper Gate-1 issue-tracker
search returns direct hits:

- **[#774] "Chrome does not exit on FreeBSD as it does on Linux"** (closed) — reports
  the *identical* mechanism on a different non-Linux OS, verbatim: *"On Linux, Chromium
  exits when the Go process does regardless of whether the context is canceled. On
  FreeBSD, Chromium only exits if the context is canceled."* This is the pack's finding.
- **[#752] "Hanging Chromium processes"** (open, filed on `darwin/amd64`) — macOS
  Chromium processes not reaped when the Go process stops.
- **[#562] "Make allocateCmdOptions optional"** (closed) and **[#1566] "Default
  SysProcAttr Pdeathsig=SIGKILL…"** (open) — both explicitly document that the
  parent-death force-kill lives in `allocate_linux.go` (Linux-only) via
  `Pdeathsig=SIGKILL`.

**Fix:** re-tag from "EXCLUSIVE macOS orphan measurement" to **"KNOWN-ISSUE
(platform-scoped non-exit: [#774] FreeBSD, [#752] macOS hanging; mechanism [#562]/[#1566])
+ EXCLUSIVE *quantification*"** — i.e. the *behavior* is documented; the pack's genuine
contribution is the **pgrep process-truth measurement** (cancel-vs-no-cancel contrast,
~13 ms reap, 3/3 determinism), which those qualitative bug reports do not provide. This
mirrors the pack's own correct handling of H1/H2 ("DOCUMENTED mechanism / EXCLUSIVE
demonstration"). It is the exact v2 failure mode the methodology warns about (self-tag
EXCLUSIVE without searching the tracker), so it must be corrected, but the measurement,
attribution, and score are unaffected.

### 2. COSMETIC — "godoc force-kill guarantee is Linux-scoped" is slightly imprecise

The godoc (`ModifyCmdFunc` doc comment in `allocate.go`) actually states the default
command *"sends SIGKILL to any open browsers when the Go program exits"* **as if
universal** — the Linux-scoping is not in the godoc prose but in the build-tagged
source (`allocate_linux.go` sets `Pdeathsig`; `allocate_other.go` is a no-op). So the
finding is really a **correction to an over-promising godoc**, which *strengthens* it.
Frame the Linux-scoping as measured/source-derived, not as a godoc statement.

### 3. COSMETIC — self-praise adjective lint (evidence-phase, not a blocker)

`grep -iE 'honest|independent|strongest|trustworthy'` over the `*.md` surfaces only
"Reproducibility notes (honest)", "Novelty honesty", "reported honestly", "Honest
negative", and "independent of chromedp's own return" — all either negative-result
transparency labels (rule-required disclosure) or instrument-independence descriptions,
not self-awarded quality adjectives on the tool. Consistent with the katana audit's
treatment; neutralize in the final draft, not a blocker now.

**Nothing required in-place was left unfixed by me. No abspath/secret/typo fix was
needed (scans clean). Fix #1 is flagged for the worker (evidence integrity — not
auditor-rewritten); #2/#3 are cosmetic writer notes.**

---

## Independent reproduction (my re-runs)

Rebuilt `chromedp_probe` from source (`go build`, resolved chromedp v0.16.0), then ran
each harness against the pack's fixture. **The pack's five artifact JSONs were restored
to the worker's originals after my runs** so the pack's prose↔JSON numbers stay
consistent; my reproduction values are recorded below.

### H1 — recall matrix (delay=800), the headline — **must-run, done**

| Strategy | A static | B sync | C delayed | my elapsed | worker elapsed |
|---|:--:|:--:|:--:|---:|---:|
| `none` (Navigate+read) | ✓ | ✓ | **✗** | 354 ms | 317 ms |
| `WaitReady("body")` | ✓ | ✓ | **✗** | 111 ms | 107 ms |
| `WaitVisible("#delayed-injected")` | ✓ | ✓ | **✓** | 908 ms | 912 ms |
| poll until marker | ✓ | ✓ | **✓** | 967 ms | 972 ms |

`C_delayed_found_by = ["waitvisible","poll"]`, `naive_navigate_misses_C = true`,
`waitready_body_misses_C = true`, all 4 strategies `stable = true` across 3 reps —
reproduced identically. Injection-timing gradient (`none` vs `WaitVisible`):

| C delay | none sees C | WaitVisible sees C | WV elapsed (mine / worker) |
|---:|:--:|:--:|---:|
| 0 ms | **yes** (race) | yes | 111 / 109 ms |
| 100 ms | **no** | yes | 206 / 208 ms |
| 400 ms | **no** | yes | 508 / 519 ms |
| 800 ms | **no** | yes | 919 / 911 ms |
| 1500 ms | **no** | yes | 1617 / 1625 ms |

`WaitVisible` elapsed tracks the injection delay (proving it genuinely waited); `none`
catches C only at delay 0 (the disclosed race boundary). **Independent reproduction:
CONSISTENT.** Cross-series parity holds: class C is the same runtime-injected node
katana's static crawl misses and playwright-mcp's live snapshot catches — here a live
chromedp browser *does* catch it, **but only with a node-keyed wait**. The pack frames
this correctly as a wait-strategy footgun (Runtime-content dimension 9/12, "not a
capability limit"), **not** as "chromedp can't get dynamic content" — no misstatement.

### H3 — lifecycle: cancel-reap vs macOS orphan (process-truth) — **must-run, done**

| Path | before | after | outcome | reap_ms (mine / worker) |
|---|:--:|:--:|---|---|
| `defer cancel()` | 1 | **0** | reaped | 12/12/12 / 13/13/12 |
| exit **without** cancel | 0 | **1** | **orphaned** (3/3), then force-cleaned to 0 | — |

`cancel_reaps_all = true`, `orphan_on_exit_all = true`, `all_orphans_cleaned = true` —
reproduced identically (pgrep on a unique `--user-data-dir`, browser-only procs).
**Independent reproduction: CONSISTENT. Post-run sweep: 0 real
`chrome-headless-shell` processes, 0 leftover temp dirs — my runs left no orphan.**

**Attribution audit (highest-risk item — source-verified, holds):**
- (a) The orphan is **real pgrep process-truth**, not inferred: `before=0` (unique dir),
  `after_probe_exit=1` proves Chrome both started and survived the Go exit.
- (b) cancel vs no-cancel is the **same binary/harness** (`main.go` `cmdLifecycle` vs
  `cmdStartNoCancel`, identical `allocOpts`+`Navigate`+`WaitReady`); the *only*
  difference is the `cancel()`/`cancelAlloc()` calls. Rules out a confounder.
- (c) "godoc force-kill is Linux-scoped" — **CONFIRMED in source.** In the module cache
  (`chromedp@v0.16.0`): `allocate_linux.go` (`//go:build linux`) sets
  `cmd.SysProcAttr.Pdeathsig = syscall.SIGKILL` ("When the parent process dies (Go),
  kill the child as well"); `allocate_other.go` (`//go:build !linux`, i.e. macOS) makes
  `allocateCmdOptions` a **no-op**. The reap-on-cancel path is `exec.CommandContext`
  (allocate.go:173, cross-platform — which is why cancel reaps on macOS too). So the
  pack correctly attributes the macOS orphan to the **missing Linux-only parent-death
  signal**, and correctly frames `defer cancel()` as load-bearing on macOS — **not** as
  "chromedp's macOS bug." No mis-attribution.

### H2 — WaitReady vs WaitVisible (re-run, optional) — CONSISTENT

`display:none` attached node: `WaitReady` **returns** (~5–6 ms), `WaitVisible` **times
out** at the 4 s deadline with a clean `context deadline exceeded` (3/3). Selector
semantics on the visible node: default query / `ByID` / `ByQuery` all return;
**`selector_440_hang_reproduced = false`** — the [#440] hang did not reproduce in
v0.16.0, honestly reported as not reproduced (verified [#440] exists and matches).

### H4 — cold start (re-run, optional) — CONSISTENT

Worker `[102,111,105,98,98]` p50 **102** (self-consistent: median 102, mean 102.8). My
re-run `[101,93,93,94,100]` p50 94 — same ~100 ms band (host slightly warmer). Confirms
`requires_external_chrome = true`. Order-of-magnitude reproduced.

### H5 — concurrency (re-run alone, optional) — CONSISTENT on the durable finding

Process count **shared = 1 vs separate = 4** reproduced exactly (the durable finding).
Wall time: my run shared p50 220 (213–235) vs separate p50 252 (243–274) — ranges still
**disjoint** (235 < 243) but the margin is **thinner** than the worker's (209–219 vs
261–278). The pack already treats the process-count as the finding and hedges the
wall-time as "modest and workload-specific" (medium confidence, 9/10) — appropriate; the
writer must **keep the wall-time hedged** and not harden it into a clean speed win.

---

## Four-class leak audit (Part 6)

**D1 — self-contradicting winner sentence: PASS.** Weights sum to 100, scores to 84
(self-consistent). No winner sentence is contradicted by its own table:
- "pure-Go / no external deps" is **never** claimed as a win — the pack repeatedly
  caveats "the no-dependencies claim is about the Go module, not the runtime," and
  Setup scores **8/10** *because* of the runtime Chrome requirement. Not defeated by H4.
- "`defer cancel()` cleans up" is **not** claimed as automatic cleanup — Lifecycle
  scores **8/12**, explicitly docked for the macOS orphan. Not defeated by H3.
- Concurrency "shared faster" rests on **non-overlapping ranges** (both runs) + the
  process-count gap, and is hedged as modest/workload-specific. Recall-matrix elapsed
  gaps are correctly framed as the *cost of waiting*, not a speed win.

**D2 — blind instrument: PASS.** The recall probe registers **both** presence (catches
C under WaitVisible) and absence (misses C under none/WaitReady) — positive+negative
control. Class B/C markers+hrefs are runtime-assembled from fragments (verified in
`fixture_server.py`), so a "found" proves JS execution, not byte-reading. The lifecycle
pgrep counter registers **both** reap (1→0) and non-reap (orphan 1 survives), filtered
to browser-only procs on a unique dir. Neither instrument is blind — my re-runs
exercised both signal directions.

**D3 — mis-attribution: PASS.** H1 class-C miss attributed to Navigate's load-event
completion vs post-load injection, validated by the gradient (found at 0 ms, missed at
≥100 ms). H3 macOS orphan attributed to the absent Linux-only parent-death signal +
`exec.CommandContext` cancel-kill — **source-verified** (see H3 (c)) and controlled by
the identical-harness cancel path reaping in ~12 ms. No harness artifact.

**D4 — claim-without-artifact: PASS.** Spot-checked 6 headline numbers, all resolve to
a JSON field: C found-set → `recall-summary.contrast`; delay-tracking →
`injection_timing_gradient`; reap 13 ms → `lifecycle-summary.cancel_runs[].reap_ms`;
cold-start p50 → `coldstart-summary.cold_start_ms`; 1-vs-4 procs → `concurrency-summary`;
#440-not-reproduced → `waitsem-summary.selector_440_hang_reproduced`. The one
un-reproduced item ([#440]) is reported as *not reproduced*, not as a verified trap.

---

## Novelty classification (three-gate) + evidence

Verified against chromedp godoc/source (module cache), README/example_test.go, and the
issue tracker (`gh search issues`). Classifications:

- **pure-Go/CDP driver, context API, wait actions, `defer cancel()` — DOCUMENTED.** Correct.
- **H1 per-injection-timing recall matrix by wait strategy + `WaitVisible` delay-tracking
  — EXCLUSIVE (quantification).** Mechanism (WaitVisible on injected node) is DOCUMENTED
  (godoc examples); the per-timing recall matrix is a controlled-fixture measurement with
  no prior SERP/issue record. Defensible.
- **H2 `WaitReady`=attached vs `WaitVisible`=visible on `display:none` — DOCUMENTED
  semantics / EXCLUSIVE demonstration.** Correct; [#440] verified and honestly marked
  not reproduced.
- **H3 macOS orphan — MISLABELED (fix #1).** Tagged zero-hit EXCLUSIVE; actually
  **KNOWN-ISSUE** (behavior: [#774] FreeBSD non-exit, [#752] macOS hanging; mechanism
  [#562]/[#1566] Linux-only `Pdeathsig`) **+ EXCLUSIVE quantification** (the process-truth
  measurement). Downgrade + cite before publishing.
- **H4/H5 cold-start distribution + shared-vs-separate process/wall numbers — EXCLUSIVE
  (quantification).** No SERP source publishes these; defensible.
- **Wait flakiness ([#168]/[#682]/[#1593]), go-test incompat ([#1591]) — KNOWN-ISSUE.**
  [#1591] verified; correctly used to justify `go build` over `go test`.

---

## Anti-hardcoding lint: PASS

No result constant (13, 102, 214, 264, 912, 317…) is written as a literal in the probe
or runners. All conclusions are computed: `elapsed_ms`/`reap_ms`/`wall_ms` =
`time.Since(...)`; `reaped` = `after == 0`; recall `classes_found` = Python `classify()`
of ground-truth markers vs rendered `outerHTML`; `C_delayed_found_by`,
`wall_ranges_overlap`, `selector_440_hang_reproduced`, cold-start `p50`
(`statistics.median`) all derived from measured output. The literal marker fragments in
the Go poll (`"DELAYED"+"_INJECTED_"+"MARKER"+"_C"`) are a *search target* (assembled,
matching the fixture design), not a stored result. Fixture markers are legitimately
pre-registered ground truth (methodology Part 3), not hardcoded outcomes.

## Secret / cleanliness scan: CLEAN

- **Credentials: CLEAN.** No `sk-*`/`API_KEY`/`token=`/`Bearer`/`ghp_`/AWS/private-key
  patterns in any publish-bound file (`*.md`, `tests/*.py`, `tests/harness/*.go|go.mod|
  go.sum`, `artifacts/raw/*.json`), excluding `.venv`/`__pycache__`/the built binary.
- **Absolute paths: CLEAN.** No literal `/Users/…`, no `richardli` username, no
  `/var/folders` temp abspath. The Chrome path in `metadata-snapshot.md` and every JSON
  uses `~/Library/Caches/…` (tilde), not the absolute home — the specific concern is
  satisfied. `$HOME/…` in the README/metadata *export* commands is a shell variable
  (correct reproduction usage), not a leak.
- **`.gitignore` present:** covers `.venv/`, `__pycache__/`, logs, the `chromedp_probe`
  binary, and runtime `chromedp_*/` temp dirs. go.mod/go.sum committed (pin v0.16.0).

---

## Residual gaps the writer must not overclaim

1. **All numbers are single-machine macOS arm64 + one Chrome build**, local fixture.
   Linux reap/orphan not run — the pack lists this; keep the orphan finding macOS-scoped.
2. **H5 wall-time is fragile** (my re-run margin 8 ms vs the worker's 42 ms). The durable
   claim is process count (1 vs 4); keep wall-time distributional/hedged.
3. **The macOS orphan is a KNOWN platform behavior** (fix #1) — the pack's contribution is
   the measurement, not the discovery; frame it that way and cite [#774]/[#752].
4. **#440 / WaitReady intermittent-timeout reports were not attempted** (semantics
   measured instead); do not imply they were tested.

---

_Audit rebuilt `chromedp_probe` from source and re-ran all five harnesses on 2026-07-24
in the pack's own layout; the five artifact JSONs were restored to the worker's originals
afterward (my reproduction values are recorded above and match within timing noise).
Post-run sweep: 0 `chrome-headless-shell` processes, 0 leftover `chromedp_*` temp dirs._

**Net status: PASS WITH FIXES.** All headlines reproduced; attribution source-verified;
anti-hardcoding, secret/abspath, and D1–D4 clean. The one substantive item is the H3
macOS-orphan novelty tag (EXCLUSIVE → KNOWN-ISSUE + EXCLUSIVE quantification, cite
[#774]/[#752]/[#562]/[#1566]); it changes no measured value or score.

[#168]: https://github.com/chromedp/chromedp/issues/168
[#440]: https://github.com/chromedp/chromedp/issues/440
[#562]: https://github.com/chromedp/chromedp/issues/562
[#682]: https://github.com/chromedp/chromedp/issues/682
[#752]: https://github.com/chromedp/chromedp/issues/752
[#774]: https://github.com/chromedp/chromedp/issues/774
[#1566]: https://github.com/chromedp/chromedp/issues/1566
[#1591]: https://github.com/chromedp/chromedp/issues/1591
[#1593]: https://github.com/chromedp/chromedp/issues/1593
