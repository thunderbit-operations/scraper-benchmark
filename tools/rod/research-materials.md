# rod — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **rod**
(`github.com/go-rod/rod`), a **pure-Go library that drives a real Chrome over the Chrome
DevTools Protocol** (no Selenium/WebDriver server, no Node runtime) — the
higher-ergonomics sibling of chromedp. It judges the **behavior of that live-browser
driver on controlled ground truth**: whether rod's auto-wait recovers runtime-injected
DOM content out of the box, how its wait primitives behave at their edges, whether its
default **leakless** guardian actually prevents the macOS orphan chromedp leaves,
cold-start cost, and the concurrency model. It does **not** score Chrome itself, nor field
extraction (rod hands you the DOM/elements; what you pull out is your code).

**Direct comparison object: chromedp** (`tools/chromedp/`, published, commit `a605159`).
rod and chromedp are the two Go CDP drivers; every rod test here ran on the **identical
fixture, harness shape, host, and Chrome build** used for chromedp, so the numbers are
apples-to-apples. Central question (from the pre-test gate): the consensus says rod is
"more ergonomic than chromedp — auto-wait just works," and that leakless "prevents zombie
browser processes." Each is **qualitative**. This pack measures rod's per-idiom recall by
injection timing, its wait-primitive semantics on a controlled node, the leakless
orphan/reap process-outcome (with an on/off toggle), cold-start distribution, and the
shared-vs-separate concurrency cost — each next to chromedp's published number.

All tests run against a **local fixture on 127.0.0.1** (rod's Chrome hits loopback). No
third-party or production host is driven; no anti-bot, no auth bypass, no rate abuse.
**Cross-series axis:** the class-C runtime-injected node here is the same content class
katana's static crawl misses, playwright-mcp's live a11y snapshot catches, and chromedp
catches only with an explicit `WaitVisible` — rod is the fourth same-fixture data point,
and the axis on which its auto-wait ergonomics are supposed to pay off.

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-24** (see `metadata-snapshot.md`; refresh
within 48h before any final draft):

| Field | Value |
|---|---|
| Repo | [go-rod/rod](https://github.com/go-rod/rod) |
| Stars | **7,035** |
| Open issues | **209** |
| License | **MIT** |
| Default branch | **main** |
| Last push | **2026-07-15T20:12:13Z** |
| Version tested | **v0.116.2** (`go get github.com/go-rod/rod@v0.116.2`) |
| leakless | **v0.9.0** (`github.com/ysmood/leakless`, transitive) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (25F84) arm64 |
| rod | **v0.116.2** |
| leakless | **v0.9.0** |
| Go toolchain | **go1.26.5 darwin/arm64** |
| Chrome | **Chrome for Testing 151.0.7922.10** headless shell (build 1232, ms-playwright cache) — **same binary chromedp used**, via `launcher.Bin()` (parity, not rod's default Chromium 1321438) |
| Python (orchestrator) | **3.14** (clean venv-free stdlib; runners import stdlib only) |
| Recall runner | [tests/run_recall.py](tests/run_recall.py) → [recall-summary.json](artifacts/raw/recall-summary.json) |
| Wait-semantics runner | [tests/run_waitsem.py](tests/run_waitsem.py) → [waitsem-summary.json](artifacts/raw/waitsem-summary.json) |
| Lifecycle runner | [tests/run_lifecycle.py](tests/run_lifecycle.py) → [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json) |
| Cold-start runner | [tests/run_coldstart.py](tests/run_coldstart.py) → [coldstart-summary.json](artifacts/raw/coldstart-summary.json) |
| Concurrency runner | [tests/run_concurrency.py](tests/run_concurrency.py) → [concurrency-summary.json](artifacts/raw/concurrency-summary.json) |
| Go probe | [tests/harness/main.go](tests/harness/main.go) (built to `rod_probe`) |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) (content classes A/B/C + wait-sem page + robustness routes — byte-identical to the chromedp fixture) |

Setup / reliability notes (recorded because they affect reproduction):

- **A Chrome binary is required at runtime.** rod's Go module is pure Go (no cgo in the
  dependency tree), but it drives an *external* Chrome. This pack passes the exact
  executable via `launcher.New().Bin(path)`, which **disables auto-download** (parity with
  chromedp's `ExecPath`). rod *can* auto-download a Chromium (default revision 1321438) if
  `Bin` is unset; the "pure Go" line is about the module, not the runtime.
- **leakless guardian download (one-time).** rod's default launcher enables **leakless**,
  which drops a small per-platform **guardian binary** (`leakless-arm64-<hash>`) into
  `$TMPDIR` on first use and spawns it. It is **not** copied into this pack; only its path
  is recorded. Cold-start runs pre-warm it so a one-time download does not pollute timing.
- **Anti-hardcoding split.** The Go probe returns *raw* rendered HTML, hrefs, and measured
  booleans/timings. **Recall is computed in Python** against the fixture's pre-registered
  ground-truth markers (`ground_truth.json`) — no verdict/observation string is baked into
  the probe (`classify()` lives only in `run_recall.py`; grep finds 0 class-recall logic in
  `main.go`).
- **Process-truth.** Orphan / reap / concurrency counts come from `pgrep` on a **unique
  `--user-data-dir`** per run, counting a process only if its executable basename is
  `chrome-headless-shell` and it carries **no** `--type=` flag — so Chrome helper processes
  *and the leakless guardian* (whose argv[0] is the leakless binary) are both excluded.
  This exe-basename guard is the rod-specific addition over chromedp's counter (chromedp had
  no guardian process to disambiguate).

## Test Coverage Completed

Fixture ground truth (`artifacts/raw/ground_truth.json`) — three content classes that
separate *when* content exists, byte-identical to the chromedp/playwright-mcp/katana
fixtures, plus a wait-semantics page and robustness routes:

- **Class A — static HTML `<a>`:** marker `STATIC_ALPHA_MARKER_A`, href `/page/alpha`,
  a literal in the served bytes. Present at parse.
- **Class B — sync-injected:** an `<a>` created by an **inline `<script>`** during initial
  parse; marker + href **assembled from fragments** so no contiguous literal exists in any
  served byte. Present by the load event.
- **Class C — delayed-injected:** an `<a>` created **`DELAY` ms after the load event** via
  `setTimeout`; marker + href assembled from fragments. A naive read after navigate cannot
  see it.
- Plus: a `/waitsem` page (visible node + attached-but-hidden `display:none` node), a
  `/failure/500` route and a `/broken` dead link, and leaf pages whose fetches the
  server-side counter records.

### H1 — recall matrix: rod idiom × content class (`recall-summary.json`)

Class-C injected 800 ms after load; each idiom run 3× (found-sets identical all three —
`determinism_found_sets.*.stable = true`):

| rod idiom | A static | B sync-injected | C delayed-injected | elapsed |
|---|:--:|:--:|:--:|---:|
| `none` (Navigate + read `HTML`) | ✓ | ✓ | **✗** | 43 ms |
| `WaitLoad` + read `HTML` | ✓ | ✓ | **✗** | 13 ms |
| **`Element("#delayed-injected")` (auto-wait)** | ✓ | ✓ | **✓** | 1555 ms |
| poll until marker | ✓ | ✓ | **✓** | 851 ms |

Computed contrast (`contrast` field): `C_delayed_found_by: ["element","poll"]`;
`naive_html_misses_C: true`; `waitload_html_misses_C: true`; `element_autowait_finds_C: true`.

Injection-timing gradient (`injection_timing_gradient`), `none` vs `Element` auto-wait —
with the chromedp `WaitVisible` reference on the identical fixture:

| C injected after load | rod `none` sees C? | rod `Element` sees C? | rod `Element` elapsed | chromedp `WaitVisible` elapsed |
|---:|:--:|:--:|---:|---:|
| 0 ms | yes (race) | yes | 12 ms | 109 ms |
| 100 ms | **no** | yes | 214 ms | 208 ms |
| 400 ms | **no** | yes | 628 ms | 519 ms |
| 800 ms | **no** | yes | 1428 ms | 911 ms |
| 1500 ms | **no** | yes | 2858 ms | 1625 ms |

Reading: rod's **idiomatic** path — querying the element — recovers the runtime-injected
node **with no explicit wait call**, because `Element` auto-waits (retries on a backoff
sleeper up to the page timeout). That is the ergonomic payoff over chromedp, whose
idiomatic `Navigate`+read misses the same node and needs an explicit `WaitVisible`. **But
the auto-wait is a property of *querying the element*, not of reading the page:** a naive
rod `HTML()` snapshot (`none`) and even `WaitLoad`+`HTML` **miss** class C for any post-load
delay ≥ ~100 ms — the identical footgun to chromedp's naive read; only the ergonomic
*default* differs. The 0 ms row is the boundary (`setTimeout(…,0)` can fire before the
immediate read). **Honest cost of the ergonomics:** `Element`'s elapsed *overshoots* the
injection delay (800→1428, 1500→2858 ms) because rod's auto-wait **polls on a backoff
interval** (DefaultSleeper `100ms → ×~2 → <1s`), whereas chromedp's event-driven
`WaitVisible` tracks the delay tightly (800→911, 1500→1625 ms). So rod's auto-wait is more
convenient but latency-looser than an explicit event-driven wait — a real
ergonomics-vs-latency tradeoff, measured, not asserted.

### H3 — Element vs WaitVisible semantics + selector model (`waitsem-summary.json`)

On the `/waitsem` page; each run 3× (identical all three):

| Target | Action | Result | elapsed |
|---|---|---|---:|
| `#hidden-target` (attached, `display:none`) | `Element` | **returns** | ~2 ms |
| `#hidden-target` (attached, `display:none`) | `Element.WaitVisible` | **times out** (`context deadline exceeded`) | 4000 ms |
| `#visible-target` | CSS `Element` | returns | ~4 ms |
| `#visible-target` | XPath `ElementX` | returns | ~6 ms |
| `#never-appears-xyz` | `Element` (2 s page timeout) | **times out** (`context deadline exceeded`) | 2002 ms |

Reading: rod's two primitives mean different things — `Element` = node **attached** to the
DOM; `Element.WaitVisible` = node **actually visible**. On an attached-but-`display:none`
node they diverge cleanly: `Element` returns in ~2 ms, `WaitVisible` blocks to the 4 s
page deadline and returns a clean `context deadline exceeded` (no hang). This mirrors
chromedp's `WaitReady` vs `WaitVisible` split exactly. rod's selector **model** is cleaner
than chromedp's here: CSS (`Element`) and XPath (`ElementX`) are separate methods, so
there is **no chromedp-#440-style trap** (chromedp's `WaitVisible("#id")` default-query
hang) — CSS and XPath both resolved the visible node. The never-appearing selector honors
the page timeout with a clean error — the deadline test.

### H2 — lifecycle: leakless reap vs orphan on macOS, process-truth (`lifecycle-summary.json`)

The headline. Process-truth via `pgrep` on a unique `--user-data-dir`; each path 3×. rod's
default launcher enables leakless (a guardian binary bridged to the Go process over TCP;
when the connection closes on parent exit **or** crash, the guardian kills the browser):

| Path | leakless | Chrome browser procs | Outcome |
|---|:--:|---|---|
| graceful `browser.Close()` (in-process) | on | 1 → **0** | **reaped**, reap_ms **16 / 15 / 13** |
| Go **exits without cleanup** | **on** | 1 → **0** | **reaped** (all 3) |
| Go **exits without cleanup** | **off** | 1 → **1** | **orphaned** (all 3), then force-cleaned |
| parent **SIGKILL** (crash) | on | 1 → **0** | **reaped** (all 3) |

**chromedp reference on the identical host** (`tools/chromedp/lifecycle-summary.json`):
cancel reaps in ~13 ms; **exit-without-cancel orphans 3/3** (macOS `allocate_other.go`
no-op — no parent-death signal).

Reading: this is the **opposite** conclusion from chromedp on macOS, and the reason is
proven, not asserted. With leakless **on** (rod's default), a Go process that exits
*without* any cleanup — and even one that is **SIGKILLed** mid-run — leaves **no orphan**:
the guardian sees its TCP connection to the parent close and kills the browser (1 → 0, all
3 runs, both paths). With leakless **off**, the *same* exit path orphans the browser 3/3 —
**identical to chromedp**. The on/off toggle isolates the guardian as the mechanism: rod
isn't magically safe, *leakless* is what makes the default safe on macOS where chromedp
orphans. Graceful `browser.Close()` reaps in ~15 ms, on par with chromedp's cancel.
**Honest boundary** ([#865](https://github.com/go-rod/rod/issues/865)): leakless fires on
**process exit/crash**, not on per-browser `Close()` inside a long-running process — a
server that churns browsers without exiting can still accumulate zombies; that scenario is
*not* exercised here. (Every orphan in this test was force-killed by the runner;
`all_orphans_cleaned: true`.)

### H4 — cold-start cost + the leakless tax (`coldstart-summary.json`, 5 fresh processes each)

Each sample is a genuinely cold cycle (fresh process: launcher → connect → page → navigate
→ first `Eval`), leakless ON and OFF interleaved so drift hits both:

| Config | p50 | min–max | mean |
|---|---:|---:|---:|
| **leakless on (rod default)** | **119 ms** | 117–124 | 119.4 |
| leakless off | 114 ms | 107–124 | 113.4 |
| **chromedp (same host/Chrome)** | **102 ms** | 98–111 | 102.8 |

`leakless_tax_ms_p50: 5`, `leakless_tax_ranges_overlap: true`. Reading: rod's default
cold start to first script result is ~119 ms p50 on this host — **modestly higher than
chromedp's ~102 ms**. The **leakless guardian tax is only ~5 ms p50 and the on/off ranges
overlap** (within noise), so leakless does **not** explain the rod-vs-chromedp gap; the
small remaining delta is rod's own launcher/connect overhead (its remote-object-id
protocol setup), near the noise floor (rod-off 107–124 vs chromedp 98–111 abut at ~110).
Both are cheap enough that per-invocation spin-up is not a bottleneck for occasional jobs.
Scoped to macOS arm64 + a warm on-disk headless shell. Confirms the runtime **external-
Chrome dependency**.

### H5 — concurrency: shared browser vs separate browsers (`concurrency-summary.json`)

N=4 navigations, 3 runs each mode, with the chromedp reference:

| Mode | rod wall p50 | rod wall min–max | rod peak procs | chromedp wall p50 | chromedp peak procs |
|---|---:|---:|:--:|---:|:--:|
| shared (1 browser, 4 pages) | **211 ms** | 210–211 | **1** | 214 ms | 1 |
| separate (4 browsers) | **1302 ms** | 1294–1306 | **4** | 264 ms | 4 |

`wall_ranges_overlap: false`. Reading: rod's **shared-browser** path (four pages on one
browser) is on par with chromedp — **one** Chrome process, ~211 ms (≈ chromedp's 214 ms).
But rod's **separate-browser** path is dramatically more expensive than chromedp's: four
independent launchers take **~1302 ms** (four processes) vs chromedp's 264 ms for the same
four separate browsers — a ~5× penalty, stable across reps (1294–1306). The process-count
lever (1 vs 4) is the durable, mechanism-clear finding, identical to chromedp; the steep
separate-browser wall-time penalty is rod-specific on this host. **Mechanism =
hypothesis:** the ~1300 ms is not the leakless tax (H4 measured that at ~5 ms/launch, far
too small); it is most plausibly rod's per-launcher browser-launch + connect overhead
compounding under 4-way concurrency (a single rod cold start is ~119 ms, so 4 concurrent
separate launches at ~1300 ms is an ~11× slowdown vs chromedp's ~2.6×) — but I did not run
a per-launch attribution experiment, so the *cause* is a hypothesis; the *numbers* are
measured. Durable takeaway: in rod, strongly prefer shared-browser pages over separate
browsers — even more than in chromedp.

### Robustness

The `/failure/500` and a non-existent `/broken` route are reachable; navigation surfaces
the outcome without crashing the driver (the process exits cleanly and later actions still
run). Recorded via the server-side hit counter and the runners' clean completion.

## Key Findings for the Writer

1. **FINDING-01 — rod's idiomatic `Element()` auto-waits and recovers post-load-injected
   content out of the box; a naive `HTML()` snapshot misses it (measured, 3× deterministic).**
   On class C (injected 800 ms post-load), `none` and `WaitLoad`+`HTML` recover A+B but
   **not** C; `Element("#delayed-injected")` and a poll recover all three, with no explicit
   wait call. This is the ergonomic win over chromedp (whose idiomatic `Navigate`+read
   misses C and needs an explicit `WaitVisible`). **Honest cost:** rod's auto-wait polls on
   a backoff sleeper, so its elapsed *overshoots* the injection delay (800→1428 ms) where
   chromedp's event-driven `WaitVisible` tracks it tightly (800→911 ms). Confidence: high
   (deterministic matrix + monotonic gradient). Cross-series: same class katana misses /
   playwright-mcp catches / chromedp catches only with an explicit wait.

2. **FINDING-02 — `Element` (attached) and `Element.WaitVisible` (visible) answer different
   questions; they diverge on an attached-but-hidden node (measured), and rod's selector
   model has no #440-style trap.** `Element` returns for a `display:none` node (~2 ms);
   `WaitVisible` blocks to the page deadline and returns a clean `context deadline exceeded`
   (4 s). CSS `Element` and XPath `ElementX` both resolve the visible node — no chromedp
   `ByID`-vs-default-query footgun. Never-appearing selector honors the deadline cleanly.
   Confidence: high (3× identical).

3. **FINDING-03 — rod's default leakless reaps Chrome on exit AND on crash on macOS, where
   chromedp orphans; the on/off toggle proves leakless is the cause (process-truth, 3×).**
   leakless **on**: Go exit-without-cleanup and parent SIGKILL both leave **0** browser
   processes (guardian TCP-close kill). leakless **off**: the same exit orphans 3/3 —
   identical to chromedp on macOS. Graceful `Close()` reaps in ~15 ms. This is the reverse
   of chromedp's macOS orphan, attributed to the leakless guardian, not to "rod is safe."
   **Boundary:** leakless covers process exit/crash, not per-browser churn in a long-running
   process ([#865](https://github.com/go-rod/rod/issues/865)). Confidence: high (pgrep
   process-truth; on/off toggle rules out a harness artifact).

4. **FINDING-04 — Cold start to first script result is ~119 ms p50 (distribution); the
   leakless tax is ~5 ms, within noise.** 117–124 ms over 5 fresh processes, modestly above
   chromedp's ~102 ms; leakless on/off differ by ~5 ms with overlapping ranges, so the
   rod-vs-chromedp gap is rod's launcher/connect overhead, not the guardian. Confidence:
   high (tight spread; tax isolated by an on/off experiment).

5. **FINDING-05 — Shared-browser pages cost 1 Chrome process (~211 ms, ≈ chromedp);
   separate browsers cost 4 processes and ~1302 ms — a ~5× wall-time penalty vs chromedp's
   264 ms (measured).** The 1-vs-4 process lever matches chromedp; rod's separate-launcher
   path scales far worse under concurrency on this host. Mechanism (per-launcher overhead
   compounding) is a hypothesis; the numbers are measured (disjoint, stable ranges).
   Confidence: high on process count + wall times; the *cause* of the separate-mode penalty
   is a hypothesis.

## Provisional Scorecard

Provisional, based only on the completed material tests. **Same frozen weight template as
the chromedp pack** (Part-3 rule 11), so the two Go CDP drivers are directly comparable.
Not a final benchmark. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **8** | chainable Must API; single Go binary; needs external Chrome (or auto-downloads); one-time leakless guardian drop |
| Static/sync-injected extraction | 12 | **12** | classes A+B 3/3 in every idiom (`recall-summary.json`) |
| Runtime (post-load) content | 12 | **10** | `Element` auto-wait recovers class C **out of the box** (ergonomic edge over chromedp); naive `HTML()` still misses it; auto-wait overshoots delay |
| Wait-action clarity | 10 | **8** | `Element`≠`WaitVisible` (attached vs visible) diverge cleanly; no #440-style trap; deadline honored |
| Context lifecycle / cleanup | 12 | **10** | default leakless reaps on exit **and** crash on macOS where chromedp orphans; #865 long-running-churn boundary holds it back |
| Cold-start cost | 10 | **8** | p50 119 ms (117–124); modestly above chromedp 102 ms; leakless tax ~5 ms (noise) |
| Concurrency model | 10 | **7** | shared 1 proc/211 ms (≈ chromedp); separate 4 procs/1302 ms (~5× chromedp) — prefer shared |
| Determinism | 8 | **8** | recall + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | **6** | driver survives 500 + dead link, later actions still run |
| Cost transparency | 10 | **8** | distributions with ranges; overlap⇒tie; leakless tax isolated by on/off experiment |
| **Total** | **100** | **85** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **Linux reap/orphan not run.** The leakless reap and the chromedp orphan are both
  macOS-scoped here; leakless is cross-platform but the Linux contrast (chromedp's
  `Pdeathsig` path) should be re-run before generalizing.
- **Long-running-process browser churn ([#865]) not exercised.** The leakless win is scoped
  to process exit/crash; a server that repeatedly opens/closes browsers without exiting is
  the known zombie scenario and is untested here.
- **Separate-mode concurrency cause not isolated.** The ~5× separate-browser penalty vs
  chromedp is measured but the mechanism (per-launcher overhead vs guardian-spawn
  contention) is a hypothesis; a leakless-off separate-mode run would attribute it.
- **Concurrency at N≫4 and with real per-page work untested.** Wall-time gaps are
  workload-specific; memory deltas are not measured (only process count).
- **Network interception / hijack, `WaitStable`, `Race` untested.** rod exposes rich CDP
  helpers; out of scope for this pack.
- **Single machine, single Chrome build.** All numbers are macOS arm64 + Chrome for Testing
  151.0.7922.10; cold-start and concurrency timings are host-specific.

## Novelty verification (pre-registration search)

Sources per finding: rod + leakless issue trackers, godoc/why-rod/selectors docs, and
top-~20 SERP. Verdict is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| pure-Go/CDP driver, chainable auto-wait API, `Element` vs `WaitVisible`, remote-object-id architecture, leakless-by-default & exit-kill | **DOCUMENTED** | [godoc](https://pkg.go.dev/github.com/go-rod/rod) + [why-rod](https://github.com/go-rod/go-rod.github.io/blob/main/why-rod.md) + [launcher godoc](https://pkg.go.dev/github.com/go-rod/rod/lib/launcher); existence, not this pack's value |
| `Element` auto-wait recovers post-load content out of the box; naive `HTML()` misses it; auto-wait elapsed overshoots the injection delay (backoff) vs chromedp's tight `WaitVisible` | **EXCLUSIVE (quantification)** | No SERP/issue source measures rod's per-injection-timing recall by idiom, nor the backoff overshoot vs chromedp on the same fixture; zero-hit |
| `Element`=attached vs `WaitVisible`=visible diverge on `display:none`; no #440-style selector trap | **DOCUMENTED semantics / EXCLUSIVE demonstration** | Docs define attached vs visible + separate CSS/XPath methods; the measured `display:none` divergence + clean deadline is this pack's |
| leakless reaps on exit **and** SIGKILL on macOS where chromedp orphans; on/off toggle attribution | **KNOWN behavior + EXCLUSIVE quantification** | leakless is documented to kill the browser on process exit ([launcher godoc]; why-rod's "no zombie on Mac"); the cross-tool **pgrep process-truth** (0 vs chromedp's orphan), the SIGKILL crash proof, and the leakless-on/off attribution are this pack's |
| leakless does **not** cover per-browser churn in a long-running process (zombies remain) | **KNOWN-ISSUE** | [#865](https://github.com/go-rod/rod/issues/865) — stated as a boundary, not exercised here |
| Cold-start ~119 ms p50; leakless tax ~5 ms (noise); shared 1 proc/211 ms vs separate 4 procs/1302 ms | **EXCLUSIVE (quantification)** | No SERP source publishes rod's cold-start distribution, the isolated leakless tax, or shared-vs-separate process/wall numbers |

[#865]: https://github.com/go-rod/rod/issues/865

**Consequence for the writer:** the information-gain items are all *measurements or
mechanisms behind documented behavior* — the per-idiom recall matrix and auto-wait
overshoot, the `Element`-vs-`WaitVisible` `display:none` divergence, the leakless
reap-vs-orphan process-truth (with on/off attribution and a SIGKILL crash proof), and the
cold-start/leakless-tax/concurrency numbers. Every claim carries a confidence label and
points to a JSON field; the separate-mode concurrency *cause* is honestly marked a
hypothesis.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* Comparatives with a direction
   (concurrency shared vs separate; rod vs chromedp cold-start) are reported with ranges +
   the overlap⇒tie rule: concurrency ranges are **disjoint** (211 vs 1302 ms); cold-start
   is called "modestly higher" with the note that rod-off vs chromedp ranges **abut** (near
   noise), not a bold "slower." H1 elapsed differences are framed as recall/latency cost,
   not a speed win — `Element` being *slower* (1555 ms) is correctly the cost of waiting.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`recall-summary.json`, `waitsem-summary.json`, `lifecycle-summary.json`,
   `coldstart-summary.json`, `concurrency-summary.json`). The leakless "no orphan" claim is
   backed by the pgrep on/off measurement, **not** by the doc alone; the SIGKILL crash claim
   is backed by the kill-path runs, not by why-rod's prose.
3. **Blind instrument (D2)** — *Pass.* Recall is computed against pre-registered
   ground-truth markers and the instrument registers **both** presence and absence (misses C
   under `none`, catches it under `Element`). The process counter registers both reap (1→0)
   and non-reap (leakless-off 1 survives) — not blind. Class B/C markers are assembled from
   fragments, so a "found" requires the browser to have *executed* JS.
4. **Mis-attribution (D3)** — *Pass.* The class-C miss is attributed to reading before the
   post-load injection — validated by the gradient (found at 0 ms, missed at ≥100 ms). The
   leakless reap is attributed to the guardian — validated by the **on/off toggle** (off
   orphans identically to chromedp), ruling out "rod is magic." The separate-mode
   concurrency penalty's *cause* is explicitly left a **hypothesis** (leakless tax measured
   too small to explain it).
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a
   verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over this file
   surfaces only "Honest cost/boundary" transparency labels (rule-required), not self-praise
   adjectives on the tool.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-24** in `metadata-snapshot.md`. Stars (7,035) /
  version (v0.116.2) traceable to that GitHub fetch.
- **Versions:** tested rod v0.116.2, leakless v0.9.0, Go 1.26.5, Chrome for Testing
  151.0.7922.10 (build 1232) — read from `go list -m`, the run summaries, and the Chrome
  `--version`.

## Raw Artifact Index

- Recall matrix + gradient: [recall-summary.json](artifacts/raw/recall-summary.json)
- Wait semantics: [waitsem-summary.json](artifacts/raw/waitsem-summary.json)
- Lifecycle (leakless reap / orphan): [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json)
- Cold start (+ leakless tax): [coldstart-summary.json](artifacts/raw/coldstart-summary.json)
- Concurrency: [concurrency-summary.json](artifacts/raw/concurrency-summary.json)
- Ground truth: [ground_truth.json](artifacts/raw/ground_truth.json)
