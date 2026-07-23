# katana — evidence pack

Independent, reproducible tests for **katana** (ProjectDiscovery), an
endpoint-discovery crawler for recon/automation pipelines. Part of the Thunderbit
open-source scraping-tool benchmark. Every number in `research-materials.md` traces
to a script here and a JSON artifact under `artifacts/raw/`.

Tested version (as-of 2026-07-23): katana **v1.6.1** (Go 1.26.5), Chromium build
1228 for `-headless`, Python 3.14, macOS arm64.

## Headline

On controlled ground truth with three endpoint classes, **no single katana command
covers both JavaScript-file-literal endpoints and runtime-DOM-only endpoints**:
`-jc` finds JS-file literals in *standard* mode only (headless returns 0/2 even with
`-jc`), while runtime-DOM endpoints are found *only* by `-headless`
(`headless_jc_covers_both: false`). Full coverage needs the union of a `standard
-jc` run and a `-headless` run — and headless costs ~5.1× the wall time.

Secondary, source-grounded findings: `-resume` reaches the same endpoint set but
re-crawls completed pages (checkpoint granularity is per input *seed*, not per URL);
known-files requests robots.txt/sitemap.xml but drops the sitemap's `<loc>`
endpoints on IP-address targets (recall 0.0); scope holds by default and is widened
with a custom `-fs` regex, not `-cs`.

## Reproduce

```bash
uv venv .venv --python 3.14          # harnesses are stdlib-only; no pip deps

# 1) discovery coverage matrix (4 modes + known-files), ~3-4 min
.venv/bin/python tests/run_discovery.py

# 2) resume: baseline, SIGINT interrupt, -resume recovery, ~40s
.venv/bin/python tests/run_resume.py

# 3) scope discipline (primary 127.0.0.1 + secondary localhost), ~15s
.venv/bin/python tests/run_scope.py

# 4) mode cost (standard vs headless, 3 runs each) — RUN ALONE, timing-sensitive, ~4 min
.venv/bin/python tests/run_cost.py
```

Requires `katana` at `~/go/bin/katana` (v1.6.1) and, for `run_cost`/headless
coverage, a Chromium katana can launch. Outputs land in `artifacts/raw/*.json`
(per-run detail + stdout under `artifacts/logs/`). The local fixture
(`tests/fixture_server.py`) binds `127.0.0.1` on a random port and defines every
discoverable path, so recall is measured against a known set — never guessed.

## What the pack establishes

- **Coverage split (main headline):** class A (HTML) found by all modes; class B
  (JS-literal in `app.js`) found only by `standard -jc`; class C (runtime-DOM-only)
  found only by `-headless`; `-headless -jc` still misses B.
- **Cost:** standard p50 13.08s vs headless p50 66.82s — ~5.1×, non-overlapping.
- **Resume:** checkpoint at `~/.config/katana/resume-<xid>.cfg` stores only in-flight
  seed URLs; resume re-fetched all 11 baseline paths (10 already completed) —
  per-seed, not per-URL, recovery.
- **Scope:** out-of-scope host never fetched under default / `-fs fqdn` / `-cs
  localhost`; a custom `-fs '(127.0.0.1|localhost)'` fetches it.
- **Known-files:** `-kf all -d 3` requests robots/sitemap but fetches 0/2 sitemap
  `<loc>` endpoints on an IP target — root-caused to an empty `RootHostname` +
  IP-host scope check in katana source (v1.6.1).

## Pack contents

- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check.
- `scorecard.md` — provisional dimension scores (77/100), evidence-anchored.
- `metadata-snapshot.md` — versions, exact commands, reproducibility caveats.
- `tests/` — `fixture_server.py` + four runners.
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout.

Evidence phase only: no article, no publishing. `validation.md` (independent audit)
is produced separately and is not part of this worker's deliverable.
