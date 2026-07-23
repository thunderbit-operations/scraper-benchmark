# katana — metadata snapshot

Fetched: **2026-07-23** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [projectdiscovery/katana](https://github.com/projectdiscovery/katana) |
| Stars | **17,208** |
| Open issues | **21** |
| License | **MIT** |
| Default branch | **dev** |
| Last push | **2026-07-20T12:23:07Z** |
| Latest GitHub release | **v1.6.1**, published **2026-05-05T15:31:34Z** |
| Version tested | **v1.6.1** (== latest release on snapshot day; no drift) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| katana binary | **v1.6.1** at `~/go/bin/katana` |
| Go toolchain | **go1.26.5 darwin/arm64** |
| Headless browser | Chromium build **1228** (`chromium_headless_shell-1228`; katana `-headless` auto-detected a browser) |
| Python (harness) | **3.14.2** (clean `uv` venv; harnesses import stdlib only) |
| Platform | **macOS 26.5.2 arm64** |
| Test date | **2026-07-23** |

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `127.0.0.1`, random free port; three
endpoint classes + scope/depth/known-files/robustness routes). Ground truth:
`artifacts/raw/ground_truth.json`.

```bash
# 0) create venv (harnesses are stdlib-only; no third-party deps)
uv venv .venv --python 3.14

# 1) discovery coverage matrix (4 modes + known-files); ~3-4 min incl. 2 headless runs
.venv/bin/python tests/run_discovery.py
#    modes: standard | standard -jc | -headless | -headless -jc, all with -silent -nc -d 4
#    known-files sub-run: -kf all -d 3

# 2) resume: full baseline, then interrupt (SIGINT @3s) + -resume; ~40s
.venv/bin/python tests/run_resume.py
#    interrupted crawl: -silent -nc -duc -d 4 ; resume: -resume <file> -silent -nc -duc
#    resume file discovered by diffing ~/.config/katana/resume-*.cfg

# 3) scope: primary(127.0.0.1) + secondary(localhost); ~15s
.venv/bin/python tests/run_scope.py
#    configs: default | -fs fqdn | -cs localhost | -fs '(127.0.0.1|localhost)' ; all -silent -nc -duc -d 3

# 4) cost: standard vs headless, 3 isolated runs each — RUN ALONE (timing-sensitive); ~4 min
.venv/bin/python tests/run_cost.py
#    -silent -nc -duc -d 4 ; reports p50 + min/max ; overlap => tie
```

## Reproducibility notes (honest)

- **Fixture hardening**: the `ThreadingHTTPServer` subclass sets
  `request_queue_size=256`, `allow_reuse_address=True`, `daemon_threads=True` so
  katana's `-c 10` connection burst is accepted reliably (the stdlib default
  backlog of 5 drops connects under the burst → dial timeouts). This changes
  connection reliability only, not discovery results.
- **`-duc`** is passed on the resume/scope/cost runs to drop katana's startup
  GitHub version-check (a per-run network round-trip); applied identically to both
  cost modes, no `-timeout` tuning. `discovery-summary.json` predates this, so its
  `standard` elapsed (14.53s) includes the version-check vs the cost test's 13.08s.
- **known-files sub-run** uses a *separate* katana HTTP client that intermittently
  stalls at the dial stage on this host (the main crawl client is unaffected). The
  clean recall measurement (0.0, with robots/sitemap requested) in
  `discovery-summary.json` was captured while that client connected; the recall
  value is dial-timeout-independent.
- **Cleanup**: test-generated `~/.config/katana/resume-*.cfg` files were removed
  after the runs (katana also auto-cleans resume files older than 10 days).
