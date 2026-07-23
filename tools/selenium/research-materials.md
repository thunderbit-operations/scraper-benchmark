# selenium — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **selenium**
(`SeleniumHQ/selenium`, Python bindings), the **W3C WebDriver** browser-automation library
that drives a real Chrome through **chromedriver** (a separate process), not the Chrome
DevTools Protocol. Since Selenium 4.6 it ships **Selenium Manager**, a bundled Rust binary
that auto-downloads a matching chromedriver on a driverless `webdriver.Chrome()`. It judges
the **behavior of that modern-WebDriver setup + rendering path on controlled ground truth**:
Selenium Manager's real provisioning behavior, whether Selenium's wait idioms recover
runtime-injected DOM content, its presence-vs-visibility semantics, the **two-process
(driver + browser) lifecycle** under `quit()` vs no-quit vs crash, cold-start cost, and the
concurrency model. It does **not** score Chrome itself, nor field extraction (Selenium hands
you the DOM/elements; what you pull out is your code).

**Direct comparison objects: chromedp + rod** (`tools/chromedp/` commit `a605159`,
`tools/rod/` commit `41dee73`, both published). Those are the two Go CDP drivers; every
selenium test here ran on the **identical fixture, harness shape, host, and Chrome build**,
so the numbers are apples-to-apples. Central question (from the pre-test gate + the queue
focus): the consensus says "Selenium Manager just works," "use explicit waits for dynamic
content," and "call `quit()` or you leak" — each **qualitative**. This pack measures
Selenium Manager's real resolution/cost/cache behavior, per-idiom recall by injection
timing, wait-primitive semantics on a controlled node, the two-tier orphan/reap
process-outcome, the cold-start distribution **decomposed into protocol vs binary**, and the
shared-vs-separate concurrency cost — each next to chromedp's / rod's published numbers, and
**without** the queue-banned generic Playwright comparison.

All tests run against a **local fixture on 127.0.0.1**. No third-party or production host is
driven; no anti-bot, no auth bypass, no rate abuse. **Cross-series axis:** the class-C
runtime-injected node here is the same content class katana's static crawl misses,
playwright-mcp's live a11y snapshot catches, chromedp catches only with an explicit
`WaitVisible`, and rod catches with its auto-waiting `Element` — selenium is the fifth
same-fixture data point, and the axis on which its explicit-wait model lands.

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-24** (see `metadata-snapshot.md`; refresh
within 48h before any final draft):

| Field | Value |
|---|---|
| Repo | [SeleniumHQ/selenium](https://github.com/SeleniumHQ/selenium) |
| Stars | **34,307** |
| Open issues | **181** |
| License | **Apache-2.0** |
| Default branch | **trunk** |
| Last push | **2026-07-23T14:13:20Z** |
| Version tested | selenium (Python) **4.46.0** |
| Selenium Manager | **0.4.46** (bundled Rust binary) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (25F84) arm64 |
| selenium (Python) | **4.46.0** |
| Selenium Manager | **selenium-manager 0.4.46** |
| chromedriver | **151.0.7922.47** (auto-supplied by Selenium Manager; matches browser build 151.0.7922, latest patch .47 ≠ browser .10) |
| Chrome | **Chrome for Testing 151.0.7922.10** (build **1232**), full binary, `--headless=new` — same Chrome **version/build** chromedp/rod used (they drove the build-1232 headless-shell; see parity note) |
| Chrome (binary-matched variant) | **chrome-headless-shell** build 1232 (cold-start decomposition only) |
| Python (runner + probe) | **3.14.2** (uv venv; only third-party dep is `selenium`) |
| Provisioning runner | [tests/run_provisioning.py](tests/run_provisioning.py) → [provisioning-summary.json](artifacts/raw/provisioning-summary.json) |
| Recall runner | [tests/run_recall.py](tests/run_recall.py) → [recall-summary.json](artifacts/raw/recall-summary.json) |
| Wait-semantics runner | [tests/run_waitsem.py](tests/run_waitsem.py) → [waitsem-summary.json](artifacts/raw/waitsem-summary.json) |
| Lifecycle runner | [tests/run_lifecycle.py](tests/run_lifecycle.py) → [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json) |
| Cold-start runner | [tests/run_coldstart.py](tests/run_coldstart.py) → [coldstart-summary.json](artifacts/raw/coldstart-summary.json) |
| Concurrency runner | [tests/run_concurrency.py](tests/run_concurrency.py) → [concurrency-summary.json](artifacts/raw/concurrency-summary.json) |
| Probe | [tests/harness/selenium_probe.py](tests/harness/selenium_probe.py) |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) (content classes A/B/C + wait-sem page + robustness routes — byte-identical to the chromedp/rod fixtures) |

Setup / reliability notes (recorded because they affect reproduction):

- **Two runtime dependencies.** Selenium needs BOTH an external Chrome **and** a chromedriver
  binary. Selenium Manager auto-supplies chromedriver (H0); the browser must already exist.
- **Chrome-binary choice (parity note).** chromedp/rod pointed CDP at the build-1232
  **headless-shell**. chromedriver launches the browser with a client `--user-data-dir`; on
  headless-shell that trips `unable to discover open pages`, so this pack drives the **full
  Chrome for Testing 151.0.7922.10 (build 1232)** with `--headless=new` (accepts the client
  profile dir the pgrep process-truth needs). Same Chrome version/build; recall (DOM/JS
  timing) is identical across the two headless variants, and cold-start is measured on
  **both** to isolate the binary effect.
- **Anti-hardcoding split.** The probe returns *raw* `page_source`, hrefs, measured
  booleans/timings/pids. **Recall is computed in Python** against the fixture's
  pre-registered ground-truth markers (`ground_truth.json`) — no verdict/observation string
  is baked into the probe (`classify()` lives only in `run_recall.py`; grep finds 0
  class-recall logic in the probe).
- **Two-tier process-truth.** The **browser** tier is counted via `pgrep` on a **unique
  `--user-data-dir`** (argv[0] basename `Google Chrome for Testing`, no `--type=`); the
  **driver** tier by **pid liveness** on the chromedriver pid (chromedriver does not carry
  the udd). This two-tier counter is the Selenium-specific addition over chromedp/rod.
- **Isolated Selenium Manager caches.** H0 uses temp `--cache-path` dirs; the user's real
  `~/.cache/selenium` is read (to copy a stale 145 driver for the seed) but never modified.

## Test Coverage Completed

Fixture ground truth (`artifacts/raw/ground_truth.json`) — three content classes that
separate *when* content exists, byte-identical to the chromedp/rod/playwright-mcp/katana
fixtures, plus a wait-semantics page and robustness routes:

- **Class A — static HTML `<a>`:** marker `STATIC_ALPHA_MARKER_A`, href `/page/alpha`, a
  literal in the served bytes. Present at parse.
- **Class B — sync-injected:** an `<a>` created by an **inline `<script>`** during initial
  parse; marker + href **assembled from fragments** so no contiguous literal exists in any
  served byte. Present by the load event.
- **Class C — delayed-injected:** an `<a>` created **`DELAY` ms after the load event** via
  `setTimeout`; marker + href assembled from fragments. A naive read after navigate cannot
  see it.
- Plus: a `/waitsem` page (visible node + attached-but-hidden `display:none` node), a
  `/failure/500` route and a `/broken` dead link, and leaf pages whose fetches the
  server-side counter records.

### H0 — Selenium Manager driver auto-provisioning (`provisioning-summary.json`)

Isolated caches; browser = Chrome for Testing **151.0.7922.10**:

| Scenario | Result | Cost |
|---|---|---:|
| **COLD** (empty cache) | resolves + downloads **chromedriver 151.0.7922.47** | **4054 ms** (network) |
| **WARM** (cache hit, ×3) | same driver, no network | **28 / 25 / 25 ms** |
| **STALE** (cache seeded with chromedriver **145** only) | **fetches 151.0.7922.47** — the stale 145 is **not** reused | (network) |

Computed reading (`reading`): `resolved_driver_version = 151.0.7922.47`;
`driver_matches_browser_build = true` (151.0.7922); **`driver_patch_differs_from_browser_patch
= true`** (driver .47 ≠ browser .10); `cold_over_warm_ratio ≈ 156×`; stale-cache
`reused_stale_145 = false`, `fetched_matching_151 = true`.

Reading: on a driverless `webdriver.Chrome()`, Selenium Manager detects the browser and
resolves a chromedriver on the **major.minor.build** (151.0.7922), taking the **latest
available patch (.47)** — **not** the browser's own patch (.10), because Chrome for Testing
publishes one chromedriver per build. The **first** resolution pays a one-time network
download (~4 s here); every subsequent call is a **~25 ms cache hit** (a ~156× gap). A
**stale, mismatched** driver already in the cache (145.x while the browser is 151.x) is
**not** reused — Selenium Manager fetches the matching 151 and leaves the 145 in place. This
is the concrete behavior behind "Selenium Manager just works," measured rather than asserted.

### H1 — recall matrix: selenium idiom × content class (`recall-summary.json`)

Class-C injected 800 ms after load; each idiom run 3× (found-sets identical all three —
`determinism_found_sets.*.stable = true`):

| selenium idiom | A static | B sync-injected | C delayed-injected | elapsed |
|---|:--:|:--:|:--:|---:|
| `get()` + `page_source` (default) | ✓ | ✓ | **✗** | 74 ms |
| `implicitly_wait(20)` + `find_element(C)` + `page_source` | ✓ | ✓ | **✓** | 901 ms |
| **`get()` + `WebDriverWait(20).until(presence_of C)` + `page_source`** | ✓ | ✓ | **✓** | 1080 ms |
| `get()` + poll `page_source` until marker | ✓ | ✓ | **✓** | 936 ms |

Computed contrast (`contrast` field): `C_delayed_found_by: ["implicit","explicit","poll"]`;
`pagesource_misses_C: true`; `implicit_wait_finds_C: true`; `explicit_wait_finds_C: true`.

Injection-timing gradient (`injection_timing_gradient`), `page_source` vs `WebDriverWait` —
with the chromedp `WaitVisible` and rod `Element` references on the identical fixture:

| C injected after load | Selenium `page_source` sees C? | Selenium `WebDriverWait` sees C? | Selenium wait elapsed | chromedp `WaitVisible` | rod `Element` |
|---:|:--:|:--:|---:|---:|---:|
| 0 ms | yes (race) | yes | 44 ms | 109 ms | 12 ms |
| 100 ms | **no** | yes | 567 ms | 208 ms | 214 ms |
| 400 ms | **no** | yes | 567 ms | 519 ms | 628 ms |
| 800 ms | **no** | yes | 1084 ms | 911 ms | 1428 ms |
| 1500 ms | **no** | yes | 1580 ms | 1625 ms | 2858 ms |

Reading: Selenium's default `driver.get()` blocks to the load event (pageLoadStrategy
`normal`), so `page_source` is an **at-load snapshot** that recovers A + B but **misses
class C** for any post-load delay ≥ ~100 ms — the **same footgun** as chromedp's naive read
and rod's `WaitLoad`+`HTML`; the 0 ms row is the boundary (`setTimeout(…,0)` can fire before
the read). Recovering class C needs a **wait**: the idiomatic explicit
`WebDriverWait(presence_of C)` recovers it (parity with chromedp's explicit `WaitVisible`),
and `implicitly_wait` + `find_element(C)` also recovers it (implicit wait polls the find, and
`page_source` is read after it returns) — though the Selenium docs warn against **mixing**
implicit and explicit waits. **Honest latency signature:** the explicit-wait elapsed shows
`WebDriverWait`'s **default 500 ms poll quantization** — the 100 ms and 400 ms delays both
land at **567 ms** (caught at the first 500 ms poll after injection), 800 ms → 1084 ms
(caught at the 1000 ms poll). That is **coarser** than chromedp's event-driven `WaitVisible`
(tracks tightly: 800 → 911 ms) but **finer** than rod's exponential-backoff `Element` at
longer delays (800 → 1428 ms). A real, measured wait-latency profile — not a speed claim.

### H3 — presence vs visibility semantics + selector model (`waitsem-summary.json`)

On the `/waitsem` page; each run 3× (identical all three):

| Target | Action | Result | elapsed |
|---|---|---|---:|
| `#hidden-target` (attached, `display:none`) | `find_element` (presence) | **returns** | ~5 ms |
| `#hidden-target` (attached, `display:none`) | `WebDriverWait(visibility_of)` | **times out** (`TimeoutException`) | ~4168 ms |
| `#visible-target` | `By.CSS_SELECTOR` | returns | ~5 ms |
| `#visible-target` | `By.XPATH` | returns | ~7 ms |
| `#never-appears-xyz` | `WebDriverWait` (2 s) | **times out** (`TimeoutException`) | ~2053 ms |

Reading: Selenium's `find_element` answers **presence/attached** (returns in ~5 ms for a
`display:none` node), while an explicit `visibility_of_element_located` answers **actually
visible** and blocks to the deadline with a clean `TimeoutException` (~4 s, no hang). This
mirrors chromedp's `WaitReady` vs `WaitVisible` and rod's `Element` vs `WaitVisible` split
exactly. Selenium's selector model is explicit — `By.CSS_SELECTOR` and `By.XPATH` are
separate locators that both resolve the visible node, so there is **no chromedp-#440-style
default-query trap**. The never-appearing selector honors the page timeout with a clean
error — the deadline test.

### H2 — lifecycle: two-process reap vs orphan on macOS, process-truth (`lifecycle-summary.json`)

The headline. Selenium's chain is **python → chromedriver → chrome (+ helpers)**;
chromedriver is a separate long-lived child process. Process-truth via `pgrep` on a unique
`--user-data-dir` (browser tier) **plus pid liveness** on the chromedriver pid (driver tier);
each path 3×:

| Path | chromedriver process | chrome browser proc | Outcome |
|---|---|---|---|
| graceful `driver.quit()` | 1 → **0** | 1 → **0** | **both reaped**, reap_ms **100 / 98 / 110** |
| python **exits without `quit()`** (`os._exit`) | 1 → **1** | 1 → **1** | **both orphaned** (all 3), then force-cleaned |
| parent **SIGKILL** (crash) | 1 → **1** | 1 → **1** | **both orphaned** (all 3), then force-cleaned |

**Cross-tool references on the identical host:** chromedp — cancel reaps in ~13 ms;
**exit-without-cancel orphans the browser 3/3** (macOS `allocate_other.go` no-op), **one**
process. rod — default leakless **reaps** on exit **and** SIGKILL (0 orphans). Selenium sits
at the opposite end: **no leakless-style guardian and no parent-death signal by default**, so
a no-quit exit or a crash orphans **both tiers**.

Reading: `driver.quit()` (the W3C DELETE-session command + chromedriver termination) cleanly
reaps **both** the chromedriver process and the browser in ~100 ms (3/3). But a Python
process that **exits without `quit()`** — and one that is **SIGKILLed** mid-session — leaves
**both** the chromedriver process **and** the browser it owns running (1 → 1 on each tier,
all 3 runs, both paths). That is **one process worse** than chromedp's browser-only macOS
orphan and the **opposite** of rod's leakless reap: the extra driver-process tier is the
Selenium-specific liability, and it is why `quit()` (typically in a `try/finally` or context
manager) is not optional. `all_orphans_cleaned = true` — every orphan in this test was
force-killed by the runner (kill the chromedriver pid **and** `pkill` the udd; a bare
`pkill -f <udd>` leaves chromedriver alive because it does not carry the udd).

### H4 — cold-start cost, decomposed (protocol vs binary vs Selenium Manager) (`coldstart-summary.json`, 5 fresh processes each)

Each sample is a genuinely cold cycle (fresh process: instantiate `webdriver.Chrome` →
navigate → first `execute_script`):

| Config | p50 | min–max | mean |
|---|---:|---:|---:|
| full Chrome + `--headless=new`, **Selenium Manager each call** | 848 ms | 829–850 | 844.6 |
| full Chrome + `--headless=new`, **explicit driver (skip SM)** | 818 ms | 800–857 | 821.0 |
| **chrome-headless-shell (binary-matched to chromedp/rod), explicit driver** | **168 ms** | 118–282 | 172.4 |
| **chromedp (same host/Chrome build)** | **102 ms** | 98–111 | — |
| **rod (same host/Chrome build)** | **119 ms** | 117–124 | — |

`selenium_manager_per_call_tax_ms_p50 = 30` (ranges overlap → within noise);
`full_chrome_over_headless_shell_p50_delta_ms = 650`.

Reading (this is where the SERP trope dies): Selenium's cold start on **full Chrome +
`--headless=new`** is ~818 ms — ~8× chromedp/rod. But that gap is **almost entirely the
browser binary, not the WebDriver protocol**: driving the **same chrome-headless-shell
binary** chromedp/rod used drops Selenium's cold start to **168 ms p50**, only **~50–70 ms
above** chromedp (102 ms) and rod (119 ms). So the **chromedriver + W3C-handshake overhead is
only ~50–70 ms**; the remaining ~650 ms is the heavier full-Chrome + new-headless startup —
a binary/headless-mode choice orthogonal to Selenium. The **Selenium Manager per-call tax**
(it spawns the SM binary to resolve even when cached) is a small **~30 ms**, within the
noise floor. Scoped to macOS arm64 + warm on-disk binaries; the headless-shell variant has
wider spread (118–282). Confirms the runtime dependency on **both** an external Chrome and a
chromedriver.

### H5 — concurrency: shared session vs separate sessions (`concurrency-summary.json`)

N=4 navigations, 3 runs each mode, with the chromedp/rod references:

| Mode | Selenium wall p50 | Selenium min–max | Selenium peak procs | chromedp | rod |
|---|---:|---:|:--|---:|---:|
| shared (1 driver, 4 tabs, **serial**) | **2942 ms** | 2915–3061 | **1 browser + 1 driver** | 214 ms / 1 proc | 211 ms / 1 proc |
| separate (4 drivers, **concurrent**) | **1243 ms** | 1193–1255 | **4 browsers + 4 drivers** | 264 ms / 4 procs | 1302 ms / 4 procs |

`wall_ranges_overlap: false`. Reading: a **single WebDriver session is not thread-safe** and
serializes commands over one connection to chromedriver, so the shared-session path runs the
4 tab-navigations **sequentially** (~2942 ms ≈ 4 × per-tab) on **one** browser + **one**
chromedriver. To run the 4 navigations **concurrently** you need **4 separate drivers** —
faster wall (1243 ms) but at **4 chromedriver + 4 chrome** processes (8 total). This is the
Selenium-specific **inversion** of the CDP-driver story: chromedp/rod's shared browser gives
you **both** concurrency **and** one process (N goroutines over one CDP connection);
Selenium's single session gives you **one process xor concurrency** — you cannot have both.
The durable, mechanism-clear finding is the **two-tier process count** (1+1 vs 4+4) and the
serial-single-session constraint; the absolute wall numbers are full-Chrome-specific (a
headless-shell per-tab cost would be lower), so they are scoped, not headlined.

### Robustness

The `/failure/500` and a non-existent `/broken` route are reachable; navigation surfaces the
outcome without crashing the driver (the session stays usable and later actions still run).
Recorded via the server-side hit counter and the runners' clean completion.

## Key Findings for the Writer

1. **FINDING-01 — Selenium Manager auto-resolves a build-matched chromedriver (latest patch,
   not the browser's), cheap when warm and immune to a stale cached driver (measured).** For
   browser 151.0.7922.10 it downloads **chromedriver 151.0.7922.47** (build match; patch .47
   ≠ .10), cold ~4054 ms (one-time network) vs warm ~25 ms (~156×), and **does not reuse** a
   stale 145 driver already in cache — it fetches the matching 151. Confidence: high (isolated
   caches; SM's own JSON output). This is the concrete "modern WebDriver setup" behavior.

2. **FINDING-02 — Selenium's default `page_source` reads at the load event and misses
   post-load-injected content; recovery needs an explicit wait, with a 500 ms poll
   quantization (measured, 3× deterministic).** On class C (injected 800 ms post-load),
   `get()`+`page_source` recovers A+B but **not** C; `WebDriverWait(presence_of)`,
   `implicitly_wait`+find, and a poll recover all three. The explicit-wait elapsed exposes
   `WebDriverWait`'s documented default 500 ms `poll_frequency` (Selenium docs; the value
   itself is documented — the recovery-latency effect below is the measured contribution;
   100 ms & 400 ms delays both → 567 ms) —
   coarser than chromedp's event-driven `WaitVisible`, finer than rod's backoff at long
   delays. Same at-load footgun as chromedp/rod; the recovery idiom (explicit wait) parallels
   chromedp's `WaitVisible`. Confidence: high (deterministic matrix + monotonic gradient).
   Cross-series: same class katana misses / playwright-mcp catches / chromedp+rod catch with
   a wait.

3. **FINDING-03 — `find_element` (presence) and `visibility_of_element_located` answer
   different questions; they diverge cleanly on a `display:none` node, and Selenium's locator
   model has no #440-style trap (measured).** `find_element` returns for a `display:none`
   node (~5 ms); explicit visibility blocks to the deadline and returns a clean
   `TimeoutException` (~4 s). `By.CSS_SELECTOR` and `By.XPATH` both resolve the visible node.
   Never-appearing selector honors the deadline cleanly. Confidence: high (3× identical).

4. **FINDING-04 — `quit()` reaps both tiers, but a no-quit exit AND a crash orphan BOTH the
   chromedriver process and the browser on macOS — one process worse than chromedp, the
   opposite of rod (process-truth, 3×).** `driver.quit()` reaps the chromedriver process +
   the browser in ~100 ms. A Python exit-without-`quit()` and a parent SIGKILL each leave
   **both** tiers running (1→1 each, 3/3). No leakless-style guardian, no parent-death signal
   by default. This is the Selenium-specific lifecycle liability and the reason `quit()` in a
   `finally`/context-manager is mandatory. Confidence: high (two-tier pgrep + pid liveness;
   on-quit vs no-quit vs crash isolate it).

5. **FINDING-05 — Selenium's cold-start gap vs the CDP drivers is the browser binary, not the
   WebDriver protocol; the chromedriver/W3C overhead is only ~50–70 ms (measured
   decomposition).** Full Chrome + `--headless=new` cold-starts at ~818 ms, but the **same
   headless-shell binary** chromedp/rod used drops it to **168 ms p50** — only ~50–70 ms over
   chromedp (102) / rod (119). The Selenium Manager per-call tax is ~30 ms (noise). This
   directly refutes the "Selenium is 8× slower to start" SERP framing: it conflates the
   protocol with the binary. Confidence: high (binary-matched decomposition; tax isolated by
   an on/off experiment).

6. **FINDING-06 — a single WebDriver session serializes commands, so Selenium cannot reach
   the CDP drivers' "one process, N concurrent pages"; concurrency costs N drivers + N
   browsers (measured).** Shared session, 4 tabs = **serial** (2942 ms) at 1 browser + 1
   driver; 4 separate drivers = **concurrent** (1243 ms) at 4 browsers + 4 drivers. The
   1-vs-4 process lever is doubled by Selenium's driver tier (1+1 vs 4+4). Confidence: high on
   process count + wall ranges (disjoint); the absolute per-tab wall is full-Chrome-specific.

## Provisional Scorecard

Provisional, based only on the completed material tests. **Same frozen weight template as the
chromedp/rod packs** (Part-3 rule 11), so the three live-browser drivers are directly
comparable. Not a final benchmark. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **8** | Selenium Manager auto-provisions a build-matched driver (zero-config); but needs BOTH chrome + a driver, one-time ~4 s cold provisioning |
| Static/sync-injected extraction | 12 | **12** | classes A+B recovered by every idiom (`recall-summary.json`) |
| Runtime (post-load) content | 12 | **9** | default `page_source` misses class C; explicit `WebDriverWait` (and implicit/poll) recover it; 500 ms poll quantization adds latency |
| Wait-action clarity | 10 | **8** | presence vs visibility diverge cleanly on `display:none`; explicit CSS/XPath locators, no #440-style trap; implicit-vs-explicit mixing is a documented footgun |
| Context lifecycle / cleanup | 12 | **7** | `quit()` reaps both tiers (~100 ms), but no-quit exit AND crash orphan BOTH chromedriver + chrome — one process worse than chromedp, opposite of rod |
| Cold-start cost | 10 | **7** | binary-matched 168 ms p50 (above chromedp 102 / rod 119); full-Chrome default ~818 ms; SM tax ~30 ms |
| Concurrency model | 10 | **6** | shared session is serial (1+1 procs); concurrency needs N drivers + N browsers (4+4) — no "1 process, N concurrent pages" |
| Determinism | 8 | **8** | recall + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | **6** | driver survives 500 + dead link, later actions still run |
| Cost transparency | 10 | **8** | distributions with ranges; overlap⇒tie; SM tax isolated; cold-start decomposed by binary; two-tier process counts |
| **Total** | **100** | **79** | provisional research-material score only (chromedp 84 / rod 85 on the same template) |

## Gaps Before Final Blog Draft

- **Linux lifecycle not run.** The two-process orphan is macOS-scoped here; Linux
  (chromedriver child-death behavior may differ) should be re-run before generalizing.
- **Full-Chrome vs headless-shell only decomposed for cold-start.** Recall / wait / lifecycle
  / concurrency ran on full Chrome + `--headless=new`; the absolute concurrency wall numbers
  are that-binary-specific (a headless-shell per-tab cost would be lower).
- **Selenium Manager offline/air-gapped behavior untested.** Cold provisioning needs network;
  the failure mode with no network and no cached driver is not exercised here.
- **`webdriver.Firefox`/geckodriver + `Edge` not covered.** Selenium Manager provisions those
  too; only chromedriver was measured.
- **Concurrency at N≫4 and with real per-page work untested.** Wall-time gaps are
  workload-specific; memory deltas are not measured (only process count).
- **Remote WebDriver / Grid, `Select`, Actions/CDP-hybrid (`execute_cdp_cmd`) untested.**
  Selenium exposes a CDP escape hatch; out of scope for this pack.
- **Single machine, single Chrome build.** All numbers are macOS arm64 + Chrome for Testing
  151.0.7922.10 (build 1232); cold-start and concurrency timings are host-specific.

## Novelty verification (pre-registration search)

Sources per finding: selenium issue tracker + official selenium.dev docs + top-~20 SERP.
Verdict is `[EXCLUSIVE]` / `[KNOWN: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| W3C WebDriver, chromedriver-as-separate-process, Selenium Manager existence + auto-download, `quit()`-required, explicit-vs-implicit waits, presence-vs-visibility semantics | **DOCUMENTED** | [Selenium Manager docs](https://www.selenium.dev/documentation/selenium_manager/), [drivers](https://www.selenium.dev/documentation/webdriver/drivers/), [waits](https://www.selenium.dev/documentation/webdriver/waits/); existence, not this pack's value |
| Selenium Manager resolves a **build-matched** driver taking the **latest patch (.47 ≠ browser .10)**; cold ~4 s vs warm ~25 ms (~156×); **stale 145 not reused** | **EXCLUSIVE (quantification)** | No SERP/doc source publishes the resolved patch, the cold/warm cost split, or the stale-cache-reuse behavior on a controlled browser build; zero-hit |
| default `page_source` misses post-load class C; explicit `WebDriverWait` recovers it; **500 ms poll quantization** (100/400 ms → 567 ms); vs chromedp event-driven / rod backoff on the same fixture | **EXCLUSIVE (quantification)** | No source measures Selenium's per-injection-timing recall by idiom or the poll-interval latency signature against the CDP drivers on one fixture |
| `find_element`=presence vs `visibility_of`=visible diverge on `display:none`; no #440-style locator trap | **DOCUMENTED semantics / EXCLUSIVE demonstration** | Docs define presence vs visibility + explicit locators; the measured `display:none` divergence + clean deadline is this pack's |
| a no-quit exit **and** a SIGKILL crash orphan **BOTH** chromedriver + chrome (two-tier process-truth); `quit()` reaps both | **KNOWN behavior + EXCLUSIVE quantification** | Docs warn to call `quit()` or "leak the browser"; the **two-tier pgrep + pid** count (both orphaned, vs chromedp's 1-proc orphan / rod's reap) and the exit-vs-crash proof are this pack's |
| cold-start gap is the **binary**, not the protocol — chromedriver/W3C overhead ~50–70 ms (headless-shell 168 ms vs chromedp 102 / rod 119); SM per-call tax ~30 ms | **EXCLUSIVE (quantification)** | No source decomposes Selenium's cold start into protocol vs binary; the SERP number conflates them |
| single-session serialization → concurrency needs N drivers + N browsers (1+1 vs 4+4); no "1 process, N concurrent pages" | **KNOWN limitation + EXCLUSIVE quantification** | Session non-thread-safety is documented; the shared-serial vs separate-concurrent wall + two-tier process cost on this fixture is this pack's |

**Consequence for the writer:** the information-gain items are all *measurements or mechanisms
behind documented behavior* — the Selenium Manager cold/warm/stale resolution, the recall
matrix + 500 ms poll quantization, the presence-vs-visibility divergence, the two-tier
reap-vs-orphan process-truth (with exit vs crash), the cold-start protocol-vs-binary
decomposition, and the concurrency two-tier cost. Every claim carries a confidence label and
points to a JSON field; the absolute concurrency wall is honestly scoped to the full-Chrome
binary. The queue-banned generic Playwright comparison does not appear.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* Comparatives are reported with
   ranges + the overlap⇒tie rule: concurrency ranges are **disjoint** (2942 vs 1243 ms);
   cold-start is decomposed (818 vs 168 ms; headless-shell "modestly above" chromedp/rod, not
   a bold "slower"); the SM per-call tax (~30 ms) is called noise because ranges **overlap**.
   H1 elapsed differences are framed as wait-latency profile, not a speed win.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`provisioning-summary.json`, `recall-summary.json`, `waitsem-summary.json`,
   `lifecycle-summary.json`, `coldstart-summary.json`, `concurrency-summary.json`). The
   two-process orphan is backed by the pgrep + pid measurement, **not** by the doc alone; the
   SIGKILL-crash claim is backed by the kill-path runs; the SM behavior by SM's own JSON.
3. **Blind instrument (D2)** — *Pass.* Recall is computed against pre-registered ground-truth
   markers and registers **both** presence and absence (misses C under `page_source`, catches
   it under the waits). The lifecycle counter registers both reap (1→0 both tiers on quit) and
   non-reap (1→1 both tiers on no-quit/crash) — not blind. Class B/C markers are assembled
   from fragments, so a "found" requires the browser to have **executed** JS.
4. **Mis-attribution (D3)** — *Pass.* The class-C miss is attributed to reading before the
   post-load injection — validated by the gradient (found at 0 ms, missed at ≥100 ms). The
   orphan is attributed to the missing teardown/parent-death signal — validated by the
   quit-vs-no-quit-vs-crash contrast. The cold-start gap is attributed to the **binary**, not
   the protocol — validated by the headless-shell decomposition (168 ms), ruling out "Selenium
   is slow." The concurrency wall's per-tab cost is honestly scoped to the full-Chrome binary,
   not generalized.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a verdict
   per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over this file surfaces
   only "Honest latency/…" transparency labels (rule-required), not self-praise adjectives on
   the tool.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-24** in `metadata-snapshot.md`. Stars (34,307) /
  version (selenium 4.46.0) traceable to that GitHub fetch.
- **Versions:** tested selenium 4.46.0, Selenium Manager 0.4.46, chromedriver 151.0.7922.47
  (SM-resolved), Chrome for Testing 151.0.7922.10 (build 1232), Python 3.14.2 — read from
  `selenium.__version__`, the selenium-manager binary, the run summaries, and `--version`.

## Raw Artifact Index

- Selenium Manager provisioning: [provisioning-summary.json](artifacts/raw/provisioning-summary.json)
- Recall matrix + gradient: [recall-summary.json](artifacts/raw/recall-summary.json)
- Wait semantics: [waitsem-summary.json](artifacts/raw/waitsem-summary.json)
- Lifecycle (two-tier reap / orphan): [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json)
- Cold start (decomposed): [coldstart-summary.json](artifacts/raw/coldstart-summary.json)
- Concurrency: [concurrency-summary.json](artifacts/raw/concurrency-summary.json)
- Ground truth: [ground_truth.json](artifacts/raw/ground_truth.json)
