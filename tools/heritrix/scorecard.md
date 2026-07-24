# Heritrix — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing an `artifacts/raw/*.json` field. Dimensions follow the Katana scorecard shape
but are re-cast for **archival crawl discipline + output boundaries** (Heritrix's
role), not discovery coverage.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 6 | boots on JDK 26 + REST lifecycle works, but 41 MB / 142 jars + ~750-line cxml + mandatory contact URL (`metadata-snapshot.md`) |
| WARC record fidelity | 14 | 14 | 20/20 URIs → response+request+metadata; 20/20 sha1 digest + IP + concurrent-to linkage (`warc-fidelity.json`) |
| HTTP status / metadata capture | 8 | 8 | 200 / 404 / 500 status lines preserved; 1 metadata record per URI (`warc-fidelity.json`) |
| Content-digest dedup | 12 | 8 | OFF by default (2 full duplicate payloads / 0 revisit); enabling the chain → 1 response + 1 `revisit` (`dedup.json`) |
| Scope discipline | 12 | 11 | default SURT scope fetched out-of-scope host 0× while in-scope host crawled (`scope.json`) |
| Politeness discipline | 10 | 10 | realized same-host gap median 3036 ms ≈ `minDelayMs` 3000; 20-URI crawl 57.7 s, tight variance (`politeness.json`) |
| Robots obedience | 10 | 10 | Disallowed path 0 server hits under obey / 1 under ignore; recorded blocked (`robots.json`) |
| Known-files (robots/sitemap) | 6 | 5 | robots.txt requested + sitemap directive followed (`robots.json` `robots_txt_fetched`); loc recall not separately asserted (Gap) |
| Headless automatability (REST) | 10 | 8 | full create→build→launch→unpause→teardown via `curl`, no Web UI (`heritrix_driver.py`) |
| Deployment friction (heavier = lower) | 8 | 5 | Java engine + Jetty + 750-line Spring-bean job config; ~41 MB / 142 jars + a mandatory operator contact URL before the first fetch |
| **Total** | **100** | **85** | provisional research-material score only |

Scoring notes:

- **Content-digest dedup** is marked down (8/12) because the **default profile writes
  identical content twice** (`dedup_response_records: 2`, `dup_revisit_records: 0`,
  one shared digest) — dedup is a promise that only materializes after adding the
  `ContentDigestHistory` loader/storer beans. Credit is high, not full, because once
  configured it correctly emits an `identical-payload-digest` revisit and it is a
  documented (not hidden) boundary. Note dedup is write-time only — the byte is still
  fetched from origin.
- **Setup / deployment friction** are the two lowest structural scores: a single
  archival crawl requires a 41 MB Java distribution, a running engine + Jetty UI, and
  a ~750-line Spring `crawler-beans.cxml`, versus a single-binary CLI. This is the
  real cost of Heritrix's configurability, quantified, not editorialized.
- **Known-files** (5/6) retains partial credit: robots.txt is requested and the
  sitemap directive is followed, but this pack did not emit a dedicated
  sitemap-`<loc>` recall field, so the dimension is not fully asserted (listed in
  Gaps).
- **Politeness / robots / scope / WARC fidelity** score high because they are exactly
  what an archival crawler is for, and each is confirmed against ground truth or a
  server-side hit counter — not against Heritrix's own stdout.
- Scores reflect **archival discipline + output boundaries** only; Heritrix is not
  scored on JS-rendered capture, structured-data extraction, or scale, which are out
  of this pack's scope (see `research-materials.md` Gaps).
