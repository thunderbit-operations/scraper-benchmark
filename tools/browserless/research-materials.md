# Browserless — research materials (evidence)

Scope: the **deployment and lifecycle overhead of the containerized headless-browser
SERVICE** `ghcr.io/browserless/chromium:latest` (**browserless v2.55.0**, Chrome
149.0.7827.0), run under **colima / Docker on macOS 26.5.2 arm64**, 2026-07-24. This
pack does **not** re-score browser-library features (see the same-benchmark
`chromedp/`, `rod/`, `selenium/`, `playwright-mcp/`, `katana/` packs). Every number
below traces to a script in `tests/` and a JSON artifact under `artifacts/raw/`.
Findings are numbered and carry a confidence label (triple-run / single-observation /
hypothesis) and a novelty tag (DOCUMENTED / KNOWN-ISSUE / EXCLUSIVE). No self-evaluative
adjectives; the reader weighs the evidence.

Container reaches the local host fixture via `host.docker.internal` (colima maps it
with `--add-host host.docker.internal:host-gateway`). The container is authenticated
with a **local, self-assigned `TOKEN`** (not an external credential); it is redacted to
`<TOKEN>` in every artifact.

---

## FINDING-01 — The deployment tax, decomposed (container-ready 0.78 s, cold render 0.32 s, warm 0.15 s)

`run_startup.py`, 3 fresh `docker run` boots (`artifacts/raw/startup.json`). Medians
(min–max):

| Stage | median | min–max | what it is |
|---|---:|---|---|
| `docker run` → `/pressure` 200 (service ready) | **0.776 s** | 0.704–0.869 | container process up + node service listening |
| ready → first **cold** `/content` render | **0.318 s** | 0.278–0.412 | first per-session browser launch + navigate + return HTML |
| warm steady-state `/content` (5 calls/boot) | **0.150 s** | 0.147–0.154 | subsequent renders, browser cost amortized |

- **Phenomenon:** the one-time deployment cost a browser-*library* benchmark never pays
  is ~0.78 s to a ready service, then ~0.32 s for the first render, settling to ~0.15 s.
  The cold→warm gap (~0.17 s) is the per-session browser-launch cost, consistent in
  magnitude with the sibling in-process cold-launch numbers (chromedp 102 ms / rod
  119 ms / selenium headless-shell 168 ms) — i.e. Browserless does not launch browsers
  faster; it **amortizes** launch behind a long-lived pooled service and adds an HTTP
  round-trip.
- **Mechanism:** cold vs warm attribution is a **hypothesis** at the process level (not a
  CDP-trace attribution); the magnitude match to sibling launch costs supports it.
- **Scope:** macOS arm64 / colima VM, warm image cache; container-boot time is
  VM/host-dependent and not portable to bare-metal Linux numbers.
- Confidence: **triple-run** (n=3 boots, median+range; n<1000 so no percentile claim).
- Novelty: existence of a startup cost is **DOCUMENTED**; the **decomposed three-stage
  numbers are EXCLUSIVE** (no SERP source separates container-ready from cold render
  from warm).

## FINDING-02 — `PREBOOT` is inert on v2: silently accepted, no idle browser, absent from `/config`

`run_startup.py` PREBOOT arm + direct idle-process probe.

- With `-e PREBOOT=true`, the `startup.json` PREBOOT arm is within noise of the default
  arm (ready 0.716 vs 0.776 s; cold 0.314 vs 0.318 s; warm 0.163 vs 0.150 s — all inside
  the default min–max band).
- Direct check: a `PREBOOT=true` container at idle has **0 chrome processes** (identical
  to `PREBOOT` unset); `/config` exposes **no `preboot` key** (keys are
  `concurrent,queued,timeout,token,maxCPU,maxMemory,retries,…`).
- **Mechanism (documented root cause, Part 4.15 check):** Browserless **2.0.0 removed
  PREBOOT and KEEP_ALIVE** ([2.0 changelog](https://github.com/browserless/browserless/blob/main/CHANGELOG.md):
  "dropped since they're confusing, improve little, and cause a lot of bugs"). The v2
  container accepts `-e PREBOOT=true` without error or warning and ignores it — so a v1
  `PREBOOT` config copy-pasted onto v2 (a common migration) is a **silent no-op**.
  *Scope:* only `PREBOOT` was exercised by the harness. `KEEP_ALIVE`, also removed, instead
  logs a `deprecated and ignored` warning — so this silent-no-op result is specific to
  `PREBOOT`, not a general claim about both flags.
- Confidence: **triple-run** for the latency non-effect + **single-observation** for the
  idle-process / `/config` probe.
- Novelty: the removal is **DOCUMENTED** (changelog); the **silent-accept-and-ignore
  behavior + `/config` absence + unchanged cold latency is EXCLUSIVE** (the confirmation
  that the widely-copied v1 flag does nothing on v2, with no operator-facing signal).

## FINDING-03 — Concurrency ceiling = CONCURRENT + QUEUED, proven on client + server truth, and it moves with config

`run_concurrency.py` (`artifacts/raw/concurrency.json`). Each request navigates to
`/slow?ms=5000` (server sleeps 5 s → occupies one session ~5 s); fire C+Q+4 at once.

| (CONCURRENT, QUEUED) | fired | client 200 | client 429 | server `/pressure` peak (running / queued / recentlyRejected) | ceiling == C+Q |
|---|---:|---:|---:|---|:--:|
| (2, 2) | 8 | **4** | **4** | 2 / 2 / 4 | ✅ |
| (3, 5) | 12 | **8** | **4** | 3 / 5 / 4 | ✅ |
| (5, 5) | 14 | **10** | **4** | 5 / 5 / 4 | ✅ |

- **Phenomenon:** exactly `CONCURRENT` requests run, up to `QUEUED` wait, and every
  request beyond the `C+Q` ceiling is rejected with **HTTP 429** — the client 200-count
  equals `C+Q` in all three configs, the 429-count equals the overshoot (4) in all
  three, and the server-side `/pressure` peak (`running`==CONCURRENT, `queued`==QUEUED,
  `recentlyRejected`==overshoot) agrees with the client independently. The ceiling
  **moves** with configuration (4 → 8 → 10), so it is the configured sum, not a constant.
- **Mechanism:** direct from the documented admission contract; `/pressure` is the
  server's own accounting, so this is measurement, not attribution.
- **Scope:** admission-control behavior is version-level (v2.55) and config-driven, not
  platform-dependent.
- Confidence: **triple-config, dual-truth** (client status + server `/pressure`).
- Novelty: the `C+Q → 429` contract is **DOCUMENTED**; the **simultaneous client+server
  proof and the moving-ceiling demonstration are EXCLUSIVE** (no source shows both axes
  agreeing across configs).

## FINDING-04 — REST endpoints render on shared ground truth: `/content`+`/scrape` catch runtime-injected DOM; PNG/PDF valid; all token-gated

`run_endpoints.py` (`artifacts/raw/endpoints.json`), against `/render` whose marker
`Runtime Injected Marker 88` is assembled from JS fragments at load (no contiguous
literal in any served byte).

| Endpoint | result | bytes |
|---|---|---:|
| `/content` | runtime-injected marker **present** + both static markers present | 811 |
| `/scrape` (`#scrape-me`, a runtime-injected node) | returned value == `SCRAPE_TARGET_VALUE_CC` | — |
| `/screenshot` | valid **PNG** (magic `89 50 4E 47`) | 18,621 |
| `/pdf` | valid **PDF** (magic `%PDF-`) | 40,974 |
| token gate | `/content`,`/scrape`,`/screenshot`,`/pdf` all **401 without token** | — |

- **Phenomenon:** the service's real Chromium render surfaces JS-injected content with
  **zero client-side browser code** — a single POST. This is the **same content class
  that katana's static crawl misses** (`tools/katana/`) and that playwright-mcp / chromedp
  / rod / selenium catch (the latter three only after an explicit wait). Browserless is
  the sixth same-fixture data point on that class, and the one requiring no automation
  code on the caller.
- **Scope:** fidelity claim is for this fixture's content classes; `/unblock`
  (anti-detection) is deliberately out of scope on brand grounds and untested.
- Confidence: **single-observation** per endpoint (deterministic ground-truth markers,
  presence/absence — not a distribution).
- Novelty: the endpoints and their purpose are **DOCUMENTED**; the **same-fixture
  runtime-injected recall placed alongside the static-crawler miss is EXCLUSIVE**
  (net-new cross-series data point), as is the exact byte size of a PNG/PDF for this page.

## FINDING-05 — Clean per-session recycling: 30 sequential sessions leave 0 chrome / 0 zombies; container RSS plateaus (~9 MB, not linear)

`run_lifecycle.py` H4 (`artifacts/raw/lifecycle.json`), CONCURRENT=3, 30 sequential
`/content`.

- **Detector calibration first (Part 6.3):** while a session is in-flight the `/proc`
  enumerator reads **11 chrome-family processes** — so the detector demonstrably *sees*
  chrome; its post-run zero is therefore meaningful, not blindness. (One session spawns
  ~11 chrome processes: browser + zygote + gpu + renderers + utilities.)
- **Post-run:** **0 chrome processes, 0 zombies** inside the container; the only
  surviving procs are `dumb-init` (PID 1), `node` (MainThread), `Xvfb`, `start.sh`, `sh`.
  `/sessions` reads **0** at idle.
- **Container memory** (`docker stats`, operator-visible): baseline **294 MiB** →
  after 30 sessions **303 MiB**, with the trajectory 294→300→301→302→302→303→303 —
  **plateauing (logarithmic), not linear**. Net growth ~9.5 MB across 30 sessions.
- **Phenomenon + mechanism:** the per-request-browser model recycles cleanly; the image
  ships **`dumb-init` as PID 1** (the documented zombie-reaper), and no orphaned Chrome
  or `<defunct>` process survives a session. The ~9 MB is node steady-state warmup that
  flattens, not a per-session leak — over 30 sessions a linear per-session leak would not
  plateau.
- **Scope:** 30 sessions is a moderate soak, not a multi-hour endurance run; the plateau
  claim is scoped to this window (see Gaps).
- Confidence: **single soak run**, but with a **calibrated** detector and a memory
  *trajectory* (7 samples) rather than a single before/after.
- Novelty: zombie-process risk on Docker is a **KNOWN-ISSUE** (#20/#228; dumb-init is the
  documented mitigation); the **calibrated 30-session RSS plateau + explicit 0-zombie /
  0-chrome post-run count is EXCLUSIVE quantification** (the prose says "can leak"; this
  measures that on v2 it does not, over this window).

## FINDING-06 — Per-session `TIMEOUT` is enforced at the boundary: over-timeout session killed at 5.007 s with HTTP 408

`run_lifecycle.py` H5, `TIMEOUT=5000` ms.

| Case | page hold | status | elapsed |
|---|---:|---:|---:|
| under timeout | 2000 ms | **200** | 2.406 s |
| over timeout | 15000 ms | **408** | **5.007 s** |

- **Phenomenon:** a session whose work exceeds `TIMEOUT` is force-terminated by
  Browserless at **~TIMEOUT** (5.007 s vs the 5.000 s budget — 7 ms over) and the caller
  gets **HTTP 408 Request Timeout**, not a hang; an under-budget session returns 200.
  This is the per-session lifecycle recycler that prevents a stuck page from occupying a
  concurrency slot indefinitely (couples with FINDING-03's ceiling).
- **Mechanism:** direct measurement of the documented `TIMEOUT` knob; the boundary
  precision (7 ms) indicates a server-side timer, not client-side.
- Confidence: **single-observation** (deterministic boundary; the 5.007 s is the measured
  kill time).
- Novelty: `TIMEOUT` is **DOCUMENTED**; the **located kill boundary (5.007 s) and the
  specific 408 response code are EXCLUSIVE** (docs give the knob, not the demonstrated
  boundary + status).

---

## Cross-series position (same benchmark, shared fixture family)

- **Runtime-injected content class** (the one comparable axis to the library packs):
  katana static crawl **misses** it → playwright-mcp a11y snapshot **catches** it →
  chromedp / rod / selenium **catch it with an explicit wait** → **Browserless
  `/content` catches it with zero client-side code** (a single authenticated POST).
  Browserless trades *code* for *deployment*: no automation code, but a 4.3 GB image, a
  container to run, a token to manage, and a `C+Q` admission ceiling.
- **Cold-start comparison is deliberately not a ranking:** the sibling packs measure
  in-process browser launch (102–168 ms); Browserless's 0.32 s cold render includes
  container-mediated HTTP + navigation + HTML return and is not the same quantity — it is
  reported as the *deployment* cost, not a faster/slower verdict.

## Gaps / not tested (explicit)

- **Endurance:** 30 sequential sessions is a moderate soak; a multi-hour / thousands-of-
  sessions run (where the KNOWN-ISSUE EventEmitter warning #20/#228 and slow leaks would
  surface) is **not** done. The plateau claim is scoped to the 30-session window.
- **CDP/WebSocket path** (Puppeteer/Playwright `connect`) is not measured; only the REST
  surface.
- **`/function`, `/unblock`, `/download`, `/performance`** endpoints not exercised
  (`/unblock` intentionally excluded on brand grounds).
- **PREBOOT effectiveness on v1** is not measured (v1 is out of scope; v2 removed it).
- **Bare-metal Linux** startup/memory numbers differ from these colima-VM numbers.
- **`/metrics` JSON** requires `METRICS_JSON_PATH`; only `/pressure`, `/config`,
  `/sessions` observability were used.
