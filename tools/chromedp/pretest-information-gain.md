# chromedp — pre-test information-gain brief

Date: 2026-07-23. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable gap exists; see "Information-gain verdict").

Broad keyword: **`chromedp`** (`github.com/chromedp/chromedp`).
Article boundary: chromedp is a **pure-Go library that drives a real Chrome/Chromium
over the Chrome DevTools Protocol (CDP)** — no Selenium/WebDriver server, no Node,
no external language runtime. This pack judges **the behavior of that live-browser
driver on controlled ground truth**: whether/when it surfaces runtime-injected DOM
content, how its wait actions behave at their edges, how its context lifecycle
reaps the spawned Chrome process, cold-start cost, and the concurrency model. It is
**not** a scoring of Chrome itself, nor a structured-data/field extractor
comparison (chromedp gives you the DOM; what you pull out is your code). Cross-series
axis: the *runtime-injected* content class here is the **same class katana's static
crawl misses and playwright-mcp's live a11y snapshot catches** — chromedp is the
third data point on that same fixture idea.

## SERP scan (first ~20 results, official README/godoc/examples, issue tracker)

### What the results repeat (consensus, mostly unmeasured)

- **Pure Go, no external deps, single binary.** Repeated everywhere: "chromedp is a
  faster, simpler way to drive browsers in Go without external dependencies (e.g.
  Selenium, PhantomJS)." The nuance that it still needs a **Chrome/Chromium binary
  present at runtime** is stated in the godoc but glossed in most blog intros.
- **Context-based API.** `NewExecAllocator(ctx, opts...)` → `NewContext(ctx)` →
  `Run(ctx, actions...)`; `defer cancel()` twice. Timeouts/cancellation ride the
  standard `context.Context`. Tabs are child contexts of a shared browser
  (`ExampleNewContext_reuseBrowser`, `ExampleNewContext_manyTabs`).
- **Wait actions.** `WaitVisible` / `WaitReady` / `WaitNotPresent` etc.; the godoc
  runtime-injection examples (`Example_dump`, `Example_documentDump`,
  `Example_retrieveHTML`) inject a node with `Evaluate` then `WaitVisible` it. The
  prose consensus is "`WaitVisible` is more reliable; `WaitReady` sometimes times
  out."
- **Resource management.** "`defer cancel()` or you leak Chrome." godoc: on Linux
  chromedp force-kills started Chrome child processes; for long-running Chrome use
  `RemoteAllocator`.

### What is NOT measured anywhere (the gap)

1. **"A headless browser sees the dynamic page" is asserted, never bounded by wait
   strategy.** Everyone says a live browser (unlike a static crawler) sees
   JS-rendered content. Nobody separates *when* the content is injected
   (synchronously during parse vs after the load event via `setTimeout`) and shows
   that a **naive `Navigate` + read MISSES post-load-injected content** because
   `Navigate` returns on the load event, before a deferred injection — i.e. the
   live browser only sees it *if you wait correctly*. No source plots per-injection-
   timing recall across `{no wait, WaitReady, WaitVisible, poll}`.
2. **`WaitVisible` vs `WaitReady` is folklore, not a mechanism on ground truth.**
   "WaitReady flaky, WaitVisible better" is repeated (issues [#168], [#682],
   [#1593]) but nobody shows the *semantic* difference on a controlled node: does
   `WaitReady` return for an **attached-but-not-visible** (`display:none`) node
   while `WaitVisible` blocks to the deadline? And the selector-semantics trap
   ([#440]: `WaitVisible("#foot")` hangs, `WaitVisible("foot", ByID)` works) is
   reported once, never reproduced as a measured contrast.
3. **Context cancel → Chrome reap is described, not proven with process-truth.**
   The `defer cancel()` mantra is universal; nobody counts OS processes to show that
   cancelling actually reaps the spawned `chrome-headless-shell` (and how fast), or
   what happens on **macOS** specifically when the Go process exits *without*
   cancelling (chromedp's cross-platform `allocate.go` uses `exec.CommandContext`;
   the force-kill note is Linux-scoped — the macOS orphan behavior is untested in
   public).
4. **Cold-start cost and the concurrency model are unpriced.** No source reports
   chromedp's allocator→context→navigate→first-eval **cold-start distribution**, or
   the wall-time / Chrome-process-count difference between **N contexts sharing one
   browser** vs **N separate browsers** — the exact choice `ExampleNewContext_*`
   documents but never benchmarks.

### Source evidence

- Official: [chromedp godoc](https://pkg.go.dev/github.com/chromedp/chromedp),
  [README](https://github.com/chromedp/chromedp),
  [example_test.go](https://github.com/chromedp/chromedp/blob/master/example_test.go),
  [allocate.go](https://github.com/chromedp/chromedp/blob/master/allocate.go).
- Upstream issues to cite at execution: wait flakiness
  [#168](https://github.com/chromedp/chromedp/issues/168),
  [#682](https://github.com/chromedp/chromedp/issues/682),
  [#1593](https://github.com/chromedp/chromedp/issues/1593); selector semantics
  [#440](https://github.com/chromedp/chromedp/issues/440); lifecycle/leaks
  [#552](https://github.com/chromedp/chromedp/issues/552),
  [#1007](https://github.com/chromedp/chromedp/issues/1007),
  [#1441](https://github.com/chromedp/chromedp/issues/1441); Go-1.25 `go test`
  incompat [#1591](https://github.com/chromedp/chromedp/issues/1591).
- Representative SERP: [ZenRows chromedp tutorial](https://www.zenrows.com/blog/chromedp),
  [ScrapingBee getting-started](https://www.scrapingbee.com/blog/getting-started-with-chromedp/),
  [Starlog "Driving Chrome with Pure Go"](https://starlog.is/articles/ai-agents/chromedp-chromedp/).

## Testable information-gain hypotheses

- **H1 (adversarial, the real boundary — parity axis):** A chromedp live browser
  surfaces runtime-injected DOM content that a static crawler misses — **but only
  with the correct wait action.** A naive `Navigate` + read recovers content present
  at the load event (static HTML + synchronously-injected) yet **misses content
  injected after load** (`setTimeout`), because `Navigate` completes on the load
  event. Measure per-injection-timing recall across `{no wait, WaitReady(body),
  WaitVisible(target), poll}`. Prediction: "just use a headless browser" is
  over-claimed; you need the browser **and** a wait keyed to the injected node.
- **H2 (wait-action semantics):** `WaitReady` returns for an **attached-but-not-
  visible** node (`display:none`) whereas `WaitVisible` blocks until the context
  deadline; and the default selector query differs from `ByID` on the same target
  (the [#440] trap). Measure return/timeout + elapsed for each on a controlled node.
- **H3 (context lifecycle / resource cleanup, process-truth):** Cancelling the
  chromedp context (and allocator) **reaps** the spawned `chrome-headless-shell`
  process (count via `pgrep` on a unique `--user-data-dir`), and reports how fast;
  and on macOS a Go process that **exits without cancelling** leaves the behavior we
  measure (orphan vs reaped), since the force-kill guarantee is Linux-scoped.
- **H4 (cold-start cost):** chromedp's allocator→context→navigate→first-eval
  cold-start is a distribution, not a point; report p50 + range over ≥3 isolated
  runs, and confirm the runtime **Chrome-binary dependency** (the "no dependencies"
  claim is about the Go module, not the runtime).
- **H5 (concurrency model cost):** N=4 contexts **sharing one browser** vs N=4
  **separate browsers** on the same fixture — wall-time distribution and
  Chrome-process count. Prediction: shared-browser tabs cost far fewer OS processes
  and less wall time for the same work.

## Test matrix (tied to hypotheses)

| # | Test | Fixture route / mode | Measures | H |
|---|---|---|---|---|
| 1 | recall: no wait | `/classes`, `Navigate`+`OuterHTML` only | classes A/B/C found vs ground truth | H1 |
| 2 | recall: WaitReady(body) | `/classes` | classes A/B/C found | H1 |
| 3 | recall: WaitVisible(C-target) | `/classes` | classes A/B/C found | H1 |
| 4 | recall: poll until marker | `/classes` | classes A/B/C found | H1 |
| 5 | injection-timing gradient | C injected at `setTimeout` DELAY_MS | recall vs delay | H1 |
| 6 | WaitReady on display:none | `/waitsem` attached-hidden node | returns? elapsed | H2 |
| 7 | WaitVisible on display:none | `/waitsem` same node | returns / deadline? elapsed | H2 |
| 8 | default-query vs ByID | `/waitsem` id target | which returns vs times out | H2 |
| 9 | cancel reaps Chrome | unique user-data-dir | pgrep count before/after cancel; reap ms | H3 |
| 10 | deadline honored | never-appearing selector + ctx timeout | clean deadline error, no hang | H3 |
| 11 | exit-without-cancel (macOS) | Go exits, no cancel | orphan vs reaped (measured) | H3 |
| 12 | cold-start cost | full cold start, ≥3 isolated runs | p50 + range | H4 |
| 13 | runtime dependency | run with Chrome present | confirm external Chrome required | H4 |
| 14 | shared browser, 4 tabs | 4 contexts, one allocator | wall-time + chrome PIDs | H5 |
| 15 | 4 separate browsers | 4 allocators | wall-time + chrome PIDs | H5 |
| 16 | server-side fetch-truth | all runs | which paths Chrome actually fetched | all |
| 17 | 500 / dead-link robustness | `/failure/500`, `/broken` | Navigate error surfaced, no crash | robustness |
| 18 | class A static recall | `/classes` static `<a>` | present in every strategy | H1 |
| 19 | class B sync-injected recall | `/classes` inline-script node | present once DOM built | H1 |
| 20 | determinism | repeat recall runs | same found-set across runs | H1 |

Fixture (local, `127.0.0.1`, chromedp's Chrome hits loopback): **reuse the katana /
playwright-mcp same-fixture, server-side-hit-counter philosophy.** Three content
classes separate *when* content exists: **A** static `<a>` in served HTML; **B**
injected **synchronously** by an inline `<script>` at parse (present by the load
event); **C** injected **after load** via `setTimeout`, with its href+marker
**assembled from fragments** so no contiguous literal exists in any served byte
(only executing + waiting reveals it). A **server-side hit counter** records which
paths Chrome actually fetched (fetch-truth independent of chromedp's own return).
Recall is computed against a pre-registered ground-truth marker set — never guessed.
Process-truth (Chrome reap) uses `pgrep` on a unique `--user-data-dir` — the
process analog of the server-side hit counter.

## Harness design (Go probe + Python orchestrator)

A small **Go module** (`tests/harness/`, `go.mod` pinning `chromedp`) compiles to one
binary `chromedp_probe` with sub-commands (`recall`, `waitsem`, `lifecycle`,
`coldstart`, `concurrency`). Python `run_*.py` start the fixture, invoke the binary
with the base URL + a unique user-data-dir, parse its stdout JSON, and compute recall
vs `ground_truth.json`. **The probe returns raw extracted content / measured
booleans + timings; Python computes recall** (anti-hardcoding: no verdict string is
baked into Go). Artifacts are `_redact`-ed (`$HOME`→`~`) exactly like katana. We use
`go build` + run the binary (**not `go test`**) to sidestep the Go-1.25+/`go test`
allocator-cancel incompat ([#1591]); Go here is 1.26.5.

## Information-gain verdict: PROCEED

Not parked. The consensus is dense (pure-Go, context API, `WaitVisible>WaitReady`,
`defer cancel()`) but **entirely qualitative on the four questions that decide
whether the design behaves as sold**: (1) does the live browser actually see
post-load-injected content, and under which wait; (2) the real semantic gap between
`WaitReady` and `WaitVisible` on a controlled node; (3) does cancel reap Chrome, on
macOS, with process-truth; (4) cold-start and concurrency cost. Each is measurable on
a local fixture with no credentials and yields numbers no current SERP source
provides. Cross-series bonus: the class-C runtime-injected node is the *same* content
class katana static misses and playwright-mcp catches — a third, same-fixture data
point.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on the **local fixture** (`127.0.0.1`) + a local Chrome-for-Testing
  headless shell. No third-party/production host, no anti-bot, no auth bypass, no
  rate abuse. chromedp is a general browser driver, not positioned as a recon tool;
  framing is "live-browser driver behavior on controlled ground truth."
- No credentials anywhere. Artifacts redact `$HOME`→`~` (katana `_redact` habit); the
  Go probe redacts the home prefix before printing JSON too.
- Record the exact Chrome path + version and chromedp version/commit in metadata.
- Timing (cold-start, concurrency) reported as distributions; overlap ⇒ tie. Claims
  scoped to this fixture, chromedp version, Chrome build, and macOS arm64.
- Novelty honesty: pure-Go / context-API / wait-action existence / `defer cancel()`
  are **DOCUMENTED**; wait flakiness and the selector trap are **KNOWN-ISSUE**
  ([#168]/[#682]/[#1593]/[#440]). Only the *quantifications* (per-timing recall
  matrix, WaitReady-vs-WaitVisible semantics table, macOS reap/orphan process-truth,
  cold-start + concurrency numbers) are candidates for EXCLUSIVE.
