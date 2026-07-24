# jina-reader — metadata snapshot

Engine-matrix test date: **2026-07-24** (as-of). GitHub metadata fetched
**2026-07-10** (as-of) — refresh within 48h before any final draft.

## Service under test

| Field | Value |
|---|---|
| Service | **Jina Reader** — hosted URL→Markdown |
| Endpoint tested | `https://r.jina.ai/<URL>` (GET prefix) |
| Auth | `Authorization: Bearer $JINA_KEY` — key read from the environment at run time |
| Out of scope | paid tiers, `s.jina.ai` (search), `mcp.jina.ai` (MCP), ReaderLM-v2 |

## GitHub metadata (as-of 2026-07-10)

| Field | Value |
|---|---|
| Repo | [jina-ai/reader](https://github.com/jina-ai/reader) |
| Description | "Convert any URL to an LLM-friendly input with a simple prefix `https://r.jina.ai/`" |
| Stars | **11,506** |
| Forks | **847** |
| Open issues | **25** |
| License | **Apache-2.0** |
| Default branch | **main** |
| Primary language | **TypeScript** |
| Tagged GitHub releases | **0** (continuous deploy from `main`; no Releases, no git tags) |
| Latest commit on `main` | **1574bfd**, 2026-05-22 |
| Repo created | **2024-04-10** |
| Homepage | https://jina.ai/reader |

Profile = **hosted SaaS with an open-source core** (TypeScript service, no versioned
releases), not a `pip install` library. Star count understates usage. Refresh before
any final draft.

## Test environment (as actually run)

| Item | Value |
|---|---|
| Machine | macOS arm64 |
| Client | `curl` (system) |
| Reader path | keyed GET prefix `https://r.jina.ai/<URL>` |
| Keyed fidelity target | quotes.toscrape.com — `/js` (JS-injected) + `/` (server-rendered) |
| Anonymous-probe targets | books.toscrape.com, quotes.toscrape.com, scrapethissite.com/pages/forms, en.wikipedia.org/wiki/Web_scraping |
| Engine-matrix test date | **2026-07-24** |
| Anonymous-probe date | **2026-07-10** |
| Egress (anon probe) | 95.169.4.109 (AS25820 IT7 Networks, LA) + a second independent egress |

## Key / credential handling (read this before reproducing)

- **This pack contains no API key** — not in any script, artifact, log, or commit.
  `grep` for `jina_` / `Bearer ` over the pack returns only the harness's *env-read*
  and doc mentions, never a literal token.
- **The harness reads the key from the environment**, `$JINA_KEY`, which the operator
  sets at run time. `tests/run_engine_matrix.sh` does
  `AUTH="Authorization: Bearer $JINA_KEY"` and aborts if `$JINA_KEY` is unset — the
  value is never printed, written to an artifact, or echoed into the ndjson.
- **Reproducing the live matrix requires your own free Jina API key.** Get one at the
  Reader API page; export it, then run the harness. The recall/byte **recompute**
  (`tests/recompute_recall.py`) needs **neither network nor key** — it re-derives the
  numbers from the shipped `.md` responses.

## Engine / header matrix (variables exercised)

| `X-Engine` | Renders JS? | On `/js` (JS) | On `/` (static) |
|---|:--:|:--:|:--:|
| *auto* (default) | yes | 8/8, 1193 B, 4.81s cold / 0.96s warm | 8/8, 1787 B, 1.69s |
| `browser` | yes | 8/8, 1193 B, 1.94s | (not run; = auto on static) |
| `browser` + `X-Wait-For-Selector: .quote` | yes | 8/8, 1193 B, 1.77s | — |
| `direct` (`curl`) | **no** | **0/8, 348 B, 0.99s** | **8/8, 1787 B, 0.94s** |

Other headers used: `X-No-Cache: true` (forces fresh; all no-cache cells above),
`Accept: text/markdown` (response format). `time_s` is single-run `curl` wall time.

## Exact commands run

```bash
cd tools/jina-reader

# 1) LIVE engine/cache matrix — needs YOUR key in the environment (never committed):
export JINA_KEY="jina_..."          # or from a secret store the operator controls
bash tests/run_engine_matrix.sh      # -> artifacts/raw/engine-matrix.ndjson + *.md

# 2) Deterministic recompute — NO network, NO key (verifies recall/bytes):
python3 tests/recompute_recall.py --check    # -> artifacts/raw/recall_recompute.json
```

## Reproducibility notes (honest)

- **Live results need a key; the audit does not.** Anyone can re-derive every recall
  and byte number from the shipped `.md` responses with `recompute_recall.py`
  (offline). Only re-fetching the live matrix needs `$JINA_KEY`.
- **Ground truth = 8 distinct authors** on quotes.toscrape.com page 1 (10 quotes,
  Einstein appears 3×). `/js/page/N/` deeper pages are **not** scored (their proxied
  fetch was unreliable; the main loop dropped them).
- **Timing is single-run per cell** in the shipped matrix. The operator observed the
  ordering (`direct` < `browser` < `auto`) hold across 3 no-cache reps (`browser`
  ~1.7–4.4s, `auto` ~4.8–9.5s), but the full per-run raw is not all shipped — treat
  magnitudes as directional, not a distribution.
- **Cache is non-deterministic.** The shipped `cached_js` cell is **warm** (8/8); a
  cold stale 0/8 snapshot was observed once and could not be reproduced after
  warming, so no cache-trap claim is made. Use `X-No-Cache: true` for determinism.
- **Anonymous access is egress-dependent.** The 401 is "as-of 2026-07-10 from
  AS25820 / the second egress"; a residential IP or later date could return 200
  anonymously. Reproducible now, not necessarily universal or permanent.
- **Fidelity is scoped to the tested public targets and the fetch date.** Jina's
  hosted behavior can change; every claim is as-of.
