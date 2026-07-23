# rod — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark. Weights are the **same frozen template as the chromedp pack**
(pre-registered there; Part-3 rule 11), so the two Go CDP drivers are directly comparable.
Scores are evidence-anchored, each citing a run.

| Dimension | Weight | Score | chromedp | One-line evidence |
|---|---:|---:|---:|---|
| Setup and first run | 10 | 8 | 8 | chainable Must API; single Go binary (`go build`); needs external Chrome via `launcher.Bin` (or auto-downloads); one-time leakless guardian drop |
| Static/sync-injected extraction | 12 | 12 | 12 | classes A + B recovered 3/3 in every idiom (`recall-summary.json`) |
| Runtime (post-load) content | 12 | 10 | 9 | `Element` auto-wait recovers class C **out of the box** (no explicit wait); naive `HTML()` still misses it; auto-wait overshoots the delay (backoff) |
| Wait-action clarity | 10 | 8 | 7 | `Element`=attached vs `WaitVisible`=visible diverge on `display:none`; CSS/XPath split has no #440-style trap; deadline clean |
| Context lifecycle / cleanup | 12 | 10 | 8 | default leakless reaps on exit **and** SIGKILL on macOS where chromedp orphans (process-truth, on/off attributed); #865 churn boundary holds |
| Cold-start cost | 10 | 8 | 9 | p50 119 ms (117–124); modestly above chromedp 102 ms; leakless tax ~5 ms (ranges overlap) |
| Concurrency model | 10 | 7 | 9 | shared 1 proc / 211 ms (≈ chromedp); separate 4 procs / 1302 ms (~5× chromedp's 264 ms) |
| Determinism | 8 | 8 | 8 | recall found-sets + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | 6 | 6 | driver survives 500 + dead link; later actions still run |
| Cost transparency | 10 | 8 | 8 | distributions with min–max; overlap⇒tie; leakless tax isolated by an on/off experiment |
| **Total** | **100** | **85** | **84** | provisional research-material score only |

Scoring notes:

- **Runtime (post-load) content** (10/12, one better than chromedp's 9): rod's *idiomatic*
  path — querying the element — recovers runtime-injected content **with no explicit wait**,
  because `Element` auto-waits; chromedp's idiomatic `Navigate`+read misses it and needs an
  explicit `WaitVisible`. rod gets the extra point for the better default. Not full, because
  a naive `HTML()` snapshot still misses class C (same footgun), and the auto-wait polls on
  a backoff so its elapsed *overshoots* the injection delay (800→1428 ms) where chromedp's
  event-driven wait tracks tightly (800→911 ms) — an ergonomics-vs-latency tradeoff.
- **Wait-action clarity** (8/10, one better than chromedp's 7): `Element` and `WaitVisible`
  answer different questions (attached vs visible), diverging cleanly on `display:none`
  (`Element` ~2 ms, `WaitVisible` 4 s deadline). rod's CSS/XPath method split avoids
  chromedp's `#440` default-query trap, so it scores a point higher; still not full because
  the attached-vs-visible distinction is a real footgun if you pick the wrong one.
- **Context lifecycle / cleanup** (10/12, two better than chromedp's 8): the headline. rod's
  default leakless reaps the browser on exit-without-cleanup **and** on a SIGKILL crash on
  macOS (measured 0 browser procs, 3/3 each), where chromedp orphans 3/3. The on/off toggle
  proves leakless is the cause (off orphans like chromedp). Held back from full only by the
  [#865] boundary: leakless covers process exit/crash, not per-browser churn in a
  long-running process.
- **Cold-start cost** (8/10, one below chromedp's 9): p50 119 ms vs chromedp's 102 ms — a
  small, near-noise gap; the leakless tax is only ~5 ms (on/off ranges overlap), so the
  delta is rod's own launcher/connect overhead, not the guardian.
- **Concurrency model** (7/10, two below chromedp's 9): shared-browser pages are on par with
  chromedp (1 proc, ~211 ms), but separate browsers cost ~1302 ms (four processes) vs
  chromedp's 264 ms — a ~5× penalty. The process lever is clear; the separate-mode wall-time
  scaling is a rod-specific footgun on this host, so the dimension is docked.
- **Cost transparency** (8/10): cold-start and concurrency reported as distributions with
  ranges and an overlap⇒tie rule, and the leakless tax isolated by an on/off experiment;
  docked because Linux, larger-N, and the separate-mode *cause* remain gaps.
- Scores reflect **live-browser driver behavior** (dynamic-content recall, wait semantics,
  lifecycle, cost) only; rod is not scored on structured-data extraction or on Chrome's own
  rendering, which are out of its scope. The `chromedp` column is the published pack's score
  on the identical weight template, for reference only — not a combined ranking.
