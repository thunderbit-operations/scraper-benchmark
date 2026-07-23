# katana — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing a run.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 8 | single Go binary (`~/go/bin/katana` v1.6.1); headless auto-found a browser |
| Static/HTML discovery | 12 | 12 | class A 4/4 + depth chain 3/3 in every mode (`discovery-summary.json`) |
| JS-endpoint discovery (`-jc`) | 12 | 9 | class B 2/2 in standard+jc, but 0/2 under headless (inert) |
| Runtime-DOM discovery (headless) | 12 | 10 | class C found only by headless; ~5.1× time cost |
| Mode-selection clarity | 10 | 6 | no single command covers B+C; `headless_jc_covers_both: false` |
| Scope discipline | 12 | 10 | default/fqdn/`-cs` never fetch out-of-scope host; `-fs` regex widens correctly |
| Resume | 10 | 6 | reaches same set but re-crawls 10/10 completed pages (per-seed granularity) |
| Known-files | 10 | 4 | requests robots/sitemap but 0/2 loc recall on IP targets (`scope`/RootHostname boundary) |
| Cost transparency | 6 | 6 | non-overlapping distributions; standard 500-retry tail reported un-tuned |
| Robustness (500 / dead link) | 6 | 6 | crawl continues past 500 and broken link, rc=0 |
| **Total** | **100** | **77** | provisional research-material score only |

Scoring notes:

- **JS-endpoint discovery** is marked down (9/12) because `-jc` recovers class B in
  standard mode (2/2) but contributes nothing under `-headless` (still 0/2) — the
  parser you'd reach for on JS-heavy targets is inert in the very mode people enable
  for JS.
- **Mode-selection clarity** is marked down (6/10) because no single invocation
  covers both JS-literal (B) and runtime-DOM (C) endpoints; correct coverage needs
  the union of a `standard -jc` run and a `-headless` run. The common "just use
  headless" advice loses class B.
- **Resume** is marked down (6/10) because the checkpoint persists only in-flight
  *seed* targets; a resumed single-seed crawl re-fetches every already-completed
  page (measured: 10/10). It reaches the same final set, so it is not broken — just
  coarse.
- **Known-files** is the lowest (4/10): `-kf all -d 3` requests robots.txt and
  sitemap.xml but recovers 0/2 of the sitemap's `<loc>` endpoints on an IP target,
  because the sitemap crawler doesn't propagate the root hostname and IP-host scope
  validation rejects the loc URLs (source-cited). Not user error; a real default
  boundary. Partial credit retained because robots/sitemap are correctly requested
  and the source-predicted `-fs` workaround is plausible (unconfirmed against `-kf`).
- Scores reflect **discovery coverage + crawl discipline** only; katana is not
  scored on structured-data or content extraction, which are out of its scope.
