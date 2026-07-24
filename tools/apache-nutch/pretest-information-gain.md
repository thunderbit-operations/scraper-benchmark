# Apache Nutch — pre-test information-gain brief

Date: 2026-07-24. Gate document. Design + gate verdict.

Broad keyword: **`Apache Nutch web crawler`** (`apache/nutch`, the JVM/Hadoop-based
extensible crawler).
Article boundary: Nutch is a **batch, plugin-based, Hadoop-backed crawler** built to
discover and fetch large URL frontiers for search-index/archival pipelines — not a
structured-data extractor (Scrapy) or a content converter (Jina/trafilatura). This
pack judges **crawl control + deployment cost on controlled ground truth**, matching
the queue focus "measure modern crawl control and deployment cost."

## SERP scan (first ~20 results, official docs/wiki, GitHub, upstream issues)

### What the results repeat (consensus, mostly unmeasured)

- Nutch is **heavyweight**: "complex to set up," "requires understanding of Hadoop/
  HDFS," "big-data crawler," vs Scrapy "lightweight/easy." (Medium Scrapy-vs-Nutch,
  ZenRows, Octoparse, wpbloghelp, Quora.)
- Crawl cycle is a **batch loop**: `inject → generate → fetch → parse → updatedb`
  (→ invertlinks → index), driven by `bin/nutch` / `bin/crawl <dir> <rounds>`. Local
  mode runs Hadoop's LocalJobRunner — no cluster needed. (Nutch wiki NutchTutorial,
  Baeldung.)
- Scope/politeness via config: `regex-urlfilter.txt`, `db.ignore.external.links`,
  `fetcher.server.delay` (default 5 s), robots `Crawl-delay` obeyed. (Nutch wiki
  OptimizingCrawls / FAQ.)
- A **`parse-js`** plugin exists — "heuristic link extractor for JavaScript files…
  two-pass regex, idea from Heritrix" — but is **not** in the default `plugin.includes`.
  (Nutch wiki AboutPlugins, plugin javadoc.)
- Java: README says **CI uses Java 17 / "select Java 17 (or newer)"**; no stated
  upper bound.

### What is NOT measured anywhere (the gap)

1. **Whether the *latest* Nutch runs on a *current* JDK.** Everyone cites "Java 17";
   nobody measures Nutch 1.22 on JDK 24/25/26. Hadoop's `Subject.getSubject` removal
   (JEP 486) is documented at the **Hadoop** level (HADOOP-19212/19486, HDFS-17778,
   fixed in 3.4.3/3.5.0) but **no source ties it to a specific Nutch release's bundled
   Hadoop**. Nutch 1.22 bundles which Hadoop, and does it clear the fix?
2. **Per-endpoint-class discovery on shared ground truth.** "Browserless crawler,
   misses JS" is asserted; nobody quantifies, on a page with known endpoints, what
   default vs `parse-js` recovers, or maps it to a modern crawler's modes.
3. **The real deployment cost, quantified.** "Complex/heavyweight" is qualitative.
   Nobody counts the jars/plugins/config-steps/first-fetch friction, or times the
   batch cycle against a single-binary crawler on the same fixture.
4. **Scope/known-files/politeness behavior demonstrated on ground truth**, and how
   Nutch's batch model differs from an in-crawl `-kf` (katana) for sitemaps.

### Source evidence

- Official: [apache/nutch README](https://github.com/apache/nutch),
  [NutchTutorial](https://cwiki.apache.org/confluence/display/nutch/NutchTutorial),
  [AboutPlugins](https://cwiki.apache.org/confluence/display/nutch/AboutPlugins),
  [OptimizingCrawls](https://cwiki.apache.org/confluence/display/nutch/OptimizingCrawls).
- Java/Hadoop compat: [HADOOP-19212](https://issues.apache.org/jira/browse/HADOOP-19212),
  [HADOOP-19486](https://issues.apache.org/jira/browse/HADOOP-19486),
  [HDFS-17778](https://issues.apache.org/jira/browse/HDFS-17778).
- SERP: Medium Scrapy-vs-Nutch, ZenRows Apache-Nutch guide, Baeldung Apache-Nutch.

## Testable information-gain hypotheses

- **H1 (coverage, core):** On the katana same-fixture ground truth, a default local
  crawl recovers class A (HTML) fully but misses class B (JS-literal) and class C
  (runtime-DOM) — mirroring katana *standard* mode.
- **H2 (plugin activation, core + adversarial):** Enabling `parse-js` recovers class
  B **without a browser** (parity with katana `-jc`); class C stays unreachable for
  any static plugin set (parity with "needs `-headless`"). Adversarial: does the
  regex heuristic actually catch `fetch('…')` and a `const x = "…"` literal?
- **H3 (crawl control):** Depth == number of rounds (the chain `/depth/1→2→3` is
  fetched one level per round); the out-of-scope host is/ isn't fetched under
  `db.ignore.external.links` false vs true and under a host `regex-urlfilter`.
- **H4 (deployment cost, headline):** Quantify first-successful-crawl cost vs a
  single-binary crawler — JDK compatibility (does it even run on the host JDK?),
  unpacked size / jar+plugin count, mandatory config steps, and per-phase wall time
  (the batch cycle is N fresh JVMs).
- **H5 (robustness / known-files / politeness):** Crawl survives 500 + dead link
  (distinct crawldb status each); a normal crawl does **not** auto-consume sitemap.xml
  (unlike `-kf`) but the separate `bin/nutch sitemap` does; `fetcher.server.delay` is
  honored (server-side inter-fetch gap).

## Test matrix (tied to hypotheses)

| # | Test | Measures | H |
|---|---|---|---|
| 1-3 | default crawl, per-class recall (A/B/C), ×3 repeats | recall vs ground truth; determinism | H1 |
| 4-6 | parse-js crawl, per-class recall, ×3 repeats | B recovered without browser? C still missed? | H2 |
| 7 | protocol-htmlunit swap-in probe | is runtime-DOM (C) reachable, at what cost | H2 |
| 8-10 | depth rounds 2/3/4 | deepest chain link fetched per round | H3 |
| 11-13 | scope: ext-on / ignore-external / urlfilter | out-of-scope host fetched? (crawldb + server) | H3 |
| 14-16 | JDK matrix: 26 / 26+secmgr / 17 | inject succeeds? exact error | H4 |
| 17 | footprint | size, jars, plugins, conf files | H4 |
| 18 | config-steps | empty vs set http.agent.name → fetch refused? | H4 |
| 19 | per-phase timing (×3) | JVM floor + phase distribution | H4 |
| 20 | robustness: 500 + 404 | crawldb status/protocol code; crawl continues | H5 |
| 21 | sitemap: normal vs `bin/nutch sitemap` | auto-consumed? command recall | H5 |
| 22 | politeness delay 0.0 vs 1.0 | server-side inter-fetch gap | H5 |

Fixture: reuse the katana same-fixture (three endpoint classes A/B/C + server-side
hit truth + timestamps) so discovery coverage is directly comparable. A second
fixture on host `localhost` serves the out-of-scope target for H3.

## Gate verdict — **PROCEED** (with a hard JDK caveat)

- **JDK 26 (host default): BLOCKED.** `bin/nutch inject` dies with
  `UnsupportedOperationException: getSubject is not supported`; the
  `-Djava.security.manager=allow` workaround is rejected by the VM. This is itself
  measured as an H4 finding.
- **JDK 17 (LTS): crawl cycle runs** (inject→…→updatedb verified). Installed
  `openjdk@17` keg-only; the evaluation runs on it.
- **Not blocked by Solr/Hadoop cluster:** local mode uses Hadoop's in-process
  LocalJobRunner; indexing to Solr is skipped (out of scope for discovery/cost).
- Clear net-new information over the SERP consensus on all five hypotheses →
  PROCEED to build the pack.

## Boundary / compliance notes

- Evidence phase only; no article, no publish. Local fixture / loopback only; no
  third-party or production targets; no anti-bot; no auth.
- Novelty honesty: Nutch's documented capabilities (parse-js, batch cycle, scope
  config, the Hadoop-JDK issue at the Hadoop level) are **DOCUMENTED**; only the
  quantification, the Nutch-1.22-specific JDK-26 block, and the same-fixture parity
  numbers are **EXCLUSIVE**.
