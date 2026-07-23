# rod — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable gap exists; see "Information-gain verdict").

Broad keyword: **`rod`** (`github.com/go-rod/rod`).
Article boundary: rod is a **pure-Go library that drives a real Chrome/Chromium over
the Chrome DevTools Protocol (CDP)** — like chromedp, no Selenium/WebDriver server, no
Node, no external language runtime. Where chromedp exposes a lower-level context/action
DSL, rod is positioned as the **higher-ergonomics** CDP driver: single-selector methods
**auto-wait**, and the default launcher ships **leakless** (a guardian process) to force-
kill the browser when the Go process exits. This pack judges **the behavior of that
higher-level live-browser driver on controlled ground truth**: whether rod's auto-wait
recovers post-load runtime-injected content *out of the box*, how its wait primitives
behave at their edges, whether leakless actually prevents the macOS orphan that chromedp
leaves, cold-start cost, and the concurrency model. It is **not** a scoring of Chrome
itself, nor a structured-data/field-extractor comparison (rod hands you the DOM/elements;
what you pull out is your code).

**Direct comparison object: chromedp** (`tools/chromedp/`, already published). rod and
chromedp are the two Go CDP drivers; every rod hypothesis below is designed on the
**identical fixture, harness shape, and process-truth method** used for chromedp, so the
numbers are apples-to-apples on the same host + same Chrome build. Cross-series axis: the
*runtime-injected* content class here is the **same class katana's static crawl misses,
playwright-mcp's live a11y snapshot catches, and chromedp catches only with a node-keyed
`WaitVisible`** — rod is the fourth data point on that same fixture idea, and the axis on
which rod's auto-wait ergonomics are supposed to pay off.

## SERP scan (first ~20 results, official godoc/docs, issue tracker)

### What the results repeat (consensus, mostly unmeasured)

- **"More ergonomic than chromedp; auto-wait; chainable."** The dominant framing
  (ZenRows, Latenode, DEV.co, LambdaTest, rod's own `why-rod.md`): rod uses "as few
  interfaces as possible," is chainable, and its **single-selector methods wait for the
  element to appear**, so it "simplifies scraping dynamic JavaScript-heavy sites." The
  rod-vs-chromedp trope: "chromedp forces a verbose DSL of `Tasks`; rod's `page.Element`
  just works." Repeated as prose, never measured against ground truth.
- **Auto-wait mechanism (documented).** rod's `Page.Element`/`Element*` retry on a
  `DefaultSleeper` backoff (`A(0)=100ms`, `A(n)=A(n-1)*rand[1.9,2.1)`, capped <1s) until
  the element is found or the page context/timeout expires. `Race()` polls multiple
  selectors; `Element.WaitVisible()` / `Page.WaitStable()` are separate primitives.
- **Architecture: remote-object-id, not DOM-node-id.** `why-rod.md` argues rod (like
  puppeteer) keys on the CDP *remote object id*, which it says lets rod attach high-level
  runtime-coupled helpers that chromedp's DOM-node-id design cannot — and claims chromedp
  "leaves the zombie browser process on Windows and Mac" on a crash.
- **leakless by default.** `launcher.New()` enables `Leakless` by default: it **force-
  kills the browser after the Go process exits**. Mechanism (leakless README,
  `github.com/ysmood/leakless`): a **separate per-platform guardian binary** (ships
  darwin/arm64) is spawned and bridged to the parent over a **TCP connection**; when that
  connection closes (parent exits *or crashes*), the guardian kills the browser. PID is
  deliberately *not* used ("a new process may reuse the PID"). The guardian binary is
  **downloaded/dropped on first use** (issue [#266] flags the binary drop; [#739]
  Windows AV false-positive; [#457] Windows launch failure).

### What is NOT measured anywhere (the gap)

1. **The auto-wait ergonomics claim is asserted, never bounded on ground truth.**
   Everyone says rod's `page.Element` "just works" on dynamic content. Nobody separates
   *when* content is injected and shows the exact idiom boundary: does rod's `Element`
   auto-wait recover a node injected **after the load event** (`setTimeout`) with **no
   explicit wait**, while a naive `page.MustHTML()` snapshot (the other idiom) **misses**
   the same node exactly as chromedp's naive read does? No source plots
   per-injection-timing recall across rod's idioms `{navigate+HTML, WaitLoad+HTML,
   Element(node), poll}` — nor confirms auto-wait's elapsed *tracks the injection delay*
   (the proof it truly waited rather than read early).
2. **rod's wait primitives on a controlled node are folklore, not a mechanism.** rod has
   `Element` (waits for **attached** in DOM) vs `Element.WaitVisible` (waits for
   **visible**). Nobody shows the semantic split on an **attached-but-`display:none`**
   node: does `Element` return while `WaitVisible` blocks to the page deadline with a
   clean timeout error? And rod's selector model (`Element`=CSS, `ElementX`=XPath,
   `ElementR`=regex) is claimed to avoid chromedp's `ByID`-vs-default `#440` footgun —
   untested as a contrast.
3. **The leakless "no orphan on crash" claim is never proven with process-truth.**
   `why-rod.md` says chromedp orphans on Mac and rod (leakless) does not. chromedp's pack
   *measured* the macOS orphan (exit-without-cancel orphans 3/3, process-truth via
   `pgrep`). Nobody runs the mirror experiment on rod: does a Go process that **exits
   without cleanup** (and one that is **SIGKILLed**) leave the browser orphaned with
   leakless **on** vs **off**, counted by `pgrep`? Only the on/off toggle attributes the
   outcome to leakless rather than to "rod is magic." And the honest boundary ([#865]:
   leakless fires on *process exit*, not per-browser-close inside a long-running process)
   is never stated alongside the win.
4. **Cold-start cost and the concurrency model are unpriced — and the leakless tax is
   invisible.** No source reports rod's launcher→connect→page→first-eval **cold-start
   distribution**, whether the leakless guardian adds measurable startup cost vs chromedp
   (102 ms p50 on this host), the one-time guardian **download**, or the wall-time /
   browser-process-count difference between **N pages sharing one browser** vs **N
   separate browsers** — the exact choice rod's examples show but never benchmark.

### Source evidence

- Official: [rod godoc](https://pkg.go.dev/github.com/go-rod/rod),
  [launcher godoc](https://pkg.go.dev/github.com/go-rod/rod/lib/launcher),
  [why-rod.md](https://github.com/go-rod/go-rod.github.io/blob/main/why-rod.md),
  [selectors README](https://github.com/go-rod/go-rod.github.io/blob/main/selectors/README.md),
  [examples_test.go](https://github.com/go-rod/rod/blob/main/examples_test.go),
  [leakless](https://github.com/ysmood/leakless).
- Upstream issues to cite at execution: leakless binary drop
  [#266](https://github.com/go-rod/rod/issues/266); leakless AV
  [#739](https://github.com/go-rod/rod/issues/739); leakless Windows launch
  [#457](https://github.com/go-rod/rod/issues/457); leakless does **not** cover
  long-running-process browser churn / zombies
  [#865](https://github.com/go-rod/rod/issues/865); disable-leakless request
  [#210](https://github.com/go-rod/rod/issues/210); wait-stable vs request-idle
  [#1224](https://github.com/go-rod/rod/issues/1224).
- Representative SERP: [ZenRows Go puppeteer/rod](https://www.zenrows.com/blog/puppeteer-golang),
  [Latenode Go headless](https://latenode.com/blog/web-automation-scraping/headless-browser-overview/golang-headless-browser-best-tools-for-automation),
  [DEV.co rod](https://dev.co/testing/open-source/rod).

## Testable information-gain hypotheses

- **H1 (parity, adversarial — the auto-wait boundary):** rod's `page.Element(selector)`
  auto-waits, so it recovers a class-C node injected after the load event **with no
  explicit wait call** — the ergonomic payoff chromedp lacks (chromedp's `Navigate`+read
  and `WaitReady("body")` miss the same node; only an explicit `WaitVisible(node)`/poll
  recovers it). **But** the auto-wait is a property of *querying the element*, not of
  reading the page: a naive rod `page.MustHTML()` snapshot right after navigate should
  **miss** class C exactly like chromedp's naive read. Measure per-injection-timing recall
  across rod idioms `{navigate+HTML, WaitLoad+HTML, Element(node), poll}`; confirm
  `Element`'s elapsed tracks the injection delay. Prediction: rod's *idiomatic* path
  (query the element) beats chromedp's *idiomatic* path (navigate+read) on out-of-the-box
  recall of post-load content — a real ergonomics win — while the naive read footgun is
  identical on both.
- **H2 (leakless orphan, adversarial — the beautiful reverse contrast, process-truth):**
  A Go process that **exits without cleanup** leaves the browser **reaped** with leakless
  **on** (the guardian's TCP closes on parent exit → kills browser), and **orphaned** with
  leakless **off** — and a **SIGKILL** of the parent is *also* reaped with leakless on
  (why-rod's "no zombie on crash" claim). Count browser processes via `pgrep` on a unique
  `--user-data-dir`, each path 3×. Prediction: the **opposite** of chromedp on macOS
  (chromedp orphans 3/3 on exit-without-cancel); the on/off toggle attributes the
  difference to leakless, not to hand-waving. Honest boundary to state: leakless covers
  *process exit*, not per-browser churn in a long-running process ([#865]).
- **H3 (wait-primitive semantics):** rod `Element` returns for an **attached-but-hidden**
  (`display:none`) node (attachment is enough) whereas `Element.WaitVisible()` blocks to
  the page deadline with a clean timeout; and rod's `Element`(CSS)/`ElementX`(XPath)
  selector split avoids chromedp's `#440` default-query trap. Measure return/timeout +
  elapsed for each on a controlled node.
- **H4 (cold-start cost + leakless tax):** rod's launcher→connect→page→first-eval
  cold-start is a distribution, not a point; report p50 + range over ≥5 isolated runs,
  compare to chromedp's 102 ms p50 on the identical host/Chrome, record whether the
  leakless guardian **download** fires (one-time) and pre-warm it so it doesn't pollute the
  timing. Confirm the runtime **Chrome-binary dependency** (rod's `.Bin(path)` disables
  auto-download; the "pure Go" claim is about the module, not the runtime).
- **H5 (concurrency model cost):** N=4 pages **sharing one browser** vs N=4 **separate
  browsers** on the same fixture — wall-time distribution and browser-process count.
  Prediction: like chromedp, shared pages cost one browser process; separate browsers cost
  N.

## Test matrix (tied to hypotheses)

| # | Test | Fixture route / mode | Measures | H |
|---|---|---|---|---|
| 1 | recall: navigate + HTML | `/classes`, `Navigate`+`HTML` only | classes A/B/C vs ground truth | H1 |
| 2 | recall: WaitLoad + HTML | `/classes` | classes A/B/C | H1 |
| 3 | recall: Element(C-node) auto-wait | `/classes` | classes A/B/C | H1 |
| 4 | recall: poll until marker | `/classes` | classes A/B/C | H1 |
| 5 | injection-timing gradient | `/classes?delay=N` | recall vs delay; Element elapsed vs delay | H1 |
| 6 | Element on display:none | `/waitsem` attached-hidden node | returns? elapsed | H3 |
| 7 | WaitVisible on display:none | `/waitsem` same node | returns / deadline? elapsed | H3 |
| 8 | CSS Element vs XPath ElementX | `/waitsem` id target | both return; no #440-style trap | H3 |
| 9 | exit-no-cleanup, leakless ON | unique user-data-dir | pgrep orphan? (predict reaped) | H2 |
| 10 | exit-no-cleanup, leakless OFF | unique user-data-dir | pgrep orphan? (predict orphan) | H2 |
| 11 | SIGKILL parent, leakless ON | unique user-data-dir | pgrep orphan? (predict reaped) | H2 |
| 12 | graceful Close(), leakless ON | unique user-data-dir | reaped + reap ms | H2 |
| 13 | deadline honored | never-appearing selector + page timeout | clean timeout error, no hang | H3 |
| 14 | cold-start cost | full cold start, ≥5 isolated runs | p50 + range vs chromedp 102ms | H4 |
| 15 | runtime dependency | run with Chrome present (`.Bin`) | confirm external Chrome required | H4 |
| 16 | leakless download | first-ever run | one-time guardian download recorded | H4 |
| 17 | shared browser, 4 pages | 4 pages, one browser | wall-time + chrome PIDs | H5 |
| 18 | 4 separate browsers | 4 launchers | wall-time + chrome PIDs | H5 |
| 19 | server-side fetch-truth | all runs | which paths Chrome actually fetched | all |
| 20 | 500 / dead-link robustness | `/failure/500`, `/broken` | error surfaced, no crash | robustness |
| 21 | class A static recall | `/classes` static `<a>` | present in every strategy | H1 |
| 22 | class B sync-injected recall | `/classes` inline-script node | present once DOM built | H1 |
| 23 | determinism | repeat recall runs | same found-set across runs | H1 |

Fixture (local, `127.0.0.1`, rod's Chrome hits loopback): **reuse the chromedp /
playwright-mcp / katana same-fixture, server-side-hit-counter philosophy verbatim** — the
identical three content classes so rod's numbers are directly comparable to chromedp's on
the same page. Class **A** static `<a>` (literal in served HTML); **B** injected
**synchronously** by an inline `<script>` at parse; **C** injected **after load** via
`setTimeout`, marker+href **assembled from fragments** so no contiguous literal exists in
any served byte (only executing + waiting reveals it). A **server-side hit counter**
records which paths Chrome actually fetched. Recall is computed against a pre-registered
ground-truth marker set — never guessed. Process-truth (orphan/reap) uses `pgrep` on a
unique `--user-data-dir`, filtered to the actual **browser** binary (first token =
`chrome-headless-shell`, no `--type=`) so the leakless guardian process is not miscounted.

## Harness design (Go probe + Python orchestrator)

A small **Go module** (`tests/harness/`, `go.mod` pinning `rod`) compiles to one binary
`rod_probe` with sub-commands (`recall`, `waitsem`, `lifecycle`, `coldstart`,
`concurrency`). Python `run_*.py` start the fixture, invoke the binary with the base URL +
a unique user-data-dir, parse its stdout JSON, and compute recall vs `ground_truth.json`.
**The probe returns raw extracted content / measured booleans + timings; Python computes
recall** (anti-hardcoding: no verdict string is baked into Go). Artifacts are `_redact`-ed
(`$HOME`→`~`) exactly like chromedp/katana. We use `go build` + run the binary (not `go
test`). rod is pointed at the **same Chrome-for-Testing headless shell (build 1232)**
chromedp used, via `launcher.New().Bin(path)` (disables auto-download) — parity, not rod's
default Chromium 1321438.

## Information-gain verdict: PROCEED

Not parked. The consensus is dense ("more ergonomic than chromedp," "auto-wait just
works," "leakless prevents zombies") but **entirely qualitative on the four questions that
decide whether the ergonomics claim survives contact with ground truth**: (1) does rod's
auto-wait `Element` actually recover post-load-injected content out of the box, and is the
naive-read footgun really identical to chromedp; (2) the real semantic gap between
`Element` and `WaitVisible` on a controlled node; (3) does leakless actually prevent the
macOS orphan chromedp leaves — proven with process-truth and an on/off toggle, not a doc
citation; (4) cold-start (incl. the leakless tax) and concurrency cost. Each is measurable
on a local fixture with no credentials, on the **same host + Chrome build** as the
published chromedp pack, yielding a genuine head-to-head no SERP source provides.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on the **local fixture** (`127.0.0.1`) + a local Chrome-for-Testing headless
  shell (build 1232, reused). No third-party/production host, no anti-bot, no auth bypass,
  no rate abuse. rod is a general browser driver, not positioned as a recon tool; framing
  is "live-browser driver behavior on controlled ground truth."
- No credentials anywhere. Artifacts redact `$HOME`→`~`; the Go probe redacts the home
  prefix before printing JSON too.
- Record the exact Chrome path + version, rod + leakless version/commit, Go version, and
  the leakless guardian download (path + one-time) in metadata. **Do not** copy the Chrome
  binary or the leakless guardian into the pack; gitignore the rod cache.
- Timing (cold-start, concurrency) reported as distributions; overlap ⇒ tie. Claims scoped
  to this fixture, rod version, Chrome build, and macOS arm64.
- **Novelty honesty:** pure-Go/CDP, auto-wait existence, `Element` vs `WaitVisible`,
  remote-object-id architecture, leakless-by-default and its exit-kill are **DOCUMENTED**;
  leakless binary-drop / long-running-churn limits are **KNOWN-ISSUE** ([#266]/[#865]).
  Only the *quantifications* (per-timing recall matrix vs chromedp, the auto-wait
  delay-tracking, the leakless-on/off orphan process-truth vs chromedp's orphan, cold-start
  incl. leakless tax, concurrency numbers) are candidates for EXCLUSIVE. **Do not** claim
  leakless "prevents orphans" from the doc alone — only from the pgrep on/off measurement.

[#210]: https://github.com/go-rod/rod/issues/210
[#266]: https://github.com/go-rod/rod/issues/266
[#457]: https://github.com/go-rod/rod/issues/457
[#739]: https://github.com/go-rod/rod/issues/739
[#865]: https://github.com/go-rod/rod/issues/865
[#1224]: https://github.com/go-rod/rod/issues/1224
