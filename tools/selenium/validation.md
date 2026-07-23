# selenium — Independent Audit (validation)

**VERDICT: PASS WITH FIXES** (one cosmetic abspath desensitization applied in-place; two
cosmetic writer-notes flagged. No headline / score / evidence-integrity fix required.)

Every headline claim reproduced independently against the pack's own harness (selenium
**4.46.0** + Selenium Manager **0.4.46** / Python **3.14.2** / auto-supplied chromedriver
**151.0.7922.47** / Chrome for Testing **151.0.7922.10** build 1232 / macOS arm64). I
**re-ran all five measurement harnesses in a clean venv** (`run_provisioning.py`,
`run_recall.py`, `run_lifecycle.py`, `run_coldstart.py`, `run_concurrency.py`; H3 waitsem
verified by artifact self-consistency). The H0 Selenium-Manager version match + cold/warm/
stale behavior, the H1 recall matrix + **500 ms poll quantization**, the **H2 two-tier
reap/orphan process-truth** (both tiers, exit + crash), the H4 cold-start protocol-vs-binary
decomposition, and the H5 shared-vs-separate two-tier process count all reproduce within
timing noise. Anti-hardcoding lint is clean, secret scan is clean, the scorecard is
arithmetically self-consistent (weights=100, selenium=79, chromedp=84, rod=85), the
full-Chrome/headless-shell binary mix is honestly disclosed and does not contaminate the
cross-tool comparison, and — critically — the pack **correctly avoids the exact Gate-1
novelty mislabel the chromedp audit had to fix**: the two-tier orphan is tagged "KNOWN
behavior + EXCLUSIVE quantification" (citing the docs' `quit()`-required warning), not
"zero-hit EXCLUSIVE."

**The pack's original artifact JSONs were restored after my runs** (my reproduction values
are recorded below and match within noise); all six restored artifacts + `ground_truth.json`
are byte-identical to the worker's originals. Post-run sweep: 0 chromedriver, 0
Chrome-for-Testing, 0 chrome-headless-shell processes, 0 leftover temp dirs; the user's real
`~/.cache/selenium` was never modified (145 dir mtime unchanged; H0 used isolated `tempfile`
caches).

---

## Required fixes before publishing

**None at headline / score / evidence-integrity level.** One cosmetic cleanliness item was a
real leak the chromedp/rod siblings do not have, so I fixed it in-place (my auditor authority
covers abspath desensitization). Two more are cosmetic writer-notes I flagged rather than
auto-fixed (fixing without re-running would desync code from the committed JSON, matching the
rod auditor's posture).

### F1 — APPLIED (cosmetic abspath leak): `provisioning-summary.json` leaked 5 `/var/folders/…/T/` temp paths
The pack's `_redact` maps only `$HOME → ~`, so the isolated Selenium-Manager cache paths
(`/var/folders/4s/<user-hash>/T/se_prov_*/chromedriver/…`) that Selenium Manager returns as
`driver_path` were emitted verbatim in `provisioning-summary.json` (5 occurrences). The
chromedp/rod audits both verified "no `/var/folders` temp abspath"; this pack failed that
bar. The hash is a per-user opaque DARWIN_USER_TEMP_DIR id (not the username, not a secret),
so it is cosmetic — but it is a genuine abspath leak inconsistent with the pack's own
`$HOME → ~` redaction intent. **Fix applied (both loci, kept consistent):**
1. `tests/run_provisioning.py` `_redact` now also maps `tempfile.gettempdir() → "$TMPDIR"`
   (the `$TMPDIR` placeholder convention the rod pack already uses), so future runs are clean.
2. The committed `artifacts/raw/provisioning-summary.json` had its 5 leaked prefixes replaced
   with `$TMPDIR`. **No measured value changed** — a diff against the worker's original,
   ignoring the `driver_path` strings, is byte-identical (cold 4054 ms, ratio 155.9, stale
   reused=false, fetched=true all intact).

### C1 — COSMETIC (flagged, not fixed): coldstart / concurrency `run_started_at ≈ run_completed_at`
In `run_coldstart.py` (lines ~124–156) and `run_concurrency.py` (lines ~112–131) the whole
summary dict — including `run_started_at` — is built at the **end** of `main()`, so both
timestamps are ~20 µs apart even though those runs take 1–2 min (`recall`/`lifecycle`/
`waitsem`/`provisioning` correctly stamp `run_started_at` at the top: 35 s / 22 s / 22 s /
8 s spans). This is the **identical** provenance imprecision the rod audit flagged as its C1;
no measured sample is affected. Writer note: if regenerating, move `run_started_at` above the
runs in those two runners.

### C2 — COSMETIC (writer-note): the 500 ms poll default is documented; cite it
`WebDriverWait`'s default `poll_frequency=0.5 s` is documented in the Selenium API. The pack
correctly tags the **latency signature** (100/400 ms → 567 ms on the controlled fixture) as
"EXCLUSIVE (quantification)" — the *measurement* is the contribution — but FINDING-02 could
briefly cite the documented 0.5 s default as the mechanism (as it does for the other DOCUMENTED
mechanisms), so the quantification is not read as discovering the poll interval itself. Not a
mislabel (the EXCLUSIVE is explicitly scoped to "(quantification)"); a one-clause strengthening.

*(The self-praise lint is clean: `grep -iE 'honest|independent|strongest|trustworthy'` over
the `*.md` surfaces only rule-required transparency labels — "parity note, honest",
"Reproducibility notes (honest)", "Honest latency signature", "honestly scoped" — and
methodology/audit-independence phrasing in the README, not quality adjectives awarded to
Selenium. Neutralize in the final draft, not a blocker — matches the chromedp/rod treatment.)*

---

## Independent reproduction (my re-runs)

### H2 — two-tier reap/orphan (the headline, **must-run**) — CONSISTENT

pgrep on a unique `--user-data-dir` counts the **browser** tier (argv[0] basename ==
`Google Chrome for Testing`, no `--type=` → helpers excluded); `ps -p <pid>` with a
`chromedriver` name-guard counts the **driver** tier. Each path 3×:

| Path | chromedriver (pid liveness) | chrome browser (pgrep udd) | outcome | mine (3/3) | worker (3/3) |
|---|:--:|:--:|---|---|---|
| graceful `driver.quit()` | 1 → **0** | 1 → **0** | **both reaped** | reap_ms 109/97/101 | 99/86/87 |
| python exit **without** `quit()` (`os._exit`) | 1 → **1** | 1 → **1** | **both orphaned** | 3/3 | 3/3 |
| parent **SIGKILL** (crash) | 1 → **1** | 1 → **1** | **both orphaned** | 3/3 | 3/3 |

`graceful_reaps_both_all=true`, `exit_both_orphaned_all=true`, `kill_both_orphaned_all=true`,
`all_orphans_cleaned=true` — **reproduced identically.** The instrument is **not blind**: my
re-run exercised both signal directions — the graceful path detects reap (both tiers 1→0),
the no-quit / crash paths detect non-reap (both tiers 1→1). The two tiers are genuinely
separate instruments (pgrep-by-udd vs pid-liveness) and I confirmed each moves independently
in the right direction. This proves the pack's core headline **by count, not by prose**: on a
no-quit exit **and** on a crash, Selenium orphans **1 chromedriver + 1 browser** (two
processes), vs chromedp's browser-only **1** (macOS `allocate_other.go` no-op) and rod's
leakless **0** — "one process worse than chromedp, the opposite of rod." **Post-run sweep: 0
driver, 0 browser procs, 0 temp dirs.**

### H0 — Selenium Manager provisioning (the setup headline, **must-run**) — CONSISTENT

Ran with an isolated `tempfile.mkdtemp` cache per resolution; the real `~/.cache/selenium` was
read only to copy the stale 145 seed and its mtime was unchanged afterward.

| Scenario | worker | my re-run | match |
|---|---|---|:--:|
| COLD resolve → driver version | `151.0.7922.47`, 4054 ms | `151.0.7922.47`, 4264 ms | ✓ |
| WARM ×3 (cache hit) | 28/25/25 ms | 28/26/25 ms | ✓ |
| cold/warm ratio | 155.9× | 161.9× | ✓ (same band) |
| STALE (cache seeded with 145 only) | fetches 151.0.7922.47; 145 **not** reused | same; `reused_stale_145=false`, `fetched_matching_151=true`, cache_after=[145,151] | ✓ |

The **version-matching logic is exactly as claimed and directly artifact-backed**: browser
`151.0.7922.10` → driver `151.0.7922.47`. `driver_matches_browser_build=true` (151.0.7922);
`driver_patch_differs_from_browser_patch=true` (.47 ≠ .10). Selenium Manager keys on
`major.minor.build` and takes the **latest patch** (Chrome for Testing publishes one driver
per build), not the browser's own `.10` — a real correction to the naive "matching driver ==
same version" intuition, and it is the resolved `driver_version` field that proves it, not
narration. The stale-145 non-reuse is proven by the `driver_versions_in_cache_after`
containing **both** 145 and 151 with `driver_version=151…`. Cold path reproduced with an
isolated temp cache; **the user's `~/.cache/selenium` was never written.**

### H1 — recall matrix + 500 ms poll quantization (**re-run**) — CONSISTENT

Matrix at delay=800 (each idiom ×3, all stable): `page_source` finds A+B, **misses C**;
`implicit` / `explicit` / `poll` all recover C. My gradient reproduced the **poll-quantization
signature exactly** — the tell the whole finding rests on:

| C delay | page_source sees C | explicit sees C | explicit elapsed (mine / worker) |
|---:|:--:|:--:|---:|
| 0 ms | yes (race) | yes | 45 / 44 ms |
| 100 ms | **no** | yes | **567 / 567 ms** |
| 400 ms | **no** | yes | **567 / 567 ms** |
| 800 ms | **no** | yes | 1080 / 1084 ms |
| 1500 ms | **no** | yes | 1580 / 1580 ms |

100 ms and 400 ms **both land at 567 ms** — recovery is gated on `WebDriverWait`'s fixed
500 ms poll, not the injection delay. This is the genuine, reproducible latency signature, and
it is coarser than chromedp's event-driven `WaitVisible` (verified below) and finer than rod's
backoff at long delays — as claimed.

### H4 — cold-start protocol-vs-binary decomposition (the highest-risk attribution, **re-run**) — CONSISTENT

| Config | worker p50 | my re-run p50 | my range |
|---|---:|---:|---:|
| full Chrome + `--headless=new`, SM each call | 848 | 839 | 828–853 |
| full Chrome + `--headless=new`, explicit driver | 818 | **808** | 802–829 |
| **chrome-headless-shell (binary-matched), explicit driver** | 168 | **125** | 116–295 |
| chromedp (same host, from its artifact) | 102 | — | — |
| rod (same host, from its artifact) | 119 | — | — |

`selenium_manager_per_call_tax_ms_p50` = 31 (worker 30), `ranges_overlap=true` → correctly
called noise. **The attribution holds and is the experiment, not conjecture:** the ~683 ms
gap between full-Chrome (808) and headless-shell (125) is produced by swapping **only the
browser binary** (same driver, same W3C protocol), and the matched headless-shell binary puts
Selenium at 125 ms — only ~20 ms above chromedp / rod. So the chromedriver/W3C overhead is
small (my run makes it even smaller than the worker's), and the ~650 ms is the full-Chrome +
new-headless binary. The pack's "the gap is the binary, not the protocol" is **directly
measured by the binary-matched decomposition** — no脑补. It refutes the "8× slower" SERP trope
**without** overcorrecting into "Selenium is fast": it still states headless-shell 168 (my 125)
is "the slowest of the three."

### H5 — concurrency two-tier process count (**re-run**) — CONSISTENT

| Mode | worker wall p50 | my wall p50 | browser peak | driver peak | my errors |
|---|---:|---:|:--:|:--:|:--:|
| shared (1 driver, 4 tabs, serial) | 2942 | 2932 | 1/1 | 1/1 | none |
| separate (4 drivers, concurrent) | 1243 | 1216 | 4/4 | 4/4 | none |

`wall_ranges_overlap=false` (disjoint) reproduced. The **durable, deterministic finding — the
two-tier process count (1+1 vs 4+4)** — reproduced exactly: separate mode spends 4
chromedrivers **on top of** 4 browsers (8 total), where chromedp/rod's separate mode is 4
procs with no driver tier. Shared session is serial (~2932 ms ≈ 4× per-tab); Selenium cannot
reach the CDP drivers' "1 process, N concurrent pages." The absolute wall is honestly scoped
to full-Chrome in the pack.

### H3 — presence vs visibility (verified by artifact self-consistency) — CONSISTENT
`find_element` (presence) returns on the `display:none` attached node (~5 ms, 3/3); explicit
`visibility_of_element_located` times out at the 4 s deadline with a clean `TimeoutException`
(~4168 ms, 3/3); `By.CSS_SELECTOR` and `By.XPATH` both resolve the visible node; the
never-appearing selector honors the 2 s deadline cleanly. Mirrors chromedp `WaitReady`-vs-
`WaitVisible` / rod `Element`-vs-`WaitVisible`, with no chromedp-#440-style default-query trap
(Selenium's locators are explicit). Deterministic across 3 runs.

---

## Full-Chrome / headless-shell mix — honesty judgment: CLEAN

The prompt's key concern: lifecycle/concurrency/recall run on **full Chrome + `--headless=new`**
(needed because a client `--user-data-dir` on chrome-headless-shell trips "unable to discover
open pages", and the pgrep-by-udd process-truth needs that dir), while H4's cold-start
attribution uses the binary-matched **chrome-headless-shell**. This mix is **disclosed
everywhere** (metadata "Chrome-binary choice (parity note, honest)"; research-materials Test
Environment + Gaps; the probe docstring) with the reason stated. And it does **not** create an
apples-to-oranges cross-tool comparison:

- **Cold-start** — the only place startup cost is compared to chromedp/rod — uses the **matched
  headless-shell** (168/125 ms vs chromedp 102 / rod 119). The full-Chrome 818 is presented
  separately and attributed to the binary; it is **never** passed off as the number to beat
  chromedp/rod with.
- **Lifecycle & concurrency** headline the **process count / architecture** (two-tier orphan;
  1+1 vs 4+4), which is structural to Selenium's `python→chromedriver→chrome` chain and
  **binary-independent**. The full-Chrome-specific **wall** numbers are explicitly scoped as
  such and not hardened into a speed win.
- **Recall** depends on DOM/JS timing (same Blink/V8 build 1232 across both headless variants),
  so which classes are found is binary-independent — the cross-tool recall axis stays valid.

No full-Chrome number masquerades as a headless-shell number. The disclosure is complete and
the comparison discipline holds.

---

## Four-class leak audit (Part 6)

**D1 — self-contradicting winner sentence: PASS.** Weights sum to 100; selenium=79 (re-added
by hand: 8+12+9+8+7+7+6+8+6+8). The 79-vs-84-vs-85 spread is the exact net of evidence-anchored
per-dimension deltas: vs chromedp, +1 wait-clarity (no #440 trap, reproduced), −1 lifecycle
(two-tier orphan, reproduced), −2 cold-start (headless-shell 168 slowest-of-three, reproduced),
−3 concurrency (4+4 procs + serial, reproduced) = −5 → 79. Selenium **honestly loses three
dimensions** (lifecycle 7, cold-start 7, concurrency 6) — exactly where my re-runs show it is
worse. There is **no "Selenium is fast/best" sentence** contradicted by its own full-Chrome
818 ms (H4 explicitly keeps headless-shell 168 "the slowest of the three"), and **no "Selenium
is slow" 8× myth** left standing either (the decomposition breaks it). Both directions threaded
correctly.

**D2 — blind instrument: PASS.** The lifecycle counter registers **both** reap (1→0 both tiers
on quit) and non-reap (1→1 both tiers on no-quit/crash) — positive+negative control, exercised
in my re-run, with the two tiers instrumented separately (pgrep-udd vs pid-liveness). The
recall instrument registers both presence (finds C under the waits) and absence (misses C under
`page_source`). Class B/C markers+hrefs are assembled from fragments in `fixture_server.py`
(`'SYNC'+'_INJECTED_'+…`, `5+6`, `6*7`), so a "found" proves JS **executed**, not bytes read.
Neither instrument is blind.

**D3 — mis-attribution: PASS.** class-C miss → reading before the post-load injection
(validated by the gradient: found at 0 ms, missed ≥100 ms). two-tier orphan → missing
teardown / no parent-death signal (validated by the **same-harness** quit-vs-no-quit-vs-crash
contrast — only the teardown differs, ruling out a confounder). cold-start gap → the **binary**,
validated by the headless-shell decomposition (125–168 ms), ruling out "Selenium's protocol is
slow." concurrency per-tab wall → honestly scoped to full-Chrome, not generalized. No harness
artifact substituted for a finding.

**D4 — claim-without-artifact: PASS.** Spot-checked 5 headline numbers, all resolve to a JSON
field: driver 151.0.7922.47 → `provisioning.reading.resolved_driver_version`; 567 ms
quantization → `recall.injection_timing_gradient[1].explicit.elapsed_ms`; two-tier orphan 1→1
→ `lifecycle.reading.exit_browser_procs_after` + `exit_chromedriver_orphaned`; headless-shell
168 → `coldstart.cold_start_ms_headless_shell.p50`; 1+1 vs 4+4 →
`concurrency.{shared,separate}.{chrome_browser,chromedriver}_procs_peak`. The **cross-tool
comparison numbers are real same-host artifact citations** (verified exact against the sibling
files): chromedp cold-start p50 **102**, rod **119**, chromedp `WaitVisible` gradient
**[109,208,519,911,1625]**, rod `Element` gradient **[12,214,628,1428,2858]**, chromedp shared
concurrency **214 ms / 1 proc** — every one matches `tools/chromedp/…` and `tools/rod/…`
verbatim, not inferred from prose.

---

## Novelty classification (three-gate) + evidence — Gate-1 CLEAN

Verified against Selenium's official docs (from training knowledge) + the pack's cited issue/
doc sources. **Key result: the pack does NOT repeat the chromedp mislabel.** The chromedp audit
had to downgrade a macOS-orphan tag from EXCLUSIVE to KNOWN-ISSUE; here the mirror finding
(two-tier orphan) is already tagged **"KNOWN behavior + EXCLUSIVE quantification"**, explicitly
citing the docs' `quit()`-or-leak warning for the *behavior* and claiming only the **two-tier
pgrep+pid count + exit-vs-crash proof** as EXCLUSIVE.

- **W3C WebDriver, chromedriver-as-separate-process, Selenium Manager existence + auto-download,
  `quit()`-required, explicit-vs-implicit waits, presence-vs-visibility semantics — DOCUMENTED.**
  Correct — all are standard selenium.dev-documented behaviors (existence, not this pack's values).
- **SM resolves a build-matched driver taking the latest patch (.47 ≠ .10); cold ~4 s vs warm
  ~25 ms (~156×); stale 145 not reused — EXCLUSIVE (quantification).** Behavior documented;
  the resolved patch + cost split + stale-reuse behavior on a controlled build are zero-hit
  measurements. Defensible.
- **default `page_source` misses post-load C; explicit wait recovers it; 500 ms poll
  quantization vs chromedp/rod on one fixture — EXCLUSIVE (quantification).** Mechanism (0.5 s
  default poll) is documented (see C2 — cite it); the per-timing recall + latency signature is
  the measurement. Correct posture.
- **presence vs visibility diverge on `display:none`; no #440 trap — DOCUMENTED semantics /
  EXCLUSIVE demonstration.** Correct.
- **two-tier orphan (both tiers, exit + crash); `quit()` reaps both — KNOWN behavior +
  EXCLUSIVE quantification.** Correct — the exact Gate-1 trap chromedp fell into, here avoided.
- **cold-start binary-vs-protocol decomposition; concurrency two-tier cost — EXCLUSIVE
  (quantification) / KNOWN limitation + EXCLUSIVE quantification.** Defensible; session
  non-thread-safety is documented, the two-tier process cost is the measurement.

No EXCLUSIVE tag sits on a merely-documented qualitative conclusion; every EXCLUSIVE is scoped
to "(quantification)" or "(demonstration)". Gate-1 clean.

## Anti-hardcoding lint: PASS

`classify()` lives **only** in `run_recall.py`; `grep -rnE 'classify|A_static|B_sync|C_delayed|
classes_found'` over `tests/harness/selenium_probe.py` is **empty** — the probe returns raw
`page_source`/hrefs/booleans/timings/pids only. No result constant (4054, 848, 818, 168, 2942,
1243, 567, 156, 30, 650, 99…) appears as a literal in the probe or runners. All conclusions are
computed: `elapsed_ms`/`reap_ms`/`wall_ms` = `time.time()` deltas; `reaped_both` =
`after==0 and not alive`; `both_orphaned` = `alive and procs>0`; recall booleans = Python
`classify()` of ground-truth markers vs rendered `page_source`; `cold_over_warm_ratio`,
`p50`/`min`/`max`, `*_ranges_overlap`, `reused_stale_145`, `driver_matches_browser_build` all
derived from measured output. The literal marker fragment in the poll (`"DELAYED"+"_INJECTED_"+
"MARKER"+"_C"`) is an assembled **search target** matching the fixture design, not a stored
result. Fixture markers are legitimately pre-registered ground truth.

## Secret / cleanliness scan

- **Credentials: CLEAN.** No `sk-*`/`API_KEY`/`token=`/`Bearer`/`ghp_`/AWS/private-key patterns
  in any publish-bound file (`*.md`, `tests/**/*.py`, `artifacts/raw/*.json`), excluding
  `.venv`/`__pycache__`/logs.
- **Absolute paths: NOW CLEAN (after F1).** No literal `/Users/…`, no `richardli` username
  anywhere. The 5 `/var/folders/…/T/` temp paths in `provisioning-summary.json` were the one
  leak; desensitized to `$TMPDIR` + the runner's `_redact` hardened so future runs stay clean.
  metadata / all other JSON use `~/…` (tilde) correctly.
- **`.gitignore` present:** covers `.venv/`, `__pycache__/`, logs, `chromedriver`/`*chromedriver*/`,
  `selenium-manager`, `.cache/selenium/`, and `sel_*/`, `se_prov_*/` temp dirs. No driver or
  browser binary is copied into the pack (only paths + versions recorded).

---

## Residual gaps the writer must not overclaim (the pack lists these; keep them)

1. **All numbers are single-machine macOS arm64 + one Chrome build**, local fixture. The
   two-tier orphan is macOS-scoped (Linux chromedriver child-death may differ) — keep it scoped.
2. **Full Chrome vs headless-shell only decomposed for cold-start.** Lifecycle/concurrency ran
   on full Chrome; the absolute concurrency wall is that-binary-specific (headless-shell per-tab
   would be lower). Keep the process count as the durable claim, wall as scoped.
3. **Selenium Manager offline/air-gapped behavior, Firefox/Edge provisioning, N≫4 concurrency,
   Remote/Grid, `execute_cdp_cmd` — untested.** Do not imply otherwise.
4. **The two-tier orphan is a KNOWN behavior** (`quit()`-or-leak) — the contribution is the
   pgrep+pid measurement, not the discovery; frame it that way (the pack already does).

---

_Audit re-ran all five measurement harnesses in the pack's clean venv on 2026-07-24 in the
pack's own layout; the pack's original artifact JSONs were restored afterward (my reproduction
values are recorded above and match within timing noise). Post-run sweep: 0 chromedriver, 0
Chrome-for-Testing, 0 chrome-headless-shell processes, 0 leftover temp dirs; the user's real
`~/.cache/selenium` was never modified (H0 used isolated `tempfile` caches)._

**Net status: PASS WITH FIXES.** All five headlines reproduced (H0/H2 must-run + H1/H4/H5,
H3 by artifact self-consistency); the two-tier orphan is a real same-harness process-truth
contrast; the cold-start binary-vs-protocol attribution is a measured decomposition; every
chromedp/rod comparison number is an exact same-host-artifact citation; D1–D4 clean; novelty
Gate-1 clean (no EXCLUSIVE-on-documented mislabel — the chromedp trap is avoided); anti-hardcoding
and secret scans clean. The full-Chrome/headless-shell mix is honestly disclosed and does not
contaminate the comparison. The one required fix (F1, cosmetic abspath) is applied in-place and
changed no measured value; C1/C2 are cosmetic writer-notes. The 79-vs-84-vs-85 spread is the
honest arithmetic of evidence-anchored dimension deltas, with Selenium losing lifecycle,
cold-start, and concurrency.
