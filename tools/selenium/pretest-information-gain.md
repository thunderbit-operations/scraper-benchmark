# selenium — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design + execution recon.
Decision: **PROCEED** (a measurable gap exists; Selenium Manager provisioning verified
live, driver resolvable, network open — see "Information-gain verdict").

Broad keyword: **`selenium`** (`SeleniumHQ/selenium`, Python bindings).
Article boundary: Selenium WebDriver drives a real browser through **chromedriver over the
**W3C WebDriver protocol** — NOT the Chrome DevTools Protocol. Its chain is three processes:
**python → chromedriver → chrome (+ chrome helpers)**, where the Go CDP drivers
(chromedp/rod) are two (go → chrome). Since Selenium 4.6 it ships **Selenium Manager**, a
Rust binary that, on a driverless `webdriver.Chrome()`, detects the browser version and
**auto-downloads a matching chromedriver**, caching it under `~/.cache/selenium`. This pack
judges **the behavior of that modern-WebDriver setup + rendering path on controlled ground
truth**: Selenium Manager's real provisioning behavior, whether Selenium's wait idioms
recover post-load runtime-injected content, its presence-vs-visibility semantics, the
two-process (driver+browser) lifecycle under `quit()` vs no-quit vs crash, cold-start
cost, and the concurrency model. It is **not** a scoring of Chrome itself, nor a
field-extractor comparison (Selenium hands you the DOM/elements).

**Direct comparison object: chromedp + rod** (`tools/chromedp/`, `tools/rod/`, both
published). Those are the two Go CDP drivers on the identical fixture, harness shape, and
process-truth method — so Selenium's numbers are apples-to-apples on the same host + same
Chrome build (Chrome for Testing 151.0.7922.10, build 1232). Cross-series axis: the
runtime-injected content class here is the **same class katana's static crawl misses,
playwright-mcp's live a11y snapshot catches, chromedp catches only with a node-keyed
`WaitVisible`, and rod catches with its auto-waiting `Element`** — Selenium is the fifth
same-fixture data point, and the axis on which its explicit-wait model lands.

**Focus constraint (from the queue):** measure *modern WebDriver setup and rendering
tradeoffs **without** a generic Playwright comparison*. So this pack does **not** rehearse
the SERP trope "Selenium is slower/heavier than Playwright." Instead it quantifies the
*new* material: Selenium Manager auto-supply, the W3C protocol, and the
chromedriver→Chrome two-process driver chain.

## SERP scan (first ~20 results, official docs, issue tracker) + live recon

### What the results repeat (consensus, mostly unmeasured)

- **"Selenium 4.6+ no longer needs manual driver management — Selenium Manager does it."**
  The dominant framing (Selenium blog, selenium.dev docs, ZenRows, BrowserStack): a
  driverless `webdriver.Chrome()` "just works" because Selenium Manager finds/downloads the
  right driver. Described as prose; the *actual resolution behavior* (which patch it picks,
  first-run cost, cache reuse, stale-driver handling) is never measured.
- **W3C WebDriver protocol.** Selenium 4 speaks W3C-standard WebDriver to chromedriver;
  chromedriver translates to CDP internally. Repeated as an architecture note, never tied
  to a rendering/recall consequence.
- **"Call `driver.quit()` or you leak the browser."** Docs and countless SO answers warn
  that `quit()` (not `close()`) ends the session and stops chromedriver; forgetting it
  "leaves chromedriver/chrome running." Stated as folklore; nobody counts the orphaned
  processes or separates the driver tier from the browser tier.
- **Explicit vs implicit waits.** `WebDriverWait` + `expected_conditions` (explicit) vs
  `implicitly_wait` (implicit); docs warn against mixing them. Which one actually recovers
  post-load-injected content, and the latency it costs, is not measured on ground truth.

### What is NOT measured anywhere (the gap)

1. **Selenium Manager's real provisioning behavior is asserted, never quantified.** Nobody
   shows, for a known browser build, *which* chromedriver version it resolves (exact patch),
   the **first-resolution (network download) cost vs the warm cache-hit cost**, or whether a
   **stale mismatched driver** already in the cache is reused or replaced by a matching one.
2. **The W3C wait-idiom × injection-timing recall boundary is folklore.** Everyone says
   "use explicit waits for dynamic content." Nobody plots per-injection-timing recall across
   Selenium's idioms `{page_source, implicit_wait, WebDriverWait, poll}` on a controlled
   node injected after the load event — nor confirms the explicit-wait elapsed *tracks* the
   injection delay (and exposes `WebDriverWait`'s default **500 ms poll quantization**).
3. **The two-process lifecycle is never proven with process-truth.** chromedp's pack
   *measured* a macOS browser orphan; rod's *measured* leakless reaping. Nobody runs the
   mirror on Selenium: on a no-quit exit and on a SIGKILL crash, are **BOTH** the
   chromedriver process **and** the browser orphaned (pgrep + pid liveness), vs `quit()`
   reaping both? The extra **driver process tier** is the Selenium-specific novelty.
4. **Cold-start cost is mis-attributed to "Selenium is slow."** No source decomposes
   Selenium's cold start into (a) the chromedriver/W3C-handshake overhead vs (b) the browser
   binary/headless-mode choice, nor prices the **Selenium Manager per-call tax**. The naive
   SERP number conflates the protocol with the binary.
5. **The concurrency model is unpriced.** A single WebDriver session is not thread-safe and
   **serializes** commands; concurrency requires N sessions = N chromedrivers + N browsers.
   Nobody benchmarks the shared-serial vs separate-concurrent wall time and the
   **two-tier** (driver + browser) process cost.

### Live execution recon (done before committing to build)

- **Network open.** Chrome-for-Testing metadata + the chromedriver 151 zip both return
  HTTP 200; GitHub 200. Selenium Manager can provision (not `BLOCKED_DRIVER_PROVISIONING`).
- **Selenium Manager resolves.** `selenium-manager 0.4.46`, given the full Chrome for
  Testing 151.0.7922.10 binary, resolves **chromedriver 151.0.7922.47** into an isolated
  cache — cold ~4 s (network), warm ~25 ms. It does **not** reuse a pre-seeded stale
  chromedriver 145. (Verified live; this is the H0 headline.)
- **Chrome binary choice.** chrome-headless-shell (build 1232, the binary chromedp/rod
  drove) works with chromedriver **without** a client `--user-data-dir`, but a client-
  supplied `--user-data-dir` on headless-shell trips `unable to discover open pages`. Full
  **Chrome for Testing 151.0.7922.10 (build 1232)** driven with `--headless=new` accepts the
  client profile dir, which the pgrep-by-unique-udd process-truth method (parity with
  chromedp/rod) needs. Same Chrome *version/build*; recall (DOM/JS timing) is identical
  across the two headless variants, so cross-tool recall stays valid. Cold-start is measured
  on **both** binaries to isolate the binary effect.

## Testable information-gain hypotheses

- **H0 (Selenium Manager provisioning — the setup headline):** for browser 151.0.7922.10,
  Selenium Manager resolves a chromedriver matching the browser's **major.minor.build**
  (151.0.7922) and takes the **latest patch** (not the browser's own .10); the first
  resolution pays a one-time network download (~seconds) while a warm cache hit is ~ms; a
  **stale mismatched driver** (145.x) in the cache is **not** reused — a matching version is
  fetched. Measure with isolated cache dirs (never touch `~/.cache/selenium`).
- **H1 (wait-idiom × injection-timing recall, parity):** Selenium's default `driver.get()`
  blocks to the load event, so `page_source` is an at-load snapshot that **misses** class C
  (injected after load) — the same footgun as chromedp's naive read / rod's `WaitLoad`+HTML.
  An explicit `WebDriverWait(presence_of C)` recovers it (parity: chromedp's explicit
  `WaitVisible`), and its elapsed tracks the delay with a **500 ms poll quantization**.
  Measure recall across `{page_source, implicit_wait, WebDriverWait, poll}` and the gradient.
- **H2 (two-process lifecycle, adversarial — process-truth):** `driver.quit()` reaps
  **both** chromedriver and chrome; a python exit **without** quit and a **SIGKILL** crash
  each orphan **both** the chromedriver process and the browser (no leakless-style guardian,
  no parent-death signal). Count via `pgrep` on a unique `--user-data-dir` + pid liveness,
  each path 3×. Prediction: **one process worse** than chromedp's browser-only macOS orphan,
  and the opposite of rod's leakless reap.
- **H3 (wait-primitive semantics):** `find_element` (presence/attached) returns for an
  attached-but-`display:none` node while an explicit `visibility_of_element_located` blocks
  to the deadline with a clean `TimeoutException`; `By.CSS_SELECTOR` and `By.XPATH` both
  resolve the visible node; a never-appearing selector honors the deadline (no hang).
- **H4 (cold-start decomposition + Selenium Manager tax):** cold start is a distribution;
  report p50 + range for (i) full Chrome + `--headless=new` with Selenium Manager per call,
  (ii) same with an explicit driver (skip SM), (iii) **chrome-headless-shell** (binary-
  matched to chromedp/rod). The SM per-call tax = (i)−(ii); the binary effect = (ii)−(iii).
  Compare to chromedp 102 ms / rod 119 ms p50 on the same host. Prediction: the
  chromedriver/W3C overhead is small; the big number is the full-Chrome+new-headless binary.
- **H5 (concurrency model cost):** shared one session (N tabs, **serial** — a session is not
  thread-safe) vs N **separate** drivers (concurrent). Report wall-time distribution and the
  peak **browser** AND **chromedriver** process counts. Prediction: shared = 1+1 procs but
  serial; separate = N+N procs but concurrent — Selenium can't reach the CDP drivers'
  "1 process, N concurrent pages" sweet spot.

## Test matrix (tied to hypotheses)

| # | Test | Fixture route / mode | Measures | H |
|---|---|---|---|---|
| 1 | SM cold resolve | isolated empty cache | driver version + network cost | H0 |
| 2 | SM warm resolve | same cache ×3 | cache-hit cost | H0 |
| 3 | SM stale cache | cache seeded with 145 only | reuse vs fetch matching | H0 |
| 4 | recall: page_source | `/classes`, get()+page_source | A/B/C vs ground truth | H1 |
| 5 | recall: implicit_wait | `/classes` | A/B/C | H1 |
| 6 | recall: WebDriverWait | `/classes` | A/B/C | H1 |
| 7 | recall: poll | `/classes` | A/B/C | H1 |
| 8 | injection-timing gradient | `/classes?delay=N` | recall vs delay; explicit elapsed | H1 |
| 9 | presence on display:none | `/waitsem` hidden node | returns? elapsed | H3 |
| 10 | visibility on display:none | `/waitsem` same node | timeout? elapsed | H3 |
| 11 | CSS vs XPath | `/waitsem` visible node | both return | H3 |
| 12 | deadline honored | never-appearing selector | clean timeout, no hang | H3 |
| 13 | graceful quit() | unique udd | reap both driver+browser + ms | H2 |
| 14 | exit-no-quit | unique udd | pgrep+pid both-orphan? | H2 |
| 15 | SIGKILL crash | unique udd | pgrep+pid both-orphan? | H2 |
| 16 | cold-start full+SM | full chrome, SM each call | p50 + range | H4 |
| 17 | cold-start full+driver | full chrome, explicit driver | p50 + range (SM tax) | H4 |
| 18 | cold-start headless-shell | headless-shell, explicit driver | p50 + range (binary effect) | H4 |
| 19 | shared session, 4 tabs | one driver, 4 tabs serial | wall + browser/driver procs | H5 |
| 20 | 4 separate drivers | 4 drivers concurrent | wall + browser/driver procs | H5 |
| 21 | server-side fetch-truth | all runs | which paths Chrome fetched | all |
| 22 | 500 / dead-link robustness | `/failure/500`, `/broken` | error surfaced, no crash | robustness |
| 23 | determinism | repeat recall/waitsem/lifecycle | same result across 3 runs | H1/H2/H3 |

Fixture (local, `127.0.0.1`, Chrome hits loopback): **reuse the chromedp / rod / katana
same-fixture, server-side-hit-counter philosophy verbatim** — the identical three content
classes so Selenium's numbers are directly comparable. Class **A** static `<a>` (literal in
served HTML); **B** injected **synchronously** by an inline `<script>` at parse; **C**
injected **after load** via `setTimeout`, marker+href **assembled from fragments** so no
contiguous literal exists in any served byte (only executing + waiting reveals it). A
**server-side hit counter** records which paths Chrome actually fetched. Recall is computed
against a pre-registered ground-truth marker set — never guessed. Process-truth
(orphan/reap) uses `pgrep` on a unique `--user-data-dir` (browser tier) **plus pid
liveness** on the chromedriver pid (driver tier).

## Harness design (Python probe + Python orchestrator)

A single **Python probe** (`tests/harness/selenium_probe.py`) with sub-commands
(`recall`, `waitsem`, `graceful`, `startidle`, `coldstart`, `concurrency`) drives a real
Chrome via chromedriver/W3C and prints raw JSON. The `run_*.py` orchestrators start the
fixture, invoke the probe as a **fresh subprocess** per measurement, and compute recall vs
`ground_truth.json`. **The probe returns raw page_source / hrefs / measured booleans +
timings + pids; Python computes recall** (anti-hardcoding: no verdict string in the probe;
`classify()` lives only in `run_recall.py`). A separate `run_provisioning.py` exercises
Selenium Manager directly with isolated caches. Artifacts are `_redact`-ed (`$HOME`→`~`)
exactly like chromedp/rod. Selenium runs under a `uv` venv with `selenium>=4,<5`; the
chromedriver is auto-supplied by Selenium Manager (path recorded) or passed explicitly to
skip SM.

## Information-gain verdict: PROCEED

Not parked, not blocked. Network is open and Selenium Manager provisions live (verified:
151.0.7922.10 → chromedriver 151.0.7922.47). The consensus is dense ("Selenium Manager just
works," "use explicit waits," "call quit()") but **entirely qualitative on the five
questions that decide the modern-WebDriver story**: (1) Selenium Manager's real
resolution/cost/cache behavior; (2) which wait idiom recovers post-load content and at what
latency; (3) whether a no-quit exit / crash orphans BOTH the driver and the browser
(process-truth); (4) the honest cold-start decomposition (protocol vs binary); (5) the
serial-single-session vs concurrent-N-process tradeoff. Each is measurable on a local
fixture with no credentials, on the **same host + Chrome build** as the published
chromedp/rod packs — a genuine head-to-head no SERP source provides, and none of it is the
banned generic Playwright comparison.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on the **local fixture** (`127.0.0.1`) + a local Chrome for Testing build 1232
  (reused). No third-party/production host, no anti-bot, no auth bypass, no rate abuse.
  Selenium is a general browser driver; framing is "live-browser driver behavior on
  controlled ground truth."
- No credentials anywhere. Artifacts redact `$HOME`→`~`; the probe redacts the home prefix
  before printing JSON too.
- **Selenium Manager caches are isolated temp dirs** — the user's real `~/.cache/selenium`
  is read (to seed the stale-cache experiment from a copy) but **never modified/deleted**.
- Record exact Chrome path + version, chromedriver version + path, selenium + Selenium
  Manager version, Python version, exact commands. **Do not** copy the chromedriver or a
  browser binary into the pack; gitignore driver binaries and the selenium cache.
- Timing (cold-start, concurrency) reported as distributions; overlap ⇒ tie. Claims scoped
  to this fixture, selenium version, Chrome build, and macOS arm64.
- **Novelty honesty:** Selenium Manager existence + auto-download, the W3C protocol,
  chromedriver-as-separate-process, `quit()`-required, explicit-vs-implicit waits, and
  presence-vs-visibility semantics are **DOCUMENTED** (official selenium.dev docs). Only the
  *quantifications* on this fixture (SM cold/warm/stale numbers + resolved patch, the recall
  matrix + 500 ms poll quantization, the both-orphan process-truth vs chromedp/rod,
  cold-start decomposition, concurrency two-tier cost) are candidates for EXCLUSIVE. **Do
  not** claim the two-process orphan from the doc alone — only from the pgrep + pid
  measurement.

## Source evidence

- Official: [Selenium Manager docs](https://www.selenium.dev/documentation/selenium_manager/),
  [WebDriver drivers](https://www.selenium.dev/documentation/webdriver/drivers/),
  [waits](https://www.selenium.dev/documentation/webdriver/waits/),
  [driver sessions / quit](https://www.selenium.dev/documentation/webdriver/drivers/service/),
  [selenium-manager source](https://github.com/SeleniumHQ/selenium/tree/trunk/rust).
- Chrome for Testing endpoints (used by Selenium Manager):
  [known-good-versions](https://googlechromelabs.github.io/chrome-for-testing/),
  driver zips under `storage.googleapis.com/chrome-for-testing-public/`.
- Representative SERP (design-time; NOT reproduced as claims): Selenium 4.6 release notes on
  Selenium Manager; BrowserStack/ZenRows "Selenium driver management" posts.
