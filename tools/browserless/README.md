# browserless — evidence pack

Independent, reproducible tests for **browserless** (`browserless/browserless`, Docker
image `ghcr.io/browserless/chromium`), a **containerized headless-browser service** that
pools/queues real Chromium sessions and exposes them as REST rendering endpoints
(`/content`, `/scrape`, `/screenshot`, `/pdf`, …) plus a CDP/WebSocket surface. Part of
the Thunderbit open-source scraping-tool benchmark. This pack scores the **deployment
and lifecycle overhead of running the service** — *not* the browser-library feature set
(that is the sibling `chromedp/`, `rod/`, `selenium/`, `playwright-mcp/` packs). Every
number in `research-materials.md` traces to a script in `tests/` and a JSON artifact
under `artifacts/raw/`.

Tested version (as-of 2026-07-24): **browserless v2.55.0**
(`ghcr.io/browserless/chromium:latest`, digest `sha256:9e48bf8d…ab033f4`), Chrome
149.0.7827.0, Node v24.18.0, under **colima 0.10.3 + Docker 29.2.1** on macOS arm64.
Harness is **pure Python 3 stdlib** (no venv, no third-party deps).

## Headline

**One `docker run` gets a ready service in ~0.78 s; the first cold render is ~0.32 s,
warming to ~0.15 s.** Browserless does not launch browsers faster than the in-process
CDP libraries (sibling cold launches: chromedp 102 ms / rod 119 ms / selenium 168 ms) —
it **amortizes** launch behind a long-lived pooled service and trades automation *code*
for *deployment* (a 4.3 GB image, a container, a token, an admission ceiling).

**The concurrency ceiling is exactly `CONCURRENT + QUEUED`, and it is enforced.** Firing
`C+Q+4` simultaneous session-holding requests at three configs, the client always gets
`C+Q` × 200 and 4 × **HTTP 429**, and the server's own `/pressure`
(`running`/`queued`/`recentlyRejected`) agrees exactly — the ceiling moves 4 → 8 → 10
with config. A per-session **`TIMEOUT` is enforced at the boundary**: an over-budget
session is killed at **5.007 s** (budget 5.000) with **HTTP 408**, not left to hang.

**Lifecycle is clean over a moderate soak.** 30 sequential sessions leave **0 chrome
processes and 0 zombies** inside the container (detector calibrated: it read 11 chrome
procs mid-session, so the post-run zero is real), and container RSS **plateaus** at
~303 MiB (294 → 303, logarithmic — not a linear per-session leak). The image ships
`dumb-init` as PID 1, the documented zombie reaper.

**The REST endpoints render on shared ground truth with zero client code.** `/content`
and `/scrape` surface a **runtime-injected** DOM marker (assembled from JS fragments, no
literal in served bytes) — the same content class **katana's static crawl misses**;
`/screenshot` returns a valid PNG, `/pdf` a valid PDF, and all four endpoints are
**token-gated** (401 without a token; v2 requires `TOKEN` by default).

**One migration trap:** the v1 tuning flag `PREBOOT` was **removed in v2.0**, but the v2
container **accepts `-e PREBOOT=true` with no error or warning and ignores it** (no idle
browser, absent from `/config`) — a v1 `PREBOOT` config copy-pasted onto v2 is a silent
no-op. (`KEEP_ALIVE` was also removed per the changelog, but — unlike `PREBOOT` — it logs
a `deprecated and ignored` warning; it is not separately measured here.)

## Reproduce

```bash
docker pull ghcr.io/browserless/chromium:latest   # 4.3 GB, one-time

# Each runner starts its OWN container on port 3000 (with a local self-assigned TOKEN),
# drives it, and removes it. Run ONE AT A TIME (they share port 3000). Pure stdlib.
python3 tests/run_startup.py       # H1 docker-run->ready / cold / warm / PREBOOT arm (3 boots)
python3 tests/run_concurrency.py   # H2 ceiling = CONCURRENT+QUEUED -> 429 (client + /pressure) — RUN ALONE
python3 tests/run_endpoints.py     # H3 /content /scrape /screenshot /pdf fidelity + token gate
python3 tests/run_lifecycle.py     # H4 30-session leak/zombie/RSS + H5 TIMEOUT kill
```

Artifacts land in `artifacts/raw/*.json`, redacted (`$HOME`→`~`,
`$TMPDIR`/`/var/folders`→`<TMP>`, local `TOKEN`→`<TOKEN>`).

## What each file is

| File | Purpose |
|---|---|
| `pretest-information-gain.md` | pre-test gate: SERP/doc consensus, the gap, 5 hypotheses, matrix, PROCEED verdict |
| `research-materials.md` | the evidence: FINDING-01…06 with confidence + novelty tags, cross-series position, Gaps |
| `scorecard.md` | provisional pack-local scorecard (92/100), deployment/lifecycle-weighted |
| `metadata-snapshot.md` | image tag+digest, versions, exact commands, honest reproducibility notes |
| `tests/fixture_server.py` | local fixture (binds `0.0.0.0`); `/render` runtime-injected marker + `/slow?ms=N` session-holder |
| `tests/bl_common.py` | container lifecycle + REST driver + `docker stats` mem + `/proc` proc/zombie scan + redaction |
| `tests/run_*.py` | one runner per hypothesis group |
| `artifacts/raw/*.json` | measured results (redacted) |

## Scope / boundaries

- Evidence phase only; no article, no publishing.
- All tests on a **local fixture** + a **local container**. No third-party/production
  host, no anti-bot, no auth bypass, no rate abuse. `/unblock` (anti-detection) is out of
  scope on brand grounds and untested.
- The `TOKEN` is a **local, self-assigned container password**, not an external
  credential; it is redacted from every artifact.
- Numbers are scoped to the tested image tag/digest, browserless v2.55.0, colima-VM host
  (macOS arm64), and fetch date; container startup/memory differ on bare-metal Linux.
- Novelty honesty: one-command deploy, the `CONCURRENT+QUEUED→429` contract, TOKEN,
  the REST endpoints, PREBOOT's removal, and the observability endpoints are all
  **DOCUMENTED**; zombie-process risk is a **KNOWN-ISSUE** (#20/#228). This pack's value
  is the **quantification and same-fixture proof** — decomposed startup, the moving
  ceiling on dual truth, the located TIMEOUT boundary, the calibrated leak trajectory,
  and the runtime-injected recall alongside katana's static miss.
