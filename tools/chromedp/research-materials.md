# chromedp — Review Research Materials

Date: 2026-07-23

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **chromedp**
(`github.com/chromedp/chromedp`), a **pure-Go library that drives a real Chrome over
the Chrome DevTools Protocol** (no Selenium/WebDriver server, no Node runtime). It
judges the **behavior of that live-browser driver on controlled ground truth**:
whether/when it surfaces runtime-injected DOM content, how its wait actions behave at
their edges, how its context lifecycle reaps the spawned Chrome process, cold-start
cost, and the concurrency model. It does **not** score Chrome itself, nor field
extraction (chromedp hands you the DOM; what you pull out is your code). It does not
rank chromedp against other tools.

Central question (from the pre-test gate): the consensus says a headless browser
"sees the dynamic page" a static crawler misses, that `WaitVisible` beats
`WaitReady`, and that `defer cancel()` prevents Chrome leaks. Each is **qualitative**.
This pack builds a fixture whose content classes separate *when* content enters the
DOM, and measures per-class recall by wait strategy, the wait-action semantics on a
controlled node, the cancel-vs-orphan process outcome, cold-start distribution, and
the shared-vs-separate concurrency cost.

All tests run against a **local fixture on 127.0.0.1** (chromedp's Chrome hits
loopback). No third-party or production host is driven; no anti-bot, no auth bypass,
no rate abuse. **Cross-series axis:** the class-C runtime-injected node here is the
same content class katana's static crawl misses and playwright-mcp's live a11y
snapshot catches — chromedp is the third same-fixture data point.

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-23** (see `metadata-snapshot.md`;
refresh within 48h before any final draft):

| Field | Value |
|---|---|
| Repo | [chromedp/chromedp](https://github.com/chromedp/chromedp) |
| Stars | **13,202** |
| Open issues | **178** |
| License | **MIT** |
| Latest tag | **v0.16.0** (latest GitHub *Release* object is v0.15.1, 2026-04-01) |
| Version tested | **v0.16.0** (`go get chromedp@latest` resolved v0.16.0 on snapshot day) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 arm64 |
| chromedp | **v0.16.0** (cdproto `v0.0.0-20260714215040-dc233986426f`) |
| Go toolchain | **go1.26.5 darwin/arm64** |
| Chrome | **Chrome for Testing 151.0.7922.10** headless shell (build 1232, ms-playwright cache) |
| Python (orchestrator) | **3.14** (clean venv-free stdlib; runners import stdlib only) |
| Recall runner | [tests/run_recall.py](tests/run_recall.py) → [recall-summary.json](artifacts/raw/recall-summary.json) |
| Wait-semantics runner | [tests/run_waitsem.py](tests/run_waitsem.py) → [waitsem-summary.json](artifacts/raw/waitsem-summary.json) |
| Lifecycle runner | [tests/run_lifecycle.py](tests/run_lifecycle.py) → [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json) |
| Cold-start runner | [tests/run_coldstart.py](tests/run_coldstart.py) → [coldstart-summary.json](artifacts/raw/coldstart-summary.json) |
| Concurrency runner | [tests/run_concurrency.py](tests/run_concurrency.py) → [concurrency-summary.json](artifacts/raw/concurrency-summary.json) |
| Go probe | [tests/harness/main.go](tests/harness/main.go) (built to `chromedp_probe`) |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) (content classes A/B/C + wait-sem page + robustness routes) |

Setup / reliability notes (recorded because they affect reproduction):

- **A Chrome binary is required at runtime.** chromedp's Go module is pure Go (no
  cgo), but it drives an *external* Chrome. Every run supplies the exact executable
  via `ExecPath`; with no Chrome present, a run fails immediately. The "no external
  dependencies" line applies to the Go module, not the runtime.
- **Binary, not `go test`.** chromedp issue [#1591] reports the Go-1.25+ `go test`
  runner cancelling `NewExecAllocator` mid-start; the same code runs fine under a
  built binary. This pack therefore `go build`s `chromedp_probe` and runs it — Go
  here is 1.26.5. No run used `go test`.
- **Anti-hardcoding split.** The Go probe returns *raw* rendered `outerHTML`, hrefs,
  and measured booleans/timings. **Recall is computed in Python** against the
  fixture's pre-registered ground-truth markers (`ground_truth.json`) — no verdict or
  observation string is baked into the probe.
- **Process-truth.** Chrome reap / orphan / concurrency counts come from `pgrep` on a
  **unique `--user-data-dir`** per run (counting only *browser* processes, i.e. those
  without a `--type=` flag). This is the process analog of the fixture's server-side
  hit counter — independent of chromedp's own return values.

## Test Coverage Completed

Fixture ground truth (`artifacts/raw/ground_truth.json`), three content classes that
separate *when* content exists, plus a wait-semantics page and robustness routes:

- **Class A — static HTML `<a>`:** marker `STATIC_ALPHA_MARKER_A`, href `/page/alpha`,
  a literal in the served bytes. Present at parse.
- **Class B — sync-injected:** an `<a>` created by an **inline `<script>`** during
  initial parse; marker (`SYNC_INJECTED_MARKER_B`) + href (`/sync/injected-11`)
  **assembled from fragments** so no contiguous literal exists in any served byte.
  Present by the load event.
- **Class C — delayed-injected:** an `<a>` created **`DELAY` ms after the load event**
  via `setTimeout`; marker (`DELAYED_INJECTED_MARKER_C`) + href
  (`/delayed/injected-42`) assembled from fragments. `Navigate` returns on the load
  event, so a naive read cannot see it.
- Plus: a `/waitsem` page (visible node + attached-but-hidden `display:none` node), a
  `/failure/500` route and a `/broken` dead link, and leaf pages whose fetches the
  server-side counter records.

### H1 — recall matrix: wait strategy × content class (`recall-summary.json`)

Class-C injected 800 ms after load; each strategy run 3× (found-sets identical all
three — `determinism_found_sets.*.stable = true`):

| Strategy | A static | B sync-injected | C delayed-injected | elapsed |
|---|:--:|:--:|:--:|---:|
| `none` (Navigate + read) | ✓ | ✓ | **✗** | 317 ms |
| `WaitReady("body")` | ✓ | ✓ | **✗** | 107 ms |
| `WaitVisible("#delayed-injected")` | ✓ | ✓ | **✓** | 912 ms |
| poll until marker | ✓ | ✓ | **✓** | 972 ms |

Computed contrast (`contrast` field): `C_delayed_found_by: ["waitvisible","poll"]`;
`naive_navigate_misses_C: true`; `waitready_body_misses_C: true`;
`waitvisible_node_finds_C: true`.

Injection-timing gradient (`injection_timing_gradient`), `none` vs `WaitVisible`:

| C injected after load | `none` sees C? | `WaitVisible` sees C? | `WaitVisible` elapsed |
|---:|:--:|:--:|---:|
| 0 ms | yes (race) | yes | 109 ms |
| 100 ms | **no** | yes | 208 ms |
| 400 ms | **no** | yes | 519 ms |
| 800 ms | **no** | yes | 911 ms |
| 1500 ms | **no** | yes | 1625 ms |

Reading: a live browser surfaces the runtime-injected node — but only with a wait
**keyed to that node**. `Navigate` returns on the load event, so a naive read and even
`WaitReady("body")` (body is ready at load) both miss class C for any post-load delay
≥ ~100 ms; `WaitVisible` on the node (or a poll) recovers it, and its elapsed tracks
the injection delay almost exactly (100→208, 400→519, 800→911, 1500→1625 ms) —
evidence it genuinely waited, not that it read early. The 0 ms row is the boundary:
`setTimeout(…,0)` can fire before the immediate read, so `none` occasionally catches
it — which is why the finding is scoped to delay ≥ ~100 ms.

### H2 — WaitReady vs WaitVisible semantics + selector query (`waitsem-summary.json`)

On the `/waitsem` page; each run 3× (identical all three):

| Target | Action | Result | elapsed |
|---|---|---|---:|
| `#hidden-target` (attached, `display:none`) | `WaitReady` | **returns** | ~12 ms |
| `#hidden-target` (attached, `display:none`) | `WaitVisible` | **times out** (`context deadline exceeded`) | 4000 ms |
| `#visible-target` | `WaitVisible` default query | returns | ~7 ms |
| `#visible-target` | `WaitVisible` `ByID` | returns | ~1 ms |
| `#visible-target` | `WaitVisible` `ByQuery` | returns | ~1 ms |

Reading: the two waits mean different things — `WaitReady` = node **attached** to the
DOM; `WaitVisible` = node **actually visible**. On an attached-but-`display:none` node
they diverge cleanly: `WaitReady` returns in ~12 ms, `WaitVisible` blocks to the 4 s
context deadline and returns a clean `context deadline exceeded` (no hang — the
deadline test). So "`WaitVisible` is more reliable" is imprecise; they answer
different questions, and picking `WaitReady` for a node you actually need *visible*
(or `WaitVisible` for one that never becomes visible) is the real trap.
**Honest negative:** the [#440] `WaitVisible("#id")` default-query hang did **not**
reproduce here — default query, `ByID`, and `ByQuery` all returned on `#visible-target`
in v0.16.0 (`selector_440_hang_reproduced: false`).

### H3 — context lifecycle: reap on cancel vs orphan on exit (`lifecycle-summary.json`)

Process-truth via `pgrep` on a unique `--user-data-dir`; each path 3×:

| Path | Chrome browser procs | Outcome |
|---|---|---|
| `defer cancel()` (cancel ctx+allocator) | 1 → **0** | **reaped**, reap_ms **13 / 13 / 12** |
| exit **without** cancel (macOS) | 1 → **1** (survives probe exit) | **orphaned** (all 3), then force-cleaned to 0 |

Reading: cancelling the context (and allocator) reaps the spawned
`chrome-headless-shell` in ~13 ms — chromedp starts Chrome with
`exec.CommandContext`, whose cancel kills the process. But a Go process that **exits
without cancelling** leaves Chrome **orphaned on macOS** (measured: the browser
process survives the probe's exit in all 3 runs). chromedp's godoc promises the default
command sends `SIGKILL` "to any open browsers when the Go program exits" **as if
universal**, but that parent-death cleanup lives only in build-tagged source
(`allocate_linux.go` sets `Pdeathsig=SIGKILL`; `allocate_other.go` on macOS is a no-op) —
so on macOS there is no equivalent signal, making the finding a **source-derived
correction to an over-promising godoc**. The `defer cancel()` discipline is therefore
load-bearing on macOS, not cosmetic — skip it and exit, and you leak a browser. This is
a known, platform-scoped non-exit behavior
([#774](https://github.com/chromedp/chromedp/issues/774) FreeBSD,
[#752](https://github.com/chromedp/chromedp/issues/752) macOS hanging; mechanism
[#562](https://github.com/chromedp/chromedp/issues/562)/[#1566](https://github.com/chromedp/chromedp/issues/1566)),
so the pack's contribution is the process-truth quantification, not the discovery.
(Every orphan in this test was force-killed by the runner; `all_orphans_cleaned: true`.)

### H4 — cold-start cost (`coldstart-summary.json`, 5 fresh processes)

Each sample is a genuinely cold cycle (fresh process: allocator → context → navigate →
first `Evaluate`):

| p50 | min–max | mean |
|---:|---:|---:|
| **102 ms** | 98–111 | 102.8 |

Reading: a full chromedp cold start to first script result is ~100 ms on this host
with a local headless shell — cheap enough that per-invocation browser spin-up is not
a bottleneck for occasional jobs. Scoped to macOS arm64 + a warm on-disk Chrome
binary; a first-ever launch that has to page the 155 MB binary in from cold disk would
be higher. Confirms the runtime **external-Chrome dependency** (the number is
allocator+Chrome-launch dominated).

### H5 — concurrency: shared browser vs separate browsers (`concurrency-summary.json`)

N=4 navigations, 3 runs each mode:

| Mode | wall p50 | wall min–max | peak Chrome browser procs |
|---|---:|---:|:--:|
| shared (1 browser, 4 child contexts/tabs) | **214 ms** | 209–219 | **1** |
| separate (4 browsers) | **264 ms** | 261–278 | **4** |

Verdict (`verdict` field): `wall_ranges_overlap: false`. Reading: sharing one browser
across four child contexts (tabs) does the same four navigations in **one** Chrome
process and a disjoint, lower wall-time band (214 vs 264 ms p50); spinning up four
separate browsers spends **4×** the OS browser processes for a measurably (non-
overlapping) higher wall time on this trivial workload. The process-count gap (1 vs 4)
is the durable finding; the ~1.2× wall-time gap is modest and workload-specific (four
tiny pages). For real per-page work the process/memory saving of the shared-browser
model is the main lever.

### Robustness

The `/failure/500` and a non-existent `/broken` route are reachable; `Navigate`
surfaces the outcome without crashing the driver (the process exits cleanly and later
actions still run). Recorded via the server-side hit counter and the runners' clean
completion.

## Key Findings for the Writer

1. **FINDING-01 — A live browser sees runtime-injected content only with a wait keyed
   to the node; `Navigate` and `WaitReady("body")` both miss it (measured, 3×
   deterministic).** On class C (injected 800 ms post-load), `none` and
   `WaitReady("body")` recover A+B but **not** C; `WaitVisible("#delayed-injected")`
   and a poll recover all three. `WaitVisible`'s elapsed tracks the injection delay
   (100→208 … 1500→1625 ms). The consensus "just use a headless browser" is
   incomplete: you need the browser **and** a wait targeting the injected node.
   Confidence: high (deterministic matrix + monotonic gradient). Cross-series: same
   class katana static misses / playwright-mcp catches.

2. **FINDING-02 — `WaitReady` and `WaitVisible` answer different questions; they
   diverge on an attached-but-hidden node (measured).** `WaitReady` returns for a
   `display:none` node (~12 ms); `WaitVisible` blocks to the context deadline and
   returns a clean `context deadline exceeded` (4 s). "WaitVisible is more reliable" is
   really "they mean different things." The [#440] default-query hang did **not**
   reproduce in v0.16.0. Confidence: high (3× identical); negative result reported
   honestly.

3. **FINDING-03 — Cancel reaps Chrome in ~13 ms; on macOS, exit-without-cancel
   orphans it (process-truth, 3×).** `defer cancel()` kills the spawned browser fast
   (`exec.CommandContext`); dropping the cancel and exiting leaves an orphaned
   `chrome-headless-shell` on macOS — a known platform-scoped non-exit
   ([#774](https://github.com/chromedp/chromedp/issues/774)/[#752](https://github.com/chromedp/chromedp/issues/752));
   the godoc's SIGKILL-on-exit cleanup is in Linux-tagged source only, so the pack
   contributes the process-truth measurement, not the discovery. The
   `defer cancel()` discipline is load-bearing on macOS, not cosmetic. Confidence:
   high (pgrep process-truth; cancel-vs-orphan contrast under the identical harness
   rules out a harness artifact).

4. **FINDING-04 — Cold start to first script result is ~102 ms p50 (distribution).**
   98–111 ms over 5 fresh processes on macOS arm64 with a warm on-disk headless shell.
   Cheap per-invocation spin-up; scoped to this host/binary state. Confidence: high
   (tight spread).

5. **FINDING-05 — Shared-browser tabs cost 1 Chrome process; separate browsers cost N
   (measured), with a modest non-overlapping wall-time edge to shared.** 4 navigations:
   shared = 1 process / 214 ms p50; separate = 4 processes / 264 ms p50 (ranges
   disjoint). The process/memory saving of child contexts over separate browsers is the
   real lever; the wall-time gap is small on trivial pages. Confidence: high on process
   count; medium on the wall-time gap (workload-specific).

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark and not
a cross-tool ranking. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **8** | single Go binary; pure-Go module, but requires an external Chrome (supplied via `ExecPath`) |
| Static/sync-injected extraction | 12 | **12** | classes A+B 3/3 in every strategy (`recall-summary.json`) |
| Runtime (post-load) content | 12 | **9** | class C recovered only with a node-keyed wait/poll; `Navigate`+`WaitReady(body)` miss it |
| Wait-action clarity | 10 | **7** | `WaitReady`≠`WaitVisible` (attached vs visible) diverge cleanly; deadline honored; #440 not reproduced |
| Context lifecycle / cleanup | 12 | **8** | cancel reaps in ~13 ms; macOS exit-without-cancel orphans (Linux-scoped guarantee) |
| Cold-start cost | 10 | **9** | p50 102 ms, tight (98–111) over 5 fresh runs |
| Concurrency model | 10 | **9** | shared browser 1 proc / 214 ms vs 4 procs / 264 ms; ranges disjoint |
| Determinism | 8 | **8** | recall found-sets + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | **6** | driver survives 500 + dead link, later actions still run |
| Cost transparency | 10 | **8** | distributions with ranges; overlap⇒tie logic applied to concurrency |
| **Total** | **100** | **84** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **Linux reap/orphan not run.** The orphan-on-exit finding is macOS-scoped; the
  Linux-tagged source (`Pdeathsig` in `allocate_linux.go`) implies Linux differs.
  Re-run on Linux before generalizing.
- **`WaitReady` timeout flakiness ([#168]/[#682]/[#1593]) not reproduced.** This pack
  measured `WaitReady`'s *semantics*, not the intermittent-timeout reports; those need
  a heavier/racier fixture to attempt.
- **Concurrency at N≫4 and with real per-page work untested.** Wall-time gap is
  workload-specific; the memory delta of shared-vs-separate browsers is not measured
  (only process count).
- **Network interception / request capture not tested.** chromedp exposes CDP network
  events; out of scope for this pack.
- **Single machine, single Chrome build.** All numbers are macOS arm64 + Chrome for
  Testing 151.0.7922.10; cold-start and concurrency timings are host-specific.

## Novelty verification (pre-registration search)

Sources per finding: chromedp issue tracker, godoc/README/example_test.go, and top-~20
SERP. Verdict is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| pure-Go/CDP driver, context API, `defer cancel()`, wait actions exist | **DOCUMENTED** | [godoc](https://pkg.go.dev/github.com/chromedp/chromedp) + README; existence, not this pack's value |
| Live browser sees runtime-injected content; wait for injected nodes | **DOCUMENTED (mechanism)** | godoc `Example_dump`/`Example_documentDump` inject + `WaitVisible` |
| Naive `Navigate` and `WaitReady("body")` **miss** post-load `setTimeout` content; only a node-keyed wait/poll recovers it; `WaitVisible` elapsed tracks delay | **EXCLUSIVE (quantification)** | No SERP/issue source measures per-injection-timing recall by wait strategy or the delay-tracking; zero-hit |
| `WaitReady`=attached vs `WaitVisible`=visible diverge on `display:none` (measured) | **DOCUMENTED semantics / EXCLUSIVE demonstration** | Doc strings define ready vs visible; the measured `display:none` divergence + clean deadline is this pack's |
| `WaitVisible("#id")` default-query hang | **KNOWN-ISSUE, NOT reproduced** | [#440] reports it; here default/`ByID`/`ByQuery` all returned (v0.16.0) — reported as not reproduced |
| Cancel reaps Chrome; macOS exit-without-cancel **orphans** it | **KNOWN-ISSUE (platform-scoped non-exit) + EXCLUSIVE quantification** | Platform-scoped non-exit is known: [#774](https://github.com/chromedp/chromedp/issues/774) (FreeBSD non-exit), [#752](https://github.com/chromedp/chromedp/issues/752) (macOS hanging); mechanism is Linux-only `Pdeathsig` ([#562](https://github.com/chromedp/chromedp/issues/562)/[#1566](https://github.com/chromedp/chromedp/issues/1566)). This pack contributes the process-truth quantification (cancel ~13 ms reap vs 3/3 orphan on exit), not the discovery. |
| Cold-start ~102 ms p50; shared vs separate browser 1 vs N procs | **EXCLUSIVE (quantification)** | No SERP source publishes chromedp cold-start distribution or shared-vs-separate process/wall numbers |
| `WaitReady`/`WaitVisible` intermittent timeouts | **KNOWN-ISSUE** | [#168], [#682], [#1593] — not attempted here (semantics measured instead) |

[#168]: https://github.com/chromedp/chromedp/issues/168
[#440]: https://github.com/chromedp/chromedp/issues/440
[#682]: https://github.com/chromedp/chromedp/issues/682
[#1591]: https://github.com/chromedp/chromedp/issues/1591
[#1593]: https://github.com/chromedp/chromedp/issues/1593

**Consequence for the writer:** the information-gain items are all *measurements or
mechanisms behind documented behavior* — the per-timing recall matrix, the
WaitReady-vs-WaitVisible `display:none` divergence, the macOS orphan process-truth, and
the cold-start/concurrency numbers. Every claim carries a confidence label and points
to a JSON field; the one reported trap ([#440]) is honestly marked not reproduced.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* The only comparative with a
   direction is concurrency (shared vs separate), reported with **non-overlapping**
   wall-time ranges + the process-count gap. Recall-matrix elapsed differences (e.g.
   `none` 317 ms vs `WaitReady` 107 ms) are **not** framed as a speed win — the axis is
   recall, and `WaitVisible` being *slower* (912 ms) is correctly the cost of waiting.
   No "fastest/best" on tied numbers.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`recall-summary.json`, `waitsem-summary.json`, `lifecycle-summary.json`,
   `coldstart-summary.json`, `concurrency-summary.json`). The [#440] hang I could not
   reproduce is reported as **not reproduced**, not as a verified trap.
3. **Blind instrument (D2)** — *Pass.* Recall is computed against pre-registered
   ground-truth markers (`ground_truth.json`) and the instrument demonstrably registers
   **both** presence and absence (misses C under `none`, catches it under
   `WaitVisible`). The process counter registers both reap (1→0 on cancel) and
   non-reap (1 survives on orphan) — not blind. The runtime-injected markers are
   assembled from fragments, so a "found" requires the browser to have *executed* JS,
   not merely read bytes.
4. **Mis-attribution (D3)** — *Pass.* The class-C miss is attributed to `Navigate`'s
   load-event completion vs post-load injection — validated by the gradient (found at
   0 ms, missed at ≥100 ms). The macOS orphan is attributed to the absent parent-death
   signal + `exec.CommandContext` cancel-driven kill — validated by the cancel path
   reaping in 13 ms under the *identical* harness, ruling out a harness bug.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a
   verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over this
   file surfaces only the "Honest negative" / "reported honestly" labels flagging a
   negative result (rule-required transparency), not self-praise adjectives on the
   tool.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-23** in `metadata-snapshot.md`. Stars (13,202) /
  latest tag (v0.16.0) traceable to that GitHub fetch.
- **Versions:** tested chromedp v0.16.0 (== latest tag on snapshot day; newer than the
  v0.15.1 Release object); Go 1.26.5; Chrome for Testing 151.0.7922.10 (build 1232);
  read from `go list -m` / the run summaries / the Chrome `--version`.

## Raw Artifact Index

- Recall matrix + gradient: [recall-summary.json](artifacts/raw/recall-summary.json)
- Wait semantics: [waitsem-summary.json](artifacts/raw/waitsem-summary.json)
- Lifecycle (reap / orphan): [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json)
- Cold start: [coldstart-summary.json](artifacts/raw/coldstart-summary.json)
- Concurrency: [concurrency-summary.json](artifacts/raw/concurrency-summary.json)
- Ground truth: [ground_truth.json](artifacts/raw/ground_truth.json)
