# rod — evidence pack

Independent, reproducible tests for **rod** (`github.com/go-rod/rod`), a pure-Go library
that drives a real Chrome over the Chrome DevTools Protocol — the higher-ergonomics sibling
of chromedp. Part of the Thunderbit open-source scraping-tool benchmark. Every number in
`research-materials.md` traces to a script here and a JSON artifact under `artifacts/raw/`.

Tested version (as-of 2026-07-24): rod **v0.116.2** + leakless **v0.9.0** (Go 1.26.5),
driving **Chrome for Testing 151.0.7922.10** (headless shell, build 1232, the same binary
the chromedp pack used), macOS arm64.

## Headline

On controlled ground truth with three content classes, **rod's idiomatic `Element()` query
auto-waits and recovers post-load-injected DOM content out of the box** — the ergonomic
payoff over chromedp, whose idiomatic `Navigate`+read misses the same node and needs an
explicit `WaitVisible`. Content injected 800 ms after load is recovered by
`Element("#delayed-injected")` and by a poll, but **missed** by a naive `HTML()` snapshot
*and* by `WaitLoad`+`HTML` — the same footgun as chromedp's naive read; only the ergonomic
default differs. Honest cost: rod's auto-wait polls on a backoff, so its elapsed
*overshoots* the injection delay (800→1428 ms) where chromedp's event-driven `WaitVisible`
tracks tightly (800→911 ms). Same runtime-injected class katana misses / playwright-mcp
catches / chromedp catches only with an explicit wait — rod is the fourth same-fixture
data point.

The reverse contrast (also measured): **rod's default `leakless` reaps Chrome on
exit-without-cleanup AND on a SIGKILL crash on macOS (0 orphans, 3/3), where chromedp
orphans 3/3.** A leakless on/off toggle proves the guardian is the cause — with leakless
**off**, rod orphans identically to chromedp. Boundary: leakless covers process exit/crash,
not per-browser churn in a long-running process ([#865]).

Secondary, measured findings: `Element` (attached) and `WaitVisible` (visible) diverge
cleanly on a `display:none` node (`Element` ~2 ms; `WaitVisible` hits the 4 s deadline),
and rod's CSS/XPath method split has no chromedp-#440-style trap; cold start to first script
result is ~119 ms p50 (leakless tax ~5 ms, within noise) vs chromedp's ~102 ms; four pages
share **one** Chrome process (211 ms) while four separate browsers cost four processes and
~1302 ms (~5× chromedp's 264 ms — prefer shared).

## Reproduce

```bash
# build the probe once
cd tests/harness && go build -o rod_probe . && cd ../..
export ROD_CHROME="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1232/chrome-headless-shell-mac-arm64/chrome-headless-shell"

python3 tests/run_recall.py       # 1) H1 recall matrix + injection-timing gradient
python3 tests/run_waitsem.py      # 2) H3 Element vs WaitVisible + selector model + deadline
python3 tests/run_lifecycle.py    # 3) H2 leakless reap/orphan (on/off + SIGKILL)
python3 tests/run_coldstart.py    # 4) H4 cold-start distribution (leakless on/off) — RUN ALONE
python3 tests/run_concurrency.py  # 5) H5 shared vs separate browsers — RUN ALONE
```

Requires Go 1.26+, a Chrome/Chromium the launcher can run (path via `ROD_CHROME` or
`launcher.Bin`), and Python 3 (stdlib only). Outputs land in `artifacts/raw/*.json`. The
local fixture (`tests/fixture_server.py`) binds `127.0.0.1` on a random port and defines
every ground-truth marker, so recall is measured against a known set — never guessed. Class
B/C markers are assembled at runtime from fragments, so a "found" proves the browser
executed JS. Every runner force-kills its Chrome by a unique `--user-data-dir` and cleans
temp dirs on exit; the lifecycle test verifies zero leftover browser processes.

## What the pack establishes

- **rod-idiom recall (main headline):** class A (static) + B (sync-injected) found by every
  idiom; class C (delayed-injected) found by `Element(node)` auto-wait / poll out of the box
  — `HTML()` snapshot and `WaitLoad`+`HTML` miss it. Deterministic across 3 reps.
- **Wait semantics:** `Element` returns on a `display:none` attached node (~2 ms);
  `WaitVisible` times out at the 4 s deadline (clean `context deadline exceeded`). CSS
  `Element` and XPath `ElementX` both resolve — no #440-style trap.
- **Lifecycle (process-truth, the reverse contrast):** default leakless reaps Chrome on
  exit-without-cleanup and on SIGKILL (0 orphans, 3/3); leakless **off** orphans 3/3 like
  chromedp; graceful `Close()` reaps in ~15 ms. All orphans force-cleaned.
- **Cold start:** p50 119 ms (117–124) over 5 fresh processes; leakless tax ~5 ms (ranges
  overlap). chromedp reference: 102 ms.
- **Concurrency:** shared browser = 1 process / 211 ms p50; separate = 4 processes /
  1302 ms p50; wall ranges disjoint. chromedp reference: 214 ms / 264 ms.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, hypotheses, matrix,
  PROCEED verdict).
- `research-materials.md` — full evidence, per-finding confidence, novelty table, Part-6
  self-check, chromedp cross-tool comparison.
- `scorecard.md` — provisional dimension scores (85/100), same frozen weights as chromedp.
- `metadata-snapshot.md` — versions, exact commands, reproducibility caveats.
- `tests/` — `fixture_server.py`, five `run_*.py` runners, and `harness/` (Go probe).
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout (gitignored).

Evidence phase only: no article, no publishing. Independent audit is produced separately and
is not part of this worker's deliverable.

[#865]: https://github.com/go-rod/rod/issues/865
