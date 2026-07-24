# jina-reader — evidence pack

Independent, reproducible tests for **Jina Reader**, the hosted
`https://r.jina.ai/<URL>` service that fetches a live URL server-side and returns
LLM-friendly Markdown. Part of the Thunderbit open-source scraping-tool benchmark.
Every number in `research-materials.md` traces to a script here and a response
artifact under `artifacts/raw/`.

Tested: engine/cache matrix **2026-07-24** (keyed, quotes.toscrape.com); anonymous
access probes **2026-07-10** (four public pages); macOS arm64.

**No API key is in this pack.** The live harness reads the key from a `$JINA_KEY`
environment variable the operator sets at run time — it is never written to a
script, artifact, log, or commit. Every shipped response is public
quotes.toscrape.com content.

## Headline

The API key buys **access, not fidelity.** From a datacenter egress the anonymous
prefix is refused with a hard **HTTP 401 `AuthenticationRequiredError`** on every
target; with a key the request is *allowed*, and from there **what content you get
is governed by `X-Engine` + cache, never by the key**. On the JS page (cache
bypassed): `X-Engine: direct` (the `curl` engine) returns **0 of 8** authors in 348
bytes of nav chrome — it does not run JavaScript — while `browser` and the default
`auto` return **8/8** in 1193 bytes on the same URL. Crucially, `direct` is a **pure
HTTP fetch, not a lossy engine**: on the server-rendered twin it returns **8/8**,
byte-identical to `auto`, so its JS-blindness is by design and fires only if you
*explicitly* pick it. And a timing reversal: the default `auto` is the **slowest**
engine (4.81s cold) for output identical to `browser` (1.94s); `direct` is fastest
(0.99s) — pinning `browser` is ~2.5× faster than the default at no fidelity cost.

## Reproduce

```bash
# 1) LIVE engine/cache matrix — needs YOUR free Jina key in the environment:
export JINA_KEY="jina_..."           # never committed; harness aborts if unset
bash tests/run_engine_matrix.sh       # -> artifacts/raw/engine-matrix.ndjson + *.md

# 2) Deterministic recompute — NO network, NO key:
python3 tests/recompute_recall.py --check    # -> artifacts/raw/recall_recompute.json
```

Step 1 re-fetches the live matrix (requires the key). Step 2 re-derives every recall
and byte number from the shipped `.md` responses **offline** and asserts they equal
the recorded matrix (`recall_recompute.json: consistent_with_shipped_matrix = true`)
— so the fidelity numbers are provably computed, not hand-typed.

## What the pack establishes

- **Access vs fidelity (core):** anonymous datacenter = hard 401; keyed = 200.
  Fidelity varies only by `X-Engine` + cache with the key held constant ⇒ the key's
  role is isolated to access. (H1 rests on this decomposition; the cleanest direct
  anon/keyed byte-diff is blocked by the 401 and listed as a Gap.)
- **Engine recall:** `direct` 0/8 on the JS page (JS-blind), `browser`/`auto` 8/8;
  `direct` 8/8 on the static twin (pure HTTP, by design).
- **Timing reversal:** default `auto` slowest (4.81s cold) for output identical to
  `browser` (1.94s); `direct` fastest (0.99s); warm cache collapses `auto` to 0.96s.
- **Access outcome:** anonymous 401 `AuthenticationRequiredError` reproduced across
  all 4 shipped anonymous GET probes (single datacenter egress); the error's ASN is misattributed
  (flag, not a bug claim).
- **Cache:** `X-No-Cache: true` forces fresh; default may serve a **flagged**
  snapshot; one cold stale 0/8 hit observed but **not reproduced** — no headline.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, hypotheses,
  matrix, PROCEED verdict; calibrated to the measured results).
- `research-materials.md` — full evidence, per-hypothesis verdict, per-finding
  confidence, novelty table, Part-6 self-check.
- `scorecard.md` — provisional dimension scores (74/100), evidence-anchored.
- `metadata-snapshot.md` — endpoint, versions, engine/header matrix, key handling,
  exact commands, reproducibility notes.
- `tests/` — `run_engine_matrix.sh` (live, key from env) and `recompute_recall.py`
  (offline recall/byte re-derivation).
- `artifacts/raw/` — `engine-matrix.ndjson`, `recall_recompute.json`, one `.md` per
  matrix cell, and the anonymous 401 `.txt` access logs.

Evidence phase only: no article, no publishing. All fidelity numbers are scoped to
the tested public targets and the fetch dates — Jina's hosted behavior can change,
so every claim is as-of.
