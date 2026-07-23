# selenium — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [SeleniumHQ/selenium](https://github.com/SeleniumHQ/selenium) |
| Stars | **34,307** |
| Open issues | **181** |
| License | **Apache-2.0** |
| Default branch | **trunk** |
| Last push | **2026-07-23T14:13:20Z** |
| Version tested | selenium (Python) **4.46.0** (`pip install "selenium>=4,<5"`) |
| Selenium Manager | **0.4.46** (bundled Rust binary in the pip package) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| selenium (Python bindings) | **4.46.0** |
| Selenium Manager | **selenium-manager 0.4.46** (`.../selenium/webdriver/common/macos/selenium-manager`) |
| chromedriver | **151.0.7922.47** — **auto-supplied by Selenium Manager** to `~/.cache/selenium/chromedriver/mac-arm64/151.0.7922.47/chromedriver` (matches browser build 151.0.7922; latest patch .47, not the browser's .10) |
| Chrome | **Chrome for Testing 151.0.7922.10**, build **1232**, full binary at `~/Library/Caches/ms-playwright/chromium-1232/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, driven with `--headless=new` (same Chrome **version/build** chromedp/rod used; they drove the build-1232 headless-shell — see note) |
| Chrome (binary-matched variant) | **chrome-headless-shell** build 1232 (`~/Library/Caches/ms-playwright/chromium_headless_shell-1232/…`) — the exact binary chromedp/rod drove; used in the cold-start decomposition |
| Python (runner + probe) | **3.14.2** (uv venv; only third-party dep is `selenium`) |
| Go / cgo | not applicable (Selenium bindings + probe are Python; chromedriver is a prebuilt binary) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-24** |

## Chrome-binary choice (parity note, honest)

chromedp/rod pointed CDP directly at the **chrome-headless-shell** binary (build 1232).
Selenium drives Chrome through **chromedriver**, which launches the browser with a
client-supplied `--user-data-dir`. On chrome-headless-shell that client profile dir trips
`session not created … unable to discover open pages`; the **full Chrome for Testing
151.0.7922.10 (build 1232)** binary driven with `--headless=new` accepts it. Because the
pgrep-by-unique-`--user-data-dir` process-truth method (parity with chromedp/rod) needs the
client profile dir, the pack uses **full Chrome + `--headless=new`** for recall / wait /
lifecycle / concurrency, and additionally measures **chrome-headless-shell** in the
cold-start test to isolate the binary effect. Same Chrome **version/build (151.0.7922.10 /
1232)**; the DOM/JS execution timing that class A/B/C recall depends on is identical across
the two headless variants (same Blink/V8), so cross-tool recall comparison stays valid.

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `127.0.0.1`, random free port; content classes
A static / B sync-injected / C delayed-injected + `/waitsem` + robustness routes —
byte-identical to the chromedp/rod fixtures). Ground truth: `artifacts/raw/ground_truth.json`.
The Python probe (`tests/harness/selenium_probe.py`) is invoked as a fresh subprocess per
measurement.

```bash
# 0) venv (uv) + selenium
uv venv --python 3.14 .venv
VIRTUAL_ENV="$PWD/.venv" uv pip install "selenium>=4,<5"

# point runs at the full Chrome for Testing 1232 (or set SEL_CHROME); optionally pass an
# explicit driver to SKIP Selenium Manager per call (SEL_DRIVER_PATH). Without it, the
# runners fall back to Selenium Manager auto-provisioning (still correct, slightly slower).
export SEL_CHROME="$HOME/Library/Caches/ms-playwright/chromium-1232/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export SEL_DRIVER_PATH="$HOME/.cache/selenium/chromedriver/mac-arm64/151.0.7922.47/chromedriver"

# 1) H0 Selenium Manager provisioning (cold/warm/stale, isolated caches); ~6s + network
.venv/bin/python tests/run_provisioning.py

# 2) H1 recall matrix (4 idioms x 3 reps) + injection-timing gradient; ~40s
.venv/bin/python tests/run_recall.py

# 3) H3 presence-vs-visibility + selector model + deadline (3 reps); ~20s
.venv/bin/python tests/run_waitsem.py

# 4) H2 lifecycle: graceful quit + exit-no-quit + SIGKILL, 3x each (BOTH driver+browser); ~40s
.venv/bin/python tests/run_lifecycle.py

# 5) H4 cold-start distribution (SM / explicit-driver / headless-shell) — RUN ALONE; ~90s
.venv/bin/python tests/run_coldstart.py

# 6) H5 concurrency shared-vs-separate (3 reps each) — RUN ALONE (timing); ~40s
.venv/bin/python tests/run_concurrency.py
```

## Reproducibility notes (honest)

- **Two runtime dependencies.** Selenium needs BOTH an external Chrome **and** a
  chromedriver binary. Selenium Manager auto-supplies chromedriver (measured in
  `run_provisioning.py`); the browser must already exist. With no Chrome, the session fails.
- **Selenium Manager caches are isolated.** The provisioning runner uses **temp cache dirs**
  (`--cache-path`), so the user's real `~/.cache/selenium` is read once (to *copy* a stale
  145 driver for the seed experiment) but **never modified or deleted**. The other runners
  reuse the already-cached `~/.cache/selenium/…/151.0.7922.47/chromedriver` (or re-provision
  via SM if `SEL_DRIVER_PATH` is unset).
- **Anti-hardcoding split.** The probe returns raw `page_source` + hrefs + measured
  booleans/timings/pids; **recall is computed in Python** (`classify()` in `run_recall.py`)
  against the fixture's ground-truth markers. No verdict/observation string is baked into the
  probe (`grep -nE 'A_static|B_sync|C_delayed|classes_found|classify' tests/harness/selenium_probe.py`
  is empty).
- **Process-truth is two-tier.** The **browser** tier is counted via `pgrep -f <unique
  --user-data-dir>`, keeping a process only if its argv[0] basename is `Google Chrome for
  Testing` and it has no `--type=` flag (Chrome helper procs excluded). The **driver** tier
  is counted by **pid liveness** on the chromedriver pid (`ps -p`, guarded by the
  `chromedriver` command name against pid reuse), because chromedriver does **not** carry the
  udd. This two-tier counter is the Selenium-specific addition over the chromedp/rod counter.
- **Class B/C are runtime-assembled.** The B and C markers + hrefs are built from string
  fragments + a computed number in the fixture's JS, so no contiguous literal exists in any
  served byte — a "found" therefore proves the browser executed JS, not that it read bytes.
- **Mandatory cleanup.** Every runner force-kills its Chrome by unique udd **and kills the
  chromedriver pid** (chromedriver survives a bare `pkill -f <udd>` because it lacks the udd)
  and removes temp dirs in a `finally`; the lifecycle test additionally verifies
  `browser_procs_after_cleanup == 0` **and** `chromedriver_alive_after_cleanup == 0` for
  every exit/kill run. Post-run host check: **0** chromedriver, **0** Chrome-for-Testing, **0**
  chrome-headless-shell processes remained.
- **Timing scope.** Cold-start and concurrency wall times are macOS arm64 + warm on-disk
  binaries; a first-ever cold-disk launch would be higher. Timings reported as distributions
  with min–max; overlapping ranges ⇒ tie.
- **Cross-tool comparability.** All comparison numbers cited against chromedp/rod are the
  published packs' own artifacts on this **same host + Chrome build**
  (`tools/chromedp/artifacts/raw/*.json`, `tools/rod/artifacts/raw/*.json`), not inferred
  from their prose.
- **Nothing binary is copied into the pack** — Chrome lives in the ms-playwright cache, the
  chromedriver in `~/.cache/selenium`; only their paths + versions are recorded, to keep the
  pack small. The `.gitignore` guards against a stray driver/browser copy.
