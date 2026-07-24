# apache-nutch — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking. Weights
are pack-local, pre-registered here, and chosen to reflect the queue focus (**crawl
control + deployment cost**). Scores are evidence-anchored, each citing a run. Nutch
is judged on discovery coverage + crawl discipline + deployment cost only — not on
structured-data/content extraction, which is out of its scope.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup / first run (JDK + config) | 12 | 4 | host JDK 26 hard-blocks the crawl (`getSubject`); forced LTS 17; empty `http.agent.name` refuses fetch (`jdk_matrix`, `config_steps`) |
| Static / HTML discovery | 12 | 12 | class A 4/4 + depth chain 3/3, deterministic across 3 repeats (`discovery-summary.json`) |
| JS-endpoint discovery (`parse-js`) | 12 | 9 | B recall 0→1.0 once `parse-js` enabled (2/2), browserless; not default, but not mode-gated either |
| Runtime-DOM discovery | 10 | 3 | class C unreached by all static configs; `protocol-htmlunit` swap not drop-in (1 round, 0 records round 2) |
| Scope discipline | 12 | 8 | `ignore.external`=true and host `regex-urlfilter` both fully contain, but shipped **default follows external** (crawldb+server agree) |
| Depth control | 8 | 7 | depth == rounds, one level/round (2→d1, 3→d2, 4→d3); no single `--depth` flag |
| Known-files / sitemap | 10 | 6 | normal crawl ignores sitemap (0/2); separate `bin/nutch sitemap` injects 2/2 (recall 1.0) |
| Deployment footprint / cost | 12 | 4 | ≈395 MB / 188 jars / 78 plugins; round ≈12.1 s = N fresh JVMs (~1.77 s floor); depth-4 ≈45 s vs katana ≈13 s |
| Robustness (500 / dead link) | 6 | 6 | crawl continues rc=0; 500→`db_unfetched`, 404→`db_gone`, distinct protocol codes |
| Politeness / cost transparency | 6 | 6 | `fetcher.server.delay` honored (median 1.009 s @ 1.0); per-phase timing distribution reported |
| **Total** | **100** | **65** | provisional research-material score only |

Scoring notes:

- **Setup / first run (4/12)** is the lowest-with-weight: the *latest* Nutch cannot run
  on the host's current JDK at all (FINDING-01), the escape hatch is rejected, and even
  on the LTS the shipped `http.agent.name` is empty so the first fetch is refused. This
  is real, measured first-run friction, not a preference.
- **Deployment footprint / cost (4/12)** reflects the ≈395 MB / 188-jar / 78-plugin
  install and a batch cycle that is N fresh JVMs (~1.77 s startup floor each), ≈45 s for
  a depth-4 crawl of a tiny fixture vs katana's single ≈13 s process — architectural
  cost, quantified.
- **JS-endpoint discovery (9/12)**: `parse-js` recovers both class-B endpoints
  browserless (parity with katana `-jc`) and, unlike katana's `-jc` under `-headless`,
  is not inert — but it is off by default, so partial credit for the activation step.
- **Runtime-DOM (3/10)**: no static plugin reaches class C and the JS-executing protocol
  probe was not drop-in; credit retained only because the capability exists and the
  probe loaded/ran (FINDING-03, scoped as a bounded probe).
- **Scope discipline (8/12)**: both containment mechanisms verifiably work
  (crawldb + independent server counter agree), but the shipped default leaks to
  external hosts, so it is docked for an unsafe default rather than a broken control.
- **Static discovery, robustness, politeness** are full marks: deterministic class-A
  coverage, clean error handling with distinct crawldb status, and an honored delay.
- Scores are **local-mode, single-host, tiny-fixture, macOS/JDK-17** only; distributed
  mode, resume/hostdb, and Solr indexing were not tested (see Gaps).
