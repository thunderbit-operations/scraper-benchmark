# selenium — evidence pack

Independent, reproducible tests for **selenium** (`SeleniumHQ/selenium`, Python bindings),
the W3C WebDriver library that drives a real Chrome through **chromedriver** (a separate
process), with **Selenium Manager** auto-supplying the driver. Part of the Thunderbit
open-source scraping-tool benchmark. Every number in `research-materials.md` traces to a
script here and a JSON artifact under `artifacts/raw/`.

Tested version (as-of 2026-07-24): selenium **4.46.0** + Selenium Manager **0.4.46**
(Python 3.14.2), auto-supplied **chromedriver 151.0.7922.47**, driving **Chrome for Testing
151.0.7922.10** (build 1232, `--headless=new`; the same Chrome version/build the chromedp/rod
packs used), macOS arm64.

## Headline

**Selenium Manager auto-provisions a build-matched chromedriver, and it is cheap and correct**
— for browser 151.0.7922.10 it downloads **chromedriver 151.0.7922.47** (matches the
`major.minor.build` 151.0.7922; latest patch .47, not the browser's .10), cold ~4 s (one-time
network) vs warm ~25 ms (~156×), and a **stale cached 145 driver is not reused** — the
matching 151 is fetched.

On controlled ground truth with three content classes, **Selenium's default `page_source`
reads at the load event and misses post-load-injected DOM content** — the same footgun as
chromedp's naive read and rod's `WaitLoad`+`HTML`. Recovery needs an explicit
`WebDriverWait` (implicit wait and poll also work), whose elapsed exposes `WebDriverWait`'s
default **500 ms poll quantization** (100 ms & 400 ms delays both land at 567 ms) — coarser
than chromedp's event-driven `WaitVisible`, finer than rod's backoff at long delays. Same
runtime-injected class katana misses / playwright-mcp catches / chromedp+rod catch with a
wait — selenium is the fifth same-fixture data point.

**The lifecycle liability (process-truth):** Selenium's chain is **python → chromedriver →
chrome**. `driver.quit()` reaps **both** the chromedriver process and the browser (~100 ms),
but a python exit **without** `quit()` **and** a SIGKILL crash each orphan **both** tiers
(1→1 each, 3/3) — **one process worse** than chromedp's browser-only macOS orphan, and the
opposite of rod's leakless reap. No guardian, no parent-death signal by default.

**Cold start, decomposed (kills the SERP trope):** full Chrome + `--headless=new` is ~818 ms,
but the **same headless-shell binary** chromedp/rod used drops Selenium to **168 ms p50** —
only ~50–70 ms over chromedp (102) / rod (119). The chromedriver/W3C overhead is small; the
gap is the browser binary, not the protocol. **Concurrency:** a single session serializes
(shared 4 tabs = 2942 ms, 1+1 procs), so concurrency needs N separate drivers (1243 ms, 4+4
procs) — Selenium can't reach the CDP drivers' "one process, N concurrent pages."

## Reproduce

```bash
# venv (uv) + selenium
uv venv --python 3.14 .venv
VIRTUAL_ENV="$PWD/.venv" uv pip install "selenium>=4,<5"

export SEL_CHROME="$HOME/Library/Caches/ms-playwright/chromium-1232/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
# optional: skip Selenium Manager per call by passing the cached driver (else SM auto-provisions)
export SEL_DRIVER_PATH="$HOME/.cache/selenium/chromedriver/mac-arm64/151.0.7922.47/chromedriver"

.venv/bin/python tests/run_provisioning.py   # H0 Selenium Manager cold/warm/stale
.venv/bin/python tests/run_recall.py         # H1 recall matrix + injection-timing gradient
.venv/bin/python tests/run_waitsem.py        # H3 presence vs visibility + selector model + deadline
.venv/bin/python tests/run_lifecycle.py      # H2 two-tier reap/orphan (quit / no-quit / SIGKILL)
.venv/bin/python tests/run_coldstart.py      # H4 cold-start decomposed (SM / driver / headless-shell) — RUN ALONE
.venv/bin/python tests/run_concurrency.py    # H5 shared vs separate sessions — RUN ALONE
```

Requires Python 3 + `selenium>=4,<5`, a Chrome/Chromium the driver can run (path via
`SEL_CHROME`), and network for the first Selenium Manager resolution (afterwards the driver is
cached). Without `SEL_DRIVER_PATH`, the runners fall back to Selenium Manager auto-provisioning
(still correct). Outputs land in `artifacts/raw/*.json`. The local fixture
(`tests/fixture_server.py`) binds `127.0.0.1` on a random port and defines every ground-truth
marker, so recall is measured against a known set — never guessed. Class B/C markers are
assembled at runtime from fragments, so a "found" proves the browser executed JS. Every runner
force-kills its Chrome by a unique `--user-data-dir` **and kills the chromedriver pid** and
cleans temp dirs on exit; the lifecycle test verifies zero leftover browser **and** driver
processes.

## What the pack establishes

- **Selenium Manager provisioning (setup headline):** resolves chromedriver 151.0.7922.47 for
  browser 151.0.7922.10 (build match, latest patch); cold ~4 s / warm ~25 ms; stale 145 not
  reused. Isolated caches — the user's `~/.cache/selenium` is not modified.
- **Recall (main rendering headline):** class A (static) + B (sync-injected) found by every
  idiom; class C (delayed-injected) missed by default `page_source`, recovered by explicit
  `WebDriverWait` / implicit wait / poll — with a 500 ms poll quantization. Deterministic
  across 3 reps.
- **Wait semantics:** `find_element` returns on a `display:none` node (~5 ms);
  `visibility_of` times out at the 4 s deadline (clean `TimeoutException`). `By.CSS_SELECTOR`
  and `By.XPATH` both resolve — no #440-style trap.
- **Lifecycle (two-tier process-truth):** `quit()` reaps chromedriver + chrome (~100 ms);
  no-quit exit AND SIGKILL each orphan BOTH tiers (3/3), all force-cleaned.
- **Cold start (decomposed):** full-Chrome 818 ms; headless-shell 168 ms (binary-matched);
  SM per-call tax ~30 ms. chromedp 102 / rod 119.
- **Concurrency:** shared session = serial, 1 browser + 1 driver, 2942 ms; separate = 4
  browsers + 4 drivers, concurrent, 1243 ms; wall ranges disjoint.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, live recon, hypotheses,
  matrix, PROCEED verdict).
- `research-materials.md` — full evidence, per-finding confidence, novelty table, Part-6
  self-check, chromedp+rod cross-tool comparison.
- `scorecard.md` — provisional dimension scores (79/100), same frozen weights as chromedp/rod.
- `metadata-snapshot.md` — versions, exact commands, reproducibility caveats.
- `tests/` — `fixture_server.py`, six `run_*.py` runners, and `harness/selenium_probe.py`.
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout (gitignored).

Evidence phase only: no article, no publishing. Independent audit is produced separately and
is not part of this worker's deliverable.
