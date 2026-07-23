# rod — Independent Audit (validation)

**VERDICT: PASS** (no headline/score/evidence-integrity fix required; three trivial cosmetic notes only)

Every headline claim reproduced independently against the pack's own harness
(rod **v0.116.2** + leakless **v0.9.0** / Go **1.26.5** / Chrome for Testing
**151.0.7922.10** headless shell build 1232 / Python 3.14 / macOS arm64). I **rebuilt
`rod_probe` from source** (`go build`, resolved rod v0.116.2 + leakless v0.9.0 from the
committed go.mod/go.sum) and **re-ran all five harnesses** (`run_recall.py`,
`run_lifecycle.py`, `run_waitsem.py`, `run_coldstart.py`, `run_concurrency.py`). The H1
recall matrix + injection-timing gradient, the H2 leakless-on/off orphan/reap
process-truth (both exit-without-cleanup and SIGKILL), the H3 Element-vs-WaitVisible
semantics, H4 cold-start + leakless tax, and H5 shared-vs-separate process/wall counts all
reproduce. Anti-hardcoding lint is clean, secret/abspath scan is clean, the scorecard is
arithmetically self-consistent (weights=100, rod=85, chromedp=84), and — critically — the
pack **correctly avoids the exact Gate-1 novelty mislabel the chromedp audit had to
fix**: the leakless-reaps-on-macOS finding is tagged "KNOWN behavior + EXCLUSIVE
quantification" with why-rod cited, not "zero-hit EXCLUSIVE."

**The pack's originals were restored after my runs** (my reproduction values are recorded
below and match within timing noise); the rebuilt `rod_probe` binary was removed
(gitignored). Post-run sweep: 0 `chrome-headless-shell` processes, 0 `rod_*` temp dirs.

---

## Required fixes before publishing

**None at headline / score / evidence-integrity level.** Unlike the chromedp pack (which
needed its macOS-orphan novelty tag downgraded from EXCLUSIVE to KNOWN-ISSUE), the rod
pack already labels the mirror finding correctly. The three items below are **cosmetic
writer-notes**, not blockers, and I did **not** auto-edit them (the timestamp one is a
runner-code nuance, not a typo — fixing it without re-running would desync code from the
committed JSON; I flag rather than half-fix, matching the chromedp auditor's posture).

### C1 — COSMETIC: coldstart / concurrency `run_started_at` ≈ `run_completed_at`
In `run_coldstart.py` and `run_concurrency.py` the summary dict — **including**
`run_started_at` — is built at the *end* of `main()` (coldstart lines ~115–138,
concurrency lines ~111–128), so both timestamps are ~19 µs apart even though those runs
take ~1–2 min. `run_recall.py`/`run_lifecycle.py`/`run_waitsem.py` correctly stamp
`run_started_at` at the top. Provenance-only imprecision; **no measured sample is
affected**. Writer note: if regenerating, move `run_started_at` above the runs in those two
runners.

### C2 — COSMETIC: unused link references
`research-materials.md` defines `[#210]` and `[#266]` (lines ~354–355) but the body cites
only `[#865]`. Harmless dangling link defs; drop or wire them in the final draft.

### C3 — COSMETIC: "graceful reaps in ~14 ms"
README/materials say graceful `Close()` "reaps in ~14 ms"; the artifact values are
`[16,15,13]` (mean 14.67, median 15). "~14 ms" ≈ the mean, within rounding — fine; could
say ~15 ms for the median. No change required.

---

## Independent reproduction (my re-runs)

### H2 — leakless on/off orphan/reap (the headline, **must-run**) — CONSISTENT

pgrep process-truth on a unique `--user-data-dir`, browser-only procs (exe basename
`chrome-headless-shell`, no `--type=`; leakless guardian excluded). **The on/off toggle is
the attribution core — I ran both arches:**

| Path | leakless | browser procs before → after | orphaned? (mine, 3/3) | worker |
|---|:--:|:--:|:--:|:--:|
| Go exits **without cleanup** | **on** | 0 → **0** | **no** (0/0/0) | no (0/0/0) |
| Go exits **without cleanup** | **off** | 0 → **1** | **yes** (3/3) | yes (3/3) |
| parent **SIGKILL** (crash) | **on** | 1 → **0** | **no** (0/0/0) | no (0/0/0) |
| graceful `Close()` (in-process) | on | 1 → **0** | reaped, reap_ms **16/18/16** | reaped, 16/15/13 |

`exit_leakless_on_reaped_all=true`, `exit_leakless_off_orphaned_all=true`,
`kill_leakless_on_reaped_all=true`, `all_orphans_cleaned=true` — **reproduced identically.**
The OFF arm genuinely orphans 3/3 (before=0 on a unique dir proves the browser both started
and survived the Go exit; after=1 is a real leftover), and the ON arm reaps 3/3 on both the
graceful-exit and the SIGKILL path. So "leakless is the cause" is a **measured same-harness
on/off contrast**, not a doc assertion — the pretest's own instruction ("do not claim
leakless prevents orphans from the doc alone — only from the pgrep on/off measurement") is
honored. **Independent reproduction: CONSISTENT. Post-run: 0 real browser procs, 0 temp
dirs.**

### H1 — recall matrix + injection-timing overshoot (the ergonomic headline, **must-run**) — CONSISTENT

Recall matrix at delay=800, each idiom ×3 (found-sets stable all three):

| rod idiom | A | B | C | my elapsed | worker elapsed |
|---|:--:|:--:|:--:|---:|---:|
| `none` (Navigate+read HTML) | ✓ | ✓ | **✗** | 33 ms | 43 ms |
| `WaitLoad`+HTML | ✓ | ✓ | **✗** | 12 ms | 13 ms |
| **`Element("#delayed-injected")` (auto-wait)** | ✓ | ✓ | **✓** | 1356 ms | 1555 ms |
| poll until marker | ✓ | ✓ | **✓** | 858 ms | 851 ms |

`C_delayed_found_by=["element","poll"]`, `naive_html_misses_C=true`,
`waitload_html_misses_C=true`, all 4 idioms `stable=true` across 3 reps — reproduced. rod's
idiomatic `Element()` recovers class C **with no explicit wait call** (the ergonomic win
over chromedp's `Navigate`+read, which misses it); the naive `HTML()`/`WaitLoad+HTML`
footgun is identical to chromedp's naive read — correctly framed.

Injection-timing gradient (rod `Element` elapsed vs delay), with the **honesty check** on
the overshoot:

| C delay | none sees C | Element sees C | Element elapsed (mine / worker) | chromedp WaitVisible (from chromedp artifact) |
|---:|:--:|:--:|---:|---:|
| 0 ms | yes (race) | yes | 11 / 12 ms | 109 ms |
| 100 ms | **no** | yes | 211 / 214 ms | 208 ms |
| 400 ms | **no** | yes | 615 / 628 ms | 519 ms |
| 800 ms | **no** | yes | 1415 / 1428 ms | 911 ms |
| 1500 ms | **no** | yes | 3023 / 2858 ms | 1625 ms |

rod's `Element` elapsed **tracks then overshoots** the injection delay (800 → ~1415 ms)
because its auto-wait polls on a backoff sleeper, where chromedp's event-driven
`WaitVisible` tracks tightly (800 → 911 ms). **This is presented as a cost of rod's
ergonomics, not spun in rod's favor** — the pack docks Runtime-content accordingly and
scores the tradeoff both ways. **Verified the chromedp WaitVisible column
(109/208/519/911/1625) is an EXACT match to `tools/chromedp/artifacts/raw/recall-summary.json`**
— a real same-host artifact citation, correctly attributed (not fabricated, not inferred
from prose). **Independent reproduction: CONSISTENT.** Cross-series parity holds: class C
is the same runtime-injected node katana misses / playwright-mcp catches / chromedp catches
only with an explicit wait — rod is the fourth same-fixture data point.

### H3 — Element vs WaitVisible on display:none (re-run) — CONSISTENT
Element **returns** on the attached `display:none` node (0–2 ms); `WaitVisible` **times
out** at the 4 s deadline with a clean `context deadline exceeded` (3/3); CSS `Element` and
XPath `ElementX` both resolve the visible node (no #440-style trap); never-appearing
selector honors the 2 s page timeout cleanly. Reproduced identically.

### H4 — cold start + leakless tax (re-run alone) — CONSISTENT
My leakless-**on** p50 114 (111–120), **off** p50 113 (106–115) → **tax ~1 ms, ranges
overlap** (worker: on 119 / off 114 / tax 5 ms, ranges overlap). Same conclusion both runs:
the leakless guardian tax is **within noise and does NOT explain the rod-vs-chromedp gap**
(chromedp 102 ms); the small delta is rod's own launcher/connect overhead. The
"ranges-overlap ⇒ tie" logic is correct (on-range [111,120] ∩ off-range [106,115] ≠ ∅).
`requires_external_chrome=true` confirmed. Order-of-magnitude reproduced (host slightly
warmer than the worker's).

### H5 — concurrency shared vs separate (re-run alone) — CONSISTENT on the durable finding
Process count **shared 1 vs separate 4** reproduced exactly. Wall: my shared p50 196
(192–207), separate p50 **1323** (1321–1368) — ranges **disjoint**, ~5× chromedp's 264 ms
(worker: separate 1302 ms). The pack treats the **process count (1 vs 4)** as the durable
mechanism-clear finding and explicitly marks the *cause* of the separate-mode wall penalty
a **hypothesis** ("I did not run a per-launch attribution experiment"), having ruled out
the leakless tax as far too small (H4 measured ~5 ms/launch). Correct — the writer must keep
the separate-mode *cause* hedged and not harden it into a mechanism.

---

## Four-class leak audit (Part 6)

**D1 — self-contradicting winner sentence: PASS.** Weights sum to 100; rod=85, chromedp=84
(both self-consistent, re-added by hand). The +1 edge is the **exact net of
evidence-anchored per-dimension deltas**: rod **+1** Runtime (Element recovers C
out-of-the-box, reproduced), **+1** Wait-clarity (no #440 trap, reproduced), **+2**
Lifecycle (leakless reaps where chromedp orphans, reproduced), **−1** Cold-start (119 vs
102, reproduced), **−2** Concurrency (separate 5× penalty, reproduced) = **+1**. rod
**honestly loses two dimensions**; there is no "rod wins across the board" sentence, and
every headline caveats its cost (auto-wait "overshoots"; separate mode "~5× — prefer
shared"). The rod scorecard's chromedp comparison column is an **exact dimension-by-dimension
copy of chromedp's own published scorecard** (verified) — no manufactured edge.

**D2 — blind instrument: PASS.** The pgrep counter registers **both** reap (leakless-on
1→0 / 0→0) **and** non-reap (leakless-off 0→1 orphan survives) — positive+negative control,
exercised in my re-run. The recall probe registers **both** presence (catches C under
`Element`) and absence (misses C under `none`/`WaitLoad`). Class B/C markers+hrefs are
runtime-assembled from fragments (verified in `fixture_server.py`: `'SYNC'+'_INJECTED_'+…`,
`6*7` computed), so a "found" proves JS execution, not byte-reading. Neither instrument is
blind.

**D3 — mis-attribution: PASS.** H1 class-C miss attributed to reading before the post-load
injection — validated by the gradient (found at 0 ms, missed at ≥100 ms). H2 reap
attributed to the leakless guardian — validated by the **on/off toggle** (off orphans 3/3
like chromedp), ruling out "rod is magic"; the SIGKILL arm backs the crash claim with real
kill-path runs, not why-rod prose. H5 separate-mode penalty's *cause* is explicitly left a
**hypothesis** (leakless tax ruled out as too small). No harness artifact substituted for a
finding.

**D4 — claim-without-artifact: PASS.** Spot-checked 6 headline numbers, all resolve to a
JSON field: leakless-off orphan 3/3 → `lifecycle-summary.exit_leakless_off_runs[].orphaned`;
Element@800→1428 ms → `recall-summary.injection_timing_gradient[3].element`; cold-start p50
119 → `coldstart-summary.cold_start_ms.p50`; separate 4 procs/1302 ms →
`concurrency-summary.separate_browsers`; WaitVisible timeout 4000 ms →
`waitsem-summary.runs[].hidden_node.waitvisible_ms`; SIGKILL reap →
`lifecycle-summary.kill_leakless_on_runs`. The chromedp comparison numbers are backed by
chromedp's own artifacts (verified exact), not asserted.

---

## Novelty classification (three-gate) + evidence

Verified against rod godoc / why-rod / launcher godoc and the rod issue tracker.
**Key result: the pack correctly does NOT repeat the chromedp pack's mislabel.** The
chromedp audit had to downgrade a macOS-orphan tag from EXCLUSIVE to KNOWN-ISSUE; here the
**mirror** finding (leakless reaps on macOS where chromedp orphans) is already tagged
**"KNOWN behavior + EXCLUSIVE quantification"**, explicitly citing why-rod's "no zombie on
Mac" and the launcher godoc for the *behavior*, and claiming only the **pgrep process-truth
+ SIGKILL proof + on/off attribution** as EXCLUSIVE. Correct.

- **pure-Go/CDP driver, chainable auto-wait, `Element` vs `WaitVisible`, remote-object-id,
  leakless-by-default & exit-kill — DOCUMENTED.** Correct (godoc/why-rod/launcher godoc
  establish existence, not this pack's values).
- **Per-injection-timing recall matrix by idiom + auto-wait backoff overshoot vs chromedp —
  EXCLUSIVE (quantification).** Mechanism (Element auto-waits on DefaultSleeper) is
  DOCUMENTED; the per-timing recall matrix and the overshoot-vs-chromedp on the same fixture
  are zero-hit measurements. Defensible.
- **`Element`=attached vs `WaitVisible`=visible on `display:none` + no #440 trap —
  DOCUMENTED semantics / EXCLUSIVE demonstration.** Correct.
- **leakless reap-vs-orphan pgrep process-truth (on/off + SIGKILL) — KNOWN behavior +
  EXCLUSIVE quantification.** Correct (see above).
- **leakless does not cover per-browser churn in a long-running process — KNOWN-ISSUE
  ([#865]).** Verified [#865] exists and matches; stated as a boundary, not exercised —
  honestly scoped.
- **Cold-start distribution + isolated leakless tax + shared-vs-separate process/wall —
  EXCLUSIVE (quantification).** No SERP source publishes these. Defensible.

No EXCLUSIVE tag sits on a merely-documented qualitative conclusion; every EXCLUSIVE is a
measurement. Gate-1 clean.

## Anti-hardcoding lint: PASS

No result constant (119, 1302, 1428, 1555, 851, 16, 13, 4000…) is written as a literal in
`main.go` or the runners (grep clean). Recall booleans are computed in Python
(`classify()` in `run_recall.py`) from ground-truth markers vs the probe's raw rendered
HTML — **`main.go` contains zero class-recall logic** (grep confirmed). `elapsed_ms`/
`reap_ms`/`wall_ms` = `time.Since(...)`; `orphaned` = `after>0`; `reaped` = `after==0`;
cold-start `p50` = `statistics.median`; `leakless_tax_ranges_overlap` and
`wall_ranges_overlap` derived from measured min/max. The literal marker fragments in the Go
poll (`"DELAYED"+"_INJECTED_"+"MARKER"+"_C"`) are a *search target* matching the fixture
design, not a stored result. Fixture markers are legitimately pre-registered ground truth.

## Secret / cleanliness scan: CLEAN

- **Credentials: CLEAN.** No `sk-*`/`API_KEY`/`token=`/`Bearer`/`ghp_`/AWS/private-key
  patterns in any publish-bound file (`*.md`, `tests/*.py`, `tests/harness/*.go|go.mod|
  go.sum`, `artifacts/raw/*.json`), excluding `.venv`/`__pycache__`/logs/the built binary.
- **Absolute paths: CLEAN.** No literal `/Users/…`, no `richardli` username, no
  `/var/folders` temp abspath anywhere. The Chrome path and the leakless-guardian path in
  `metadata-snapshot.md` and every JSON use `~/…` (tilde) / `$TMPDIR` placeholder, not the
  absolute home — the specific concern is satisfied. Both the Go probe (`redact()`) and the
  Python runners (`_redact()`) strip `$HOME`→`~` before printing.
- **`.gitignore` present:** covers `.venv/`, `__pycache__/`, logs, `rod_probe`/`*_probe`,
  and `rod_*/`, `leakless-*/`, `.cache/rod/` runtime dirs. go.mod/go.sum committed (pin rod
  v0.116.2 + leakless v0.9.0); neither the binary, the Chrome, nor the leakless guardian is
  copied into the pack (only paths recorded).

---

## Residual gaps the writer must not overclaim

1. **All numbers are single-machine macOS arm64 + one Chrome build**, local fixture. The
   leakless reap and the chromedp orphan are both macOS-scoped; the Linux `Pdeathsig`
   contrast is not run — keep the reap/orphan finding macOS-scoped (the pack lists this).
2. **Long-running browser churn ([#865]) not exercised** — the leakless win is scoped to
   process exit/crash; a server that churns browsers without exiting is the known zombie
   scenario and is untested. Keep the boundary stated alongside the win.
3. **Separate-mode concurrency *cause* is a hypothesis** — the ~5× wall penalty is measured;
   the per-launcher-overhead mechanism is not attributed. Keep hedged.
4. **H1 auto-wait overshoot is rod's cost** — do not let the "ergonomic win" headline bury
   the latency-looseness; the pack currently balances it correctly, and the scorecard docks
   Runtime for it. Keep both sides.

---

_Audit rebuilt `rod_probe` from source and re-ran all five harnesses on 2026-07-24 in the
pack's own layout; the pack's original artifact JSONs were restored afterward (my
reproduction values are recorded above and match within timing noise), and the rebuilt
binary was removed. Post-run sweep: 0 `chrome-headless-shell` processes, 0 `rod_*` temp
dirs — my runs left no orphan._

**Net status: PASS.** All five headlines reproduced (H1/H2 must-run + H3/H4/H5); the
leakless on/off attribution is a real same-harness process-truth contrast; every chromedp
comparison number is an exact same-host-artifact citation; D1–D4 clean; novelty Gate-1
clean (no EXCLUSIVE-on-documented mislabel — the exact trap the chromedp pack fell into is
avoided); anti-hardcoding, secret, and abspath scans clean. The 85-vs-84 edge is the honest
arithmetic of evidence-anchored dimension deltas, with rod losing cold-start and
concurrency. Three cosmetic writer-notes (C1–C3); nothing headline-level to fix.

[#865]: https://github.com/go-rod/rod/issues/865
