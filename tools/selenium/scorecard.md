# selenium — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark. Weights are the **same frozen template as the chromedp/rod packs**
(pre-registered there; Part-3 rule 11), so the three live-browser drivers are directly
comparable. Scores are evidence-anchored, each citing a run.

| Dimension | Weight | Score | chromedp | rod | One-line evidence |
|---|---:|---:|---:|---:|---|
| Setup and first run | 10 | 8 | 8 | 8 | Selenium Manager auto-provisions a build-matched chromedriver (zero-config); needs BOTH chrome + a driver; one-time ~4 s cold provisioning, ~25 ms warm |
| Static/sync-injected extraction | 12 | 12 | 12 | 12 | classes A + B recovered by every idiom (`recall-summary.json`) |
| Runtime (post-load) content | 12 | 9 | 9 | 10 | default `page_source` misses class C; explicit `WebDriverWait` / implicit / poll recover it; 500 ms poll quantization adds latency |
| Wait-action clarity | 10 | 8 | 7 | 8 | presence vs visibility diverge on `display:none`; explicit CSS/XPath locators, no #440-style trap; implicit-vs-explicit mixing is a documented footgun |
| Context lifecycle / cleanup | 12 | 7 | 8 | 10 | `quit()` reaps BOTH tiers (~100 ms); no-quit exit AND crash orphan BOTH chromedriver + chrome (two-tier), no guardian |
| Cold-start cost | 10 | 7 | 9 | 8 | binary-matched 168 ms p50 (> chromedp 102 / rod 119); full-Chrome default ~818 ms; SM per-call tax ~30 ms |
| Concurrency model | 10 | 6 | 9 | 7 | shared session is serial (1+1 procs); concurrency needs N drivers + N browsers (4+4) — no "1 process, N concurrent pages" |
| Determinism | 8 | 8 | 8 | 8 | recall found-sets + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | 6 | 6 | 6 | driver survives 500 + dead link; later actions still run |
| Cost transparency | 10 | 8 | 8 | 8 | distributions with min–max; overlap⇒tie; SM tax isolated; cold-start decomposed by binary; two-tier process counts |
| **Total** | **100** | **79** | **84** | **85** | provisional research-material score only |

Scoring notes:

- **Setup and first run** (8/10, tied with chromedp/rod): Selenium Manager auto-resolves a
  **build-matched** chromedriver (151.0.7922.47 for browser 151.0.7922.10) with **no manual
  driver management** — a real modern-setup positive, and it does not reuse a stale cached
  driver. Held to 8 (not higher) because Selenium needs **both** an external Chrome **and** a
  chromedriver, and the first-ever resolution pays a one-time ~4 s network download (warm is
  ~25 ms). Same score as the CDP drivers, which need only the browser but have no
  auto-provisioner.
- **Runtime (post-load) content** (9/12, tied with chromedp, one below rod's 10): Selenium's
  *default* read (`page_source`) misses class C exactly like chromedp's naive read; recovery
  needs an **explicit** `WebDriverWait` (implicit wait and poll also work). It does not get
  rod's extra point because rod's *idiomatic* `Element()` auto-waits with **no** explicit
  call, whereas Selenium — like chromedp — requires the explicit wait. The default 500 ms
  poll quantization (100/400 ms delays both → 567 ms) is coarser than chromedp's event-driven
  wait, so it stays at 9.
- **Wait-action clarity** (8/10, one above chromedp's 7, tied with rod): `find_element`
  (presence) and `visibility_of_element_located` answer different questions, diverging cleanly
  on `display:none` (~5 ms vs ~4 s deadline). Explicit `By.CSS_SELECTOR`/`By.XPATH` locators
  avoid chromedp's `#440` default-query trap, earning the point over chromedp. Not full
  because the implicit-vs-explicit-wait mixing footgun (docs warn against it) is a real
  clarity hazard.
- **Context lifecycle / cleanup** (7/12, one below chromedp's 8, three below rod's 10): the
  headline liability. `driver.quit()` reaps **both** the chromedriver process and the browser
  in ~100 ms (3/3). But a no-quit exit **and** a SIGKILL crash each orphan **both** tiers
  (1→1 each, 3/3) — **one process worse** than chromedp's browser-only macOS orphan and the
  opposite of rod's leakless reap. Selenium has no guardian and no parent-death signal by
  default, so it scores below both CDP drivers.
- **Cold-start cost** (7/10, below chromedp's 9 and rod's 8): binary-matched (headless-shell)
  cold start is 168 ms p50 — modestly above chromedp (102) / rod (119) — and the pack-default
  full-Chrome + `--headless=new` path is ~818 ms. Even the protocol-isolated (binary-matched)
  168 ms is the slowest of the three, so the dimension is docked; the ~650 ms full-Chrome
  premium is a binary choice, not the protocol (the SERP "8× slower" framing is refuted by the
  decomposition).
- **Concurrency model** (6/10, below chromedp's 9 and rod's 7): a single WebDriver session
  serializes commands, so the shared path is **serial** (2942 ms, 1+1 procs); concurrency
  requires **N separate drivers** (1243 ms, 4+4 procs). Selenium cannot reach the CDP drivers'
  "one process, N concurrent pages," and its concurrency doubles the process cost with a
  driver tier — the lowest concurrency score of the three.
- **Cost transparency** (8/10): cold-start and concurrency reported as distributions with
  ranges and an overlap⇒tie rule; the Selenium Manager tax isolated by an on/off experiment;
  the cold-start decomposed into protocol vs binary; process counts reported per tier. Docked
  because Linux, larger-N, and Firefox/Edge remain gaps.
- Scores reflect **live-browser driver behavior** (setup/provisioning, dynamic-content recall,
  wait semantics, lifecycle, cost) only; Selenium is not scored on structured-data extraction
  or on Chrome's own rendering, which are out of its scope. The `chromedp` / `rod` columns are
  the published packs' scores on the identical weight template, for reference only — not a
  combined ranking.
