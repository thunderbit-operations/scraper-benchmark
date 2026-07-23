# rod — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [go-rod/rod](https://github.com/go-rod/rod) |
| Stars | **7,035** |
| Open issues | **209** |
| License | **MIT** |
| Default branch | **main** |
| Last push | **2026-07-15T20:12:13Z** |
| Version tested | **v0.116.2** (`go get github.com/go-rod/rod@v0.116.2`) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| rod | **v0.116.2** |
| leakless | **v0.9.0** (`github.com/ysmood/leakless`, transitive) |
| Other rod deps | gson v0.7.3, goob v0.4.0, got v0.40.0, fetchup v0.2.3 (all `ysmood/*`, indirect) |
| Go toolchain | **go1.26.5 darwin/arm64** |
| cgo | rod dependency tree has **no cgo imports** (`go list -deps -f '{{if .CgoFiles}}...'` empty); pure Go at the module level |
| Chrome | **Chrome for Testing 151.0.7922.10**, headless shell (build **1232**) at `~/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell` (the **same binary the chromedp pack used**, for parity — passed via `launcher.Bin`, which disables rod's auto-download) |
| rod default browser (NOT used) | rod would otherwise auto-download Chromium revision **1321438**; overridden with `.Bin()` for parity |
| leakless guardian | downloaded once to `~/…/T/leakless-arm64-<hash>/leakless` (per-arch binary, darwin/arm64); **not** copied into this pack |
| Python (orchestrator) | **3.14** (runners import stdlib only; no third-party deps) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-24** |

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `127.0.0.1`, random free port; content classes
A static / B sync-injected / C delayed-injected + `/waitsem` + robustness routes —
byte-identical to the chromedp fixture). Ground truth: `artifacts/raw/ground_truth.json`.
The Go probe (`tests/harness/main.go`) is built once and invoked per measurement.

```bash
# 0) build the probe binary ONCE
cd tests/harness && go build -o rod_probe . && cd ../..

# point runs at the Chrome for Testing headless shell (or set ROD_CHROME)
export ROD_CHROME="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell"

# 1) H1 recall matrix (4 idioms x 3 reps) + injection-timing gradient; ~40s
python3 tests/run_recall.py

# 2) H3 Element-vs-WaitVisible semantics + selector model + deadline (3 reps); ~20s
python3 tests/run_waitsem.py

# 3) H2 lifecycle: graceful reap + exit(leakless on/off) + SIGKILL(leakless on), 3x each; ~40s
python3 tests/run_lifecycle.py

# 4) H4 cold-start distribution (leakless on/off, 5 fresh procs each) — RUN ALONE (timing); ~2 min
python3 tests/run_coldstart.py

# 5) H5 concurrency shared-vs-separate (3 reps each) — RUN ALONE (timing); ~1 min
python3 tests/run_concurrency.py
```

## Reproducibility notes (honest)

- **A Chrome binary is required at runtime.** rod's Go module is pure Go (no cgo imports),
  but it drives an external Chrome. Runs pass the exact executable via `launcher.Bin`, which
  disables rod's auto-download; with no Chrome and auto-download off, launch fails. The
  "pure Go" claim is about the module, not the runtime. (rod *can* auto-download Chromium
  1321438 if `Bin` is unset — not used here, for parity with chromedp.)
- **leakless is on by default and drops a guardian binary.** `launcher.New()` enables
  leakless; on first use it downloads a per-arch guardian (`leakless-arm64-<hash>`) to
  `$TMPDIR` and spawns it, bridged to the Go process over TCP. Cold-start runs pre-warm the
  download so it is not part of the measured samples. The guardian binary is **not** copied
  into this pack (only its path is recorded).
- **Binary, not `go test`.** The pack `go build`s `rod_probe` and runs it; Go here is
  1.26.5. `go.mod`/`go.sum` are committed (pin rod v0.116.2 + leakless v0.9.0); the binary
  is not.
- **Anti-hardcoding split.** The Go probe returns raw rendered `HTML` + hrefs + measured
  booleans/timings; **recall is computed in Python** (`classify()` in `run_recall.py`)
  against the fixture's ground-truth markers. No verdict/observation string is baked into
  the probe (grep: 0 class-recall logic in `main.go`).
- **Process-truth via `pgrep`.** Orphan / reap / concurrency counts come from
  `pgrep -f <unique --user-data-dir>`, counting a process only if its executable basename is
  `chrome-headless-shell` and it has no `--type=` flag — so Chrome helper processes AND the
  leakless guardian (argv[0] = leakless binary) are both excluded. Each run uses a unique
  user-data-dir so counts never cross runs. This exe-basename guard is the rod-specific
  addition over chromedp's counter.
- **Class B/C are runtime-assembled.** The B and C markers + hrefs are built from string
  fragments + a computed number in the fixture's JS, so no contiguous literal exists in any
  served byte — a "found" therefore proves the browser executed JS, not that it read static
  bytes.
- **Mandatory cleanup.** Every runner force-kills Chrome by its unique user-data-dir and
  removes the temp dir in a `finally`; the lifecycle test additionally verifies
  `browser_procs_after_cleanup == 0` for every exit/kill run. Post-run host check: **0**
  actual `chrome-headless-shell` browser processes remained (`browser_leak_count=0`).
- **Timing scope.** Cold-start (p50 119 ms) and concurrency wall times are macOS arm64 +
  warm on-disk headless shell; a first-ever cold-disk launch would be higher. Timings
  reported as distributions with min–max; overlapping ranges ⇒ tie.
- **Cross-tool comparability.** All comparison numbers cited against chromedp are the
  published chromedp pack's own artifacts on this **same host + Chrome build**
  (`tools/chromedp/artifacts/raw/*.json`), not inferred from chromedp's prose.
- **Neither the Chrome binary nor the leakless guardian is copied into this pack** (they
  live in the ms-playwright cache and `$TMPDIR`); only their paths are recorded, to keep the
  pack small.
