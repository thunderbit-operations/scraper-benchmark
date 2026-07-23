# chromedp — evidence pack

Independent, reproducible tests for **chromedp** (`github.com/chromedp/chromedp`), a
pure-Go library that drives a real Chrome over the Chrome DevTools Protocol. Part of
the Thunderbit open-source scraping-tool benchmark. Every number in
`research-materials.md` traces to a script here and a JSON artifact under
`artifacts/raw/`.

Tested version (as-of 2026-07-23): chromedp **v0.16.0** (Go 1.26.5), driving **Chrome
for Testing 151.0.7922.10** (headless shell, build 1232), macOS arm64.

## Headline

On controlled ground truth with three content classes, **a chromedp live browser
surfaces runtime-injected DOM content — but only with a wait keyed to the injected
node.** Content injected 800 ms after the load event is recovered by
`WaitVisible("#delayed-injected")` and by a poll, but **missed** by a naive
`Navigate`+read *and* by `WaitReady("body")` (both return on the load event);
`WaitVisible`'s elapsed tracks the injection delay (100→208 … 1500→1625 ms). The
consensus "just use a headless browser" is incomplete: you need the browser **and**
the right wait. This is the same runtime-injected class katana's static crawl misses
and playwright-mcp's live snapshot catches — chromedp is the third same-fixture data
point.

Secondary, measured findings: `WaitReady` (attached) and `WaitVisible` (visible)
diverge cleanly on a `display:none` node (`WaitReady` ~12 ms; `WaitVisible` hits the
4 s deadline); cancelling the context reaps Chrome in ~13 ms, but on **macOS** a
process that exits **without** cancel **orphans** the browser (the godoc force-kill
guarantee is Linux-scoped); cold start to first script result is ~102 ms p50; four
child contexts share **one** Chrome process (214 ms) vs four separate browsers (four
processes, 264 ms, disjoint ranges).

## Reproduce

```bash
# build the probe once (binary, not `go test` — see metadata note re issue #1591)
cd tests/harness && go build -o chromedp_probe . && cd ../..
export CHROMEDP_CHROME="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell"

python3 tests/run_recall.py       # 1) H1 recall matrix + injection-timing gradient
python3 tests/run_waitsem.py      # 2) H2 WaitReady vs WaitVisible + selector query
python3 tests/run_lifecycle.py    # 3) H3 cancel-reap + macOS orphan-on-exit
python3 tests/run_coldstart.py    # 4) H4 cold-start distribution  — RUN ALONE
python3 tests/run_concurrency.py  # 5) H5 shared vs separate browsers — RUN ALONE
```

Requires Go 1.26+, a Chrome/Chromium the probe can launch (path via `CHROMEDP_CHROME`
or `ExecPath`), and Python 3 (stdlib only). Outputs land in `artifacts/raw/*.json`.
The local fixture (`tests/fixture_server.py`) binds `127.0.0.1` on a random port and
defines every ground-truth marker, so recall is measured against a known set — never
guessed. Class B/C markers are assembled at runtime from fragments, so a "found"
proves the browser executed JS. Every runner force-kills its Chrome by a unique
`--user-data-dir` and cleans temp dirs on exit.

## What the pack establishes

- **Wait-strategy recall (main headline):** class A (static) + B (sync-injected) found
  by every strategy; class C (delayed-injected) found only by `WaitVisible(node)` /
  poll — `Navigate` and `WaitReady("body")` miss it. Deterministic across 3 reps.
- **Wait semantics:** `WaitReady` returns on a `display:none` attached node (~12 ms);
  `WaitVisible` times out at the 4 s context deadline (clean `context deadline
  exceeded`). The [#440](https://github.com/chromedp/chromedp/issues/440) default-query
  hang did **not** reproduce in v0.16.0.
- **Lifecycle (process-truth):** `defer cancel()` reaps Chrome in ~13 ms; macOS
  exit-without-cancel orphans it (3/3, all force-cleaned).
- **Cold start:** p50 102 ms (98–111) over 5 fresh processes.
- **Concurrency:** shared browser = 1 process / 214 ms p50; separate = 4 processes /
  264 ms p50; wall ranges disjoint.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, hypotheses, matrix,
  PROCEED verdict).
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check.
- `scorecard.md` — provisional dimension scores (84/100), evidence-anchored.
- `metadata-snapshot.md` — versions, exact commands, reproducibility caveats.
- `tests/` — `fixture_server.py`, five `run_*.py` runners, and `harness/` (Go probe).
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout (gitignored).

Evidence phase only: no article, no publishing. `validation.md` (independent audit) is
produced separately and is not part of this worker's deliverable.
