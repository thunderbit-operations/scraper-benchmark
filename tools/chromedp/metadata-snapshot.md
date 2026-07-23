# chromedp — metadata snapshot

Fetched: **2026-07-23** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [chromedp/chromedp](https://github.com/chromedp/chromedp) |
| Stars | **13,202** |
| Open issues | **178** |
| License | **MIT** |
| Default branch | **main** |
| Last push | **2026-07-14T21:56:36Z** |
| Latest GitHub *Release* object | **v0.15.1**, published **2026-04-01T00:05:30Z** |
| Latest tag | **v0.16.0** (newer than the v0.15.1 Release object) |
| Version tested | **v0.16.0** (`go get github.com/chromedp/chromedp@latest` resolved v0.16.0 on snapshot day) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| chromedp | **v0.16.0** |
| cdproto (CDP bindings) | **v0.0.0-20260714215040-dc233986426f** |
| chromedp/sysutil | **v1.1.0** |
| Go toolchain | **go1.26.5 darwin/arm64** |
| cgo | chromedp dependency tree has **no cgo imports** (`go list -deps` clean); the build's `CGO_ENABLED=1` is the darwin toolchain default and unused |
| Chrome | **Chrome for Testing 151.0.7922.10**, headless shell (build **1232**) at `~/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell` (reused from the playwright-mcp worker's install) |
| Python (orchestrator) | **3.14** (runners import stdlib only; no third-party deps) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-23** |

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `127.0.0.1`, random free port; content
classes A static / B sync-injected / C delayed-injected + `/waitsem` + robustness
routes). Ground truth: `artifacts/raw/ground_truth.json`. The Go probe
(`tests/harness/main.go`) is built once and invoked per measurement.

```bash
# 0) build the probe binary ONCE (not `go test` — see note re issue #1591)
cd tests/harness && go build -o chromedp_probe . && cd ../..

# point runs at the Chrome for Testing headless shell (or set CHROMEDP_CHROME)
export CHROMEDP_CHROME="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell"

# 1) H1 recall matrix (4 strategies x 3 reps) + injection-timing gradient; ~30s
python3 tests/run_recall.py

# 2) H2 WaitReady-vs-WaitVisible semantics + selector query (3 reps); ~30s
python3 tests/run_waitsem.py

# 3) H3 lifecycle: cancel-reap (3x) + macOS orphan-on-exit (3x, force-cleaned); ~20s
python3 tests/run_lifecycle.py

# 4) H4 cold-start distribution (5 fresh processes) — RUN ALONE (timing); ~1 min
python3 tests/run_coldstart.py

# 5) H5 concurrency shared-vs-separate (3 reps each) — RUN ALONE (timing); ~1 min
python3 tests/run_concurrency.py
```

## Reproducibility notes (honest)

- **A Chrome binary is required at runtime.** chromedp's Go module is pure Go (no cgo
  imports), but it drives an external Chrome. Runs pass the exact executable via
  `chromedp.ExecPath` (env `CHROMEDP_CHROME`); with no Chrome present a run fails
  immediately. The "no external dependencies" claim is about the Go module, not the
  runtime.
- **Binary, not `go test`.** chromedp issue [#1591](https://github.com/chromedp/chromedp/issues/1591)
  reports the Go-1.25+ `go test` runner cancelling `NewExecAllocator` mid-start; the
  same code runs fine as a built binary. This pack `go build`s `chromedp_probe` and
  runs it; Go here is 1.26.5. No run used `go test`, so the pack sidesteps that class
  of failure by construction.
- **Anti-hardcoding split.** The Go probe returns raw rendered `outerHTML` + hrefs +
  measured booleans/timings; **recall is computed in Python** against the fixture's
  ground-truth markers. No verdict/observation string is baked into the probe.
- **Process-truth via `pgrep`.** Chrome reap / orphan / concurrency counts come from
  `pgrep -f <unique --user-data-dir>`, filtered to *browser* processes (no `--type=`
  flag). Each run uses a unique user-data-dir so counts never cross runs.
- **Class B/C are runtime-assembled.** The B and C markers + hrefs are built from
  string fragments + a computed number in the fixture's JS, so no contiguous literal
  exists in any served byte — a "found" therefore proves the browser executed JS, not
  that it read static bytes.
- **Mandatory cleanup.** Every runner force-kills Chrome by its unique user-data-dir
  and removes the temp dir in a `finally`; the orphan test additionally verifies
  `browser_procs_after_cleanup == 0`. Post-run host check: **0** actual
  `chrome-headless-shell` binary processes remained.
- **Timing scope.** Cold-start (p50 102 ms) and concurrency wall times are macOS arm64
  + warm on-disk headless shell; a first-ever cold-disk launch would be higher.
  Timings reported as distributions with min–max; overlapping ranges ⇒ tie.
- **The Chrome binary is NOT copied into this pack** (it lives in the ms-playwright
  cache); only its path is recorded, to keep the pack small.
