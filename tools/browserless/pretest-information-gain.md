# Browserless — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable gap exists; see "Information-gain verdict").

Broad keyword: **`Browserless`** (`browserless/browserless`, Docker image
`ghcr.io/browserless/chromium`, v2 line).
Article boundary: Browserless is a **containerized headless-browser SERVICE** — a
long-lived Docker container that pools/queues real Chromium sessions and exposes them
as (a) REST rendering endpoints (`/content`, `/scrape`, `/screenshot`, `/pdf`,
`/function`, `/unblock`) and (b) a CDP/WebSocket surface for Puppeteer/Playwright.
This pack judges the **deployment and lifecycle overhead of running that service** —
container startup cost, concurrent-session ceiling behavior, per-session lifecycle
recycling, resource/leak behavior, and the built-in observability endpoints. It
deliberately does **not** re-run the browser-library feature comparison already
covered by the same-benchmark `chromedp/`, `rod/`, `selenium/`, `playwright-mcp/`
packs (those score CDP libraries and one agent snapshot surface). No overlap: this
pack never scores a driver API or an a11y snapshot; it scores the *container as an
operational unit*.

## SERP scan (first ~20 results, official docs, README, issue tracker)

### What the results repeat (consensus, mostly unmeasured)

- **One-command Docker deploy.** `docker run -p 3000:3000 ghcr.io/browserless/chromium`;
  the container is the product. Every guide repeats the same run line and the
  `--shm-size=2g` caveat (Docker's 64 MB `/dev/shm` default crashes Chrome under load).
- **Concurrency is a hard ceiling, not elastic.** `CONCURRENT` (default 10) running +
  `QUEUED` (default 10) pending; "total allowed = CONCURRENT + QUEUED, beyond that →
  HTTP 429." Repeated in docs and blogs but never *shown* on both client and server
  truth simultaneously.
- **TOKEN auth.** v2 requires a `TOKEN`; every REST call takes `?token=`. Framed as
  "without this anyone on your network can use your instance."
- **REST rendering endpoints** `/content`, `/scrape`, `/screenshot`, `/pdf`, `/unblock`,
  `/function` — "receive a URL, launch a browser, run the action, return the result,
  terminate the session." Asserted; never measured against controlled ground truth
  (in particular whether `/content` surfaces runtime-injected DOM).
- **PREBOOT keeps a browser warm** for faster first response, "~100–200 MB RAM at
  startup" — a number quoted, never measured.
- **Observability**: `/pressure` (running/queued/cpu/mem), `/sessions`, `/config`,
  `/metrics`. Documented; nobody demonstrates `/pressure` tracking a real saturation.
- **Known pitfalls in prose**: EventEmitter "MaxListenersExceededWarning" after ~10
  connections (#20/#228); Docker zombie Chrome processes if not reaped (the image
  ships `dumb-init` as PID 1 for exactly this); unclosed pages leak renderer memory.

### What is NOT measured anywhere (the gap)

1. **Container startup + first-usable-session latency is never decomposed.** Guides say
   "just `docker run`"; nobody reports `docker run` → service-ready, then service-ready
   → first *cold* browser render, then warm steady-state — nor whether `PREBOOT` cuts
   the first-request cost and by how much. The one-time deployment tax a
   browser-library benchmark never pays is unquantified.
2. **The `CONCURRENT + QUEUED → 429` contract is asserted, never proven on both axes.**
   No source overshoots a known `(CONCURRENT, QUEUED)` and reports the exact
   200/queued/429 split from the CLIENT while simultaneously reading `running/queued/
   recentlyRejected` from the SERVER (`/pressure`) — nor shows the ceiling MOVING with
   config.
3. **Per-session TIMEOUT recycling is documented as a number, not demonstrated.** Does a
   session exceeding `TIMEOUT` actually get force-killed at ~TIMEOUT (non-200), and is
   the boundary where the docs put it?
4. **Resource/leak behavior across many sessions is anecdotal.** "Zombie processes,"
   "memory leaks," "dumb-init helps" are prose. Nobody runs K sequential sessions and
   reports container-memory trajectory + a post-run zombie/chrome-process count with a
   CALIBRATED detector (proven able to see chrome mid-flight before trusting a post-run
   zero).
5. **`/content` fidelity vs a static crawler is never placed on shared ground truth.**
   Whether the service's real render catches JS-injected content that a static fetch
   (katana standard mode) misses is obvious in principle but never shown same-fixture.

### Source evidence

- Official: [browserless/browserless](https://github.com/browserless/browserless),
  [Docker config reference](https://docs.browserless.io/enterprise/docker/config),
  [Production best-practices](https://docs.browserless.io/enterprise/docker/best-practices),
  [Open-source Docker deploy](https://docs.browserless.io/enterprise/open-source),
  [OpenAPI reference](https://docs.browserless.io/open-api).
- Upstream issues to cite at execution (already-public behavior):
  [#20 EventEmitter leak warning](https://github.com/joelgriffith/browserless/issues/20),
  [#228 SIGHUP listeners](https://github.com/browserless/chrome/issues/228),
  [#441 running out of memory](https://github.com/browserless/chrome/issues/441),
  [#1957 default launch args & token](https://github.com/browserless/browserless/issues/1957),
  [#4946 v2 image timeout on Pi5](https://github.com/browserless/browserless/issues/4946).
- Representative SERP:
  [morphllm Browserless Docker guide](https://www.morphllm.com/browserless-docker),
  [morphllm Browserless API guide](https://www.morphllm.com/browserless-api),
  [elest.io self-host guide](https://blog.elest.io/give-your-ai-agent-a-browser-self-host-browserless/).

## Testable information-gain hypotheses

- **H1 (deployment tax, decomposed):** Measure `docker run` → `/pressure`-ready
  (container boot), → first *cold* `/content` render, → warm steady-state, across ≥3
  fresh boots (variance). Then measure `PREBOOT=true`'s effect on the first-request
  cost. Numbers no SERP source gives.
- **H2 (adversarial, the ceiling):** Overshoot a known `(CONCURRENT, QUEUED)` with
  simultaneous session-holding requests and prove `200 == CONCURRENT+QUEUED`, excess
  `== 429`, on CLIENT status codes AND SERVER `/pressure` (`running`/`queued`/
  `recentlyRejected`) at once — and show the ceiling moves across configs.
- **H3 (endpoint fidelity, shared ground truth):** `/content` + `/scrape` surface a
  RUNTIME-INJECTED marker (assembled from fragments; no literal in served bytes — the
  class a static crawler misses); `/screenshot` returns valid PNG, `/pdf` valid PDF;
  every endpoint is token-gated. Cross-series contrast with katana (static, misses) /
  playwright-mcp (catches).
- **H4 (resource lifecycle):** K sequential sessions → container-memory trajectory
  (`docker stats`) + post-run chrome-process/ZOMBIE count via `/proc`, with the
  detector first calibrated (must see chrome mid-flight). Does the service recycle
  cleanly (dumb-init reaper) or leak?
- **H5 (adversarial, TIMEOUT recycling):** a session whose page-hold exceeds `TIMEOUT`
  is force-killed at ~TIMEOUT (non-200); one under `TIMEOUT` succeeds. Locate the kill
  boundary.

## Test matrix (tied to hypotheses)

| # | Test | Config / route | Measures | H |
|---|---|---|---|---|
| 1-3 | container boot | fresh `docker run` ×3 | `docker run`→/pressure-ready (s) | H1 |
| 4-6 | first cold render | ×3 boots | ready→first /content (s) | H1 |
| 7-9 | warm steady-state | 5 warm calls ×3 boots | warm /content median (s) | H1 |
| 10-12 | PREBOOT effect | `PREBOOT=true` ×3 boots | cold first-call delta | H1 |
| 13 | ceiling @ (2,2) | 8 concurrent /slow | 200/429 split + /pressure peak | H2 |
| 14 | ceiling @ (3,5) | 12 concurrent | 200==C+Q, 429==over | H2 |
| 15 | ceiling @ (5,5) | 14 concurrent | server running/queued/rejected | H2 |
| 16 | /content fidelity | /render (runtime-injected) | marker recall | H3 |
| 17 | /scrape selector | `#scrape-me` runtime node | returned value == GT | H3 |
| 18 | /screenshot,/pdf | /render | PNG/PDF magic + size | H3 |
| 19 | token gate | 4 endpoints, no token | 401/403 | H3 |
| 20 | detector calibration | procs during live session | chrome_procs>0 | H4 |
| 21 | 30 sequential sessions | /render ×30 | mem trajectory | H4 |
| 22 | post-run leak scan | /proc comm+state | chrome/zombie count | H4 |
| 23 | TIMEOUT under | HOLD 2s < TIMEOUT 5s | 200 | H5 |
| 24 | TIMEOUT over | HOLD 15s > TIMEOUT 5s | non-200 near 5s | H5 |

Fixture (local, host `0.0.0.0`, reached from the container via
`host.docker.internal` — colima maps it with `--add-host host-gateway`): a `/render`
page whose visible marker text is INJECTED BY JS at load (assembled from fragments so
no contiguous literal exists in any served byte) + a `/slow?ms=N` route that sleeps N
ms server-side to occupy a session for a controlled duration (deterministic,
tool-independent session occupancy for the concurrency probe). A server-side hit
counter records what the browser actually fetched. Recall is computed against a
pre-registered ground-truth marker set — never guessed. Container memory uses the
operator-visible `docker stats`; process/zombie truth comes from `/proc` inside the
container.

## Harness design (Docker + REST driver, pure stdlib)

`tests/bl_common.py` manages the container lifecycle (`docker run` with explicit
`CONCURRENT/QUEUED/TIMEOUT/PREBOOT/TOKEN`, `/pressure`-poll ready, stop), drives the
REST endpoints (`urllib`, token-authenticated), and reads tool-independent truth
(`docker stats` memory, `/proc` process/zombie enumeration). Four runners map to the
hypotheses (`run_startup.py`, `run_concurrency.py`, `run_endpoints.py`,
`run_lifecycle.py`). No third-party Python deps (screenshot/pdf validated by magic
bytes). Every result field is computed from measured output; nothing hardcoded.

## Information-gain verdict: PROCEED

Not parked. The consensus is dense (one-command deploy, CONCURRENT+QUEUED→429, TOKEN,
REST endpoints, PREBOOT, /pressure) but **entirely qualitative on the five questions
that decide the operational cost of running the service**: (1) the decomposed startup
tax and PREBOOT's payoff, (2) the ceiling proven on client+server truth and shown to
move, (3) TIMEOUT recycling demonstrated with a located boundary, (4) resource/leak
behavior across many sessions with a calibrated detector, (5) `/content` fidelity on
shared ground truth. Each is measurable on a local fixture with no external
credentials (a local self-assigned TOKEN only) and yields numbers no current SERP
source provides. Cross-series bonus: the runtime-injected `/render` marker is the
*same* content class katana's static crawl misses — a container render catching it
with zero client-side browser code is a concrete same-fixture contrast.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on the **local fixture** + the local container. No third-party/production
  host, no anti-bot, no auth bypass, no rate abuse. `/unblock` (anti-detection) is out
  of scope on brand grounds and not exercised.
- **The `TOKEN` is a local, self-assigned container password**, not an external
  credential; it is recorded in metadata as a value we set and **redacted out of every
  artifact** (`redact()` maps it to `<TOKEN>`, plus `$HOME`→`~`,
  `$TMPDIR`/`/var/folders`→`<TMP>`).
- Numbers are scoped to the tested image tag/digest, host (macOS arm64 / colima), and
  fetch date; container startup/latency are platform- and VM-dependent.
- Novelty honesty: one-command deploy, the CONCURRENT+QUEUED→429 contract, TOKEN
  requirement, REST endpoints, PREBOOT, and the observability endpoints are all
  **DOCUMENTED** — this pack's value is the *quantification and same-fixture proof*, not
  their existence. The EventEmitter/zombie concerns are **KNOWN-ISSUE** (#20/#228).
  Only genuinely un-recorded measurements (decomposed startup, located TIMEOUT
  boundary, calibrated leak trajectory, moving ceiling on dual truth) get an EXCLUSIVE
  tag.
