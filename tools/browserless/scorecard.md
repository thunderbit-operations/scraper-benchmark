# browserless — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking. Weights
are pack-local and pre-registered here; scores are evidence-anchored, each citing a
run. Scope: the **deployment + lifecycle overhead** of the containerized service
`ghcr.io/browserless/chromium` **v2.55.0** under colima/Docker on macOS arm64 —
**not** the browser-library feature set (see `tools/chromedp|rod|selenium|playwright-mcp/`).
Dimensions mirror the sibling packs where they apply, but weight **deployment /
lifecycle** over feature breadth per this pack's focus.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Deploy & first-usable-session | 12 | 10 | one `docker run`; service-ready 0.78 s median, cold render 0.32 s, warm 0.15 s (`startup.json`) |
| Startup-tuning honesty (PREBOOT) | 6 | 4 | v1 `PREBOOT` removed in v2 but **silently accepted, no error/warning**; inert, absent from `/config` (KEEP_ALIVE also removed but logs a warning — not measured here) |
| Concurrency-ceiling behavior | 16 | 16 | `200==CONCURRENT+QUEUED`, excess `==429`, ceiling moves 4→8→10; client+server truth agree (`concurrency.json`) |
| Queue / admission observability | 8 | 8 | `/pressure` peak `running`/`queued`/`recentlyRejected` matched config exactly in all 3 configs |
| REST endpoint fidelity | 12 | 12 | `/content`+`/scrape` catch runtime-injected DOM; `/screenshot` valid PNG, `/pdf` valid PDF (`endpoints.json`) |
| Auth gate | 6 | 6 | all 4 REST endpoints 401 without token; token required by default on v2 |
| Session recycling / leak | 14 | 13 | 30 sessions → 0 chrome / 0 zombies post-run (detector calibrated: 11 procs mid-flight) |
| Container memory behavior | 8 | 7 | RSS 294→303 MiB, plateauing (logarithmic) over 30 sessions; ~9 MB, no linear leak |
| Per-session TIMEOUT enforcement | 10 | 10 | over-timeout session killed at 5.007 s (budget 5.000) → HTTP 408; under-budget → 200 |
| Cross-series render position | 4 | 4 | catches the runtime-injected class katana misses, with zero client code (`endpoints.json`) |
| Operational footprint honesty | 4 | 2 | 4.3 GB image; single-arch-per-manifest pull; VM-mediated numbers not bare-metal |
| **Total** | **100** | **92** | provisional research-material score only |

Scoring notes:

- **Concurrency-ceiling (16/16)** and **queue observability (8/8)** are full marks: the
  documented `CONCURRENT+QUEUED→429` contract was proven on both client status codes and
  server `/pressure`, across three configs, with the ceiling shown to move — dual-truth,
  triple-config corroboration.
- **Startup-tuning honesty (4/6)** is marked down: `PREBOOT` was removed in
  v2.0 (changelog), yet the v2 container accepts `-e PREBOOT=true` **without any error or
  warning** and ignores it. A v1 `PREBOOT` config migrated to v2 is a silent no-op — an operator
  trap, hence the deduction (the removal itself is a reasonable design choice; the silent
  acceptance is the ding).
- **Session recycling (13/14)** / **memory (7/8)**: 30 sequential sessions left zero
  chrome processes and zero zombies (with a **calibrated** detector that saw 11 chrome
  procs mid-flight), and RSS plateaued rather than growing linearly. Not full marks
  because the soak is moderate (30 sessions), not a multi-hour endurance run where the
  KNOWN-ISSUE EventEmitter warning (#20/#228) would surface — see Gaps.
- **TIMEOUT (10/10):** the per-session recycler fired at the boundary (5.007 s vs 5.000 s)
  with a clean 408, not a hang.
- **Operational footprint (2/4):** the capability is real but the cost is real too — a
  4.3 GB image and colima-VM-mediated latency/memory numbers that will differ on
  bare-metal Linux; scored low to keep the deployment cost visible.
- Scores reflect the **container-as-operational-unit** only; Browserless's CDP/WebSocket
  library-compatibility surface, `/function`/`/unblock` endpoints, and multi-hour
  endurance are out of scope (see `research-materials.md` Gaps).
