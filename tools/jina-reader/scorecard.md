# jina-reader — provisional scorecard

**Provisional.** Based only on the completed engine/access material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing a matrix cell or access log. All numbers are scoped to the tested public
targets (quotes.toscrape.com for keyed fidelity; four public pages for anonymous
access) and the fetch dates (engine matrix **2026-07-24**, anonymous probes
**2026-07-10**) — Jina's hosted behavior can change; reported as-of.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 5 | "just add a prefix" is trivial in theory, but the anonymous datacenter path returned **401** — real first-run success needs an API key (`jina_*.txt` logs) |
| Access model (anon vs keyed) | 12 | 7 | binary **401→200**; docs put anonymous in the lowest-trust pool; a key is the intended path, not optional from a server/CI |
| JS-render fidelity (default) | 14 | 12 | default `auto` recovers **8/8** authors on the JS page (`nc_js_default`, 1193 B); header-free users get full content |
| Engine correctness / predictability | 12 | 9 | `direct` **0/8** on JS but **8/8** on the static twin (pure HTTP, by design); `browser`/`auto` 8/8; predictable once the model is understood |
| Latency / engine efficiency | 10 | 6 | default `auto` is the **slowest** (4.81s cold) for output identical to `browser` (1.94s); `direct` 0.99s; single-run in-pack |
| Cache behavior / control | 8 | 6 | `X-No-Cache: true` forces a fresh fetch; default may serve a **flagged** snapshot; one cold stale **0/8** hit observed but not reproduced |
| Output cleanliness | 8 | 7 | returned markdown is clean (title + quotes, minimal chrome); full boilerplate-precision-vs-ground-truth not scored (Gap) |
| Developer experience | 8 | 7 | maximally simple API shape (URL prefix + `X-*` headers); docs clear that a free key is the intended path |
| Operations (hosted) | 8 | 6 | hosted = nothing to run; hard dependency on Jina reputation gating + a key for server use |
| Maintenance / ecosystem | 6 | 6 | active repo (commits to 2026-05-22), Apache-2.0, MCP + ReaderLM ecosystem; **0 tagged releases** makes version pinning awkward |
| Reproducibility of this pack | 4 | 3 | full harness shipped, key read from `$JINA_KEY` env (never committed); timing single-run, anon-path residential retest deferred |
| **Total** | **100** | **74** | provisional research-material score only, not a final rating |

Scoring notes:

- **Setup and first run (5/10):** the headline "zero setup, just a prefix" is real
  for a residential browser user but **did not hold from a datacenter egress** — a
  hard 401 every time, across all four shipped anonymous GET probes (single
  datacenter egress). For a
  scraping/automation audience (who run from servers) the honest first-run story is
  "get a key first." Not lower because the keyed path is genuinely one header.
- **Access model (7/12):** the 401→200 gate is clean and the docs are honest that
  anonymous is the lowest-trust pool. Docked because from a server the "free, no
  key" promise is effectively "keyed," and because the anonymous-from-residential
  path was not retested to fully qualify it (Gap).
- **JS-render fidelity (12/14):** near-full — the **default** engine renders JS and
  recovers every author (8/8) with no header tuning. Held back two points only
  because fidelity was measured on one JS fixture and recall (not full precision).
- **Engine correctness / predictability (9/12):** the engine model is **coherent** —
  `direct` is a pure HTTP fetch (8/8 on server-rendered HTML), blind only to
  client-side JS, which the static-twin control proves is by design, not a defect.
  Docked because `X-Engine: direct`/`curl` on a JS page is a **silent** 0/8 with no
  error — a genuine foot-gun if chosen for speed.
- **Latency / engine efficiency (6/10):** the default `auto` is the **slowest** cell
  (4.81s cold) while producing byte-identical output to `browser` (1.94s), so the
  default trades ~2.5× latency for nothing on this page; warm cache collapses it to
  0.96s. Docked for the inefficiency of the default; not lower because the in-pack
  timing is **single-run** (medium confidence) — the operator's 3-rep bands agree in
  direction but a full distribution is a Gap.
- **Cache behavior / control (6/8):** `X-No-Cache` reliably forces fresh and Jina
  **self-flags** cached snapshots, which is good hygiene. Docked because the default
  can silently hand back a snapshot, and a cold stale **0/8** was observed once but
  **could not be reproduced** after warming — reported as an observation, never a
  headline (no shipped artifact of a stale hit).
- **Output cleanliness / DX / Operations / Maintenance** score mid-high on
  unambiguous, mostly-positive evidence: clean markdown, a maximally simple API
  surface, nothing to self-host, an active Apache-2.0 repo with an MCP/ReaderLM
  ecosystem — with the standing caveats (reputation gating, 0 tagged releases).
- **Reproducibility of this pack (3/4):** the harness and every response artifact
  ship, and recall/bytes are re-derivable with **no network and no key**
  (`recompute_recall.py`). Docked because reproducing the *live* matrix requires the
  operator's own `$JINA_KEY`, the timing is single-run, and the anonymous-from-
  residential retest is deferred.
- Scores reflect **access + engine/cache fidelity on the tested public targets**
  only; Jina is **not** scored on paid tiers, `s.jina.ai` search, the MCP server,
  ReaderLM-v2, or boilerplate precision against a rich real page (all Gaps).
- Per methodology, **do not** sum this into a published headline number while Gaps
  (residential anon retest, timing distribution, precision study) remain open.
