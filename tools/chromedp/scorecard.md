# chromedp — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking. Weights
are pack-local and pre-registered here; scores are evidence-anchored, each citing a
run.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 8 | single Go binary (`go build`); pure-Go module but needs an external Chrome via `ExecPath` |
| Static/sync-injected extraction | 12 | 12 | classes A + B recovered 3/3 in every wait strategy (`recall-summary.json`) |
| Runtime (post-load) content | 12 | 9 | class C recovered only by a node-keyed `WaitVisible`/poll; `Navigate` and `WaitReady(body)` miss it |
| Wait-action clarity | 10 | 7 | `WaitReady`=attached vs `WaitVisible`=visible diverge on `display:none`; deadline clean; #440 not reproduced |
| Context lifecycle / cleanup | 12 | 8 | cancel reaps in ~13 ms; macOS exit-without-cancel orphans (godoc force-kill is Linux-scoped) |
| Cold-start cost | 10 | 9 | p50 102 ms, 98–111 over 5 fresh processes |
| Concurrency model | 10 | 9 | shared browser 1 proc / 214 ms vs separate 4 procs / 264 ms; ranges disjoint |
| Determinism | 8 | 8 | recall found-sets + wait-sem + lifecycle identical across 3 runs |
| Robustness (500 / dead link) | 6 | 6 | driver survives 500 + dead link; later actions still run |
| Cost transparency | 10 | 8 | distributions with min–max; overlap⇒tie logic applied to concurrency |
| **Total** | **100** | **84** | provisional research-material score only |

Scoring notes:

- **Runtime (post-load) content** is marked down (9/12) because the live browser
  recovers runtime-injected content **only** with a wait keyed to the injected node:
  the naive `Navigate`+read and `WaitReady("body")` both return class-C recall 0 (C
  injected 800 ms after load), while `WaitVisible("#delayed-injected")` and a poll
  return it. The gap is a footgun for "just render it and read," not a capability
  limit — hence partial, not full, credit.
- **Wait-action clarity** (7/10): `WaitReady` and `WaitVisible` answer different
  questions (attached vs visible), which the docs state but the folklore blurs; on a
  `display:none` node they diverge cleanly (`WaitReady` ~12 ms, `WaitVisible` 4 s
  deadline). Points held back because the naming invites the classic mistake, though
  the deadline is honored cleanly and the [#440] default-query hang did **not**
  reproduce (v0.16.0).
- **Context lifecycle / cleanup** (8/12): cancelling reaps Chrome in ~13 ms
  (`exec.CommandContext`), but on macOS a process that exits **without** cancel
  orphans the browser (measured 3/3) — the godoc force-kill guarantee is Linux-scoped.
  `defer cancel()` is load-bearing on macOS, so the dimension can't score full.
- **Concurrency model** (9/10): four child contexts share one browser process (1 vs 4)
  with a disjoint, lower wall-time band (214 vs 264 ms p50). The process/memory lever
  is clear; the wall-time gap is modest and workload-specific, so not a perfect score.
- **Cost transparency** (8/10): cold-start and concurrency reported as distributions
  with ranges and an explicit overlap⇒tie rule; docked because Linux and larger-N /
  real-workload timings are gaps, not measurements.
- Scores reflect **live-browser driver behavior** (dynamic-content recall, wait
  semantics, lifecycle, cost) only; chromedp is not scored on structured-data
  extraction or on Chrome's own rendering, which are out of its scope.
