# Heritrix — pre-test information-gain brief

Date: 2026-07-24. Gate document (deep-review-methodology-v3). Design only.

Broad keyword: **`Heritrix web crawler`** (Internet Archive `internetarchive/heritrix3`).
Article boundary: Heritrix is an **archival-quality, web-scale crawler** whose job is
to *capture* sites faithfully into WARC with polite, scope-disciplined crawling —
not to extract structured fields (Scrapy) nor to discover endpoints for recon
(Katana). This pack judges **archival crawl discipline and output boundaries**:
WARC record fidelity, content-digest dedup, SURT scope discipline, default
politeness cost, and robots obedience — measured on controlled ground truth.

## SERP scan (first ~20 results, official docs, wiki, issues)

### What the results repeat (consensus, mostly unmeasured)

- Heritrix writes **WARC** with full request/response payloads; it is *the*
  reference archival crawler behind the Wayback Machine.
- It is **polite by default**: serialized per host + multi-second delays
  (`delayFactor`, `minDelayMs`, `maxDelayMs`) and obeys `robots.txt`.
- **Scope** is controlled with SURT-prefix DecideRules seeded from the seed hosts.
- **Deduplication** exists but "requires a different configuration" — the wiki's
  *Duplication Reduction Processors* page lists `ContentDigestHistoryLoader` /
  `ContentDigestHistoryStorer`; `WARCWriter.skipIdenticalDigests` defaults false.
- Positioned as **heavy to operate**: Java engine + Jetty Web UI + CXML job beans.

### What is NOT measured anywhere (the gap)

1. The **default WARC record-set per URI** is described qualitatively but never
   counted on ground truth: does the stock profile emit request *and* response
   *and* metadata records; are responses carrying payload digests, capture IP, and
   request↔response `WARC-Concurrent-To` linkage out of the box?
2. **Whether the default profile dedups identical content** is stated ("needs extra
   beans") but the *effect* is not quantified: two distinct URLs with byte-identical
   bodies — how many full `response` payloads does the default write, and does
   enabling the digest-history chain actually convert the second into a WARC
   `revisit`?
3. **The realized cost of default politeness** on a trivial single host — the delay
   formula is documented but the actual inter-request gap distribution and the
   wall-time multiplier vs a tuned crawl are not measured.
4. **Robots obedience on ground truth**: does a `Disallow` actually suppress the
   fetch (server-side proof, hit count 0), and does `robotsPolicyName=ignore`
   reach it?
5. **Deployment friction quantified**: does the current release even start on a
   very new JDK, and what does headless automation (no Web UI clicks) cost?

### Source evidence (to cite at write-up)

- Official: [README](https://github.com/internetarchive/heritrix3),
  [Getting Started](https://heritrix.readthedocs.io/en/latest/getting-started.html)
  (states **"Heritrix requires Java 17 or later"**),
  [REST API](https://heritrix.readthedocs.io/en/latest/api.html),
  [Bean Reference](https://heritrix.readthedocs.io/en/latest/bean-reference.html).
- Wiki: [Configuring Crawl Scope Using DecideRules](https://github.com/internetarchive/heritrix3/wiki/Configuring-Crawl-Scope-Using-DecideRules),
  [Deduping (Duplication Reduction)](https://github.com/internetarchive/heritrix3/wiki/Deduping-(Duplication-Reduction)),
  [Duplication Reduction Processors](https://github.com/internetarchive/heritrix3/wiki/Duplication-Reduction-Processors),
  [Heritrix Output](https://github.com/internetarchive/heritrix3/wiki/Heritrix-Output).
- Upstream issues to scan at execution: `github.com/internetarchive/heritrix3/issues`.

## Testable information-gain hypotheses

- **H1 (WARC fidelity, output boundary):** On a controlled fixture the stock
  default profile emits, per fetched URI, a full `response` + `request` + `metadata`
  record (plus one `warcinfo`), every response carrying a `sha1` payload digest,
  capture IP, and `WARC-Concurrent-To` request↔response linkage. Measure counts and
  linkage against the known endpoint set.
- **H2 (dedup boundary, ADVERSARIAL):** Out of the box, two distinct URLs serving
  byte-identical content produce **two full `response` payloads and zero `revisit`
  records**; adding the `ContentDigestHistory` loader/storer chain converts the
  second into a WARC `revisit`. I.e. "Heritrix dedups" is true only after explicit
  configuration; quantify the default duplicate-write and the enabled reduction.
- **H3 (scope discipline, parity axis):** Default SURT-prefix scope seeded on host A
  does **not** fetch an out-of-scope host B linked from the seed page (server-side
  hit counter on B = 0), while host A is still crawled.
- **H4 (politeness cost, archival discipline):** Under the profile-default
  politeness (`delayFactor 5.0`, `minDelayMs 3000`), the realized inter-request gap
  to a single host sits near `minDelayMs`, making even a ~20-URI local crawl take
  many multiples of a zero-politeness crawl. Measure gap distribution + wall-time
  multiplier over ≥3 runs each.
- **H5 (robots obedience, ADVERSARIAL):** A path linked from the seed but
  `Disallow`-ed in robots.txt is **not fetched** by default (server hit = 0) and is
  recorded blocked; `robotsPolicyName=ignore` reaches it (control).

## Test matrix (tied to hypotheses)

| # | Test | Fixture route | Measures | H |
|---|---|---|---|---|
| 1 | default crawl, WARC record types | full fixture | counts of warcinfo/response/request/metadata | H1 |
| 2 | payload digest / IP / concurrent-to | full fixture | per-response digest+ip; request↔response link | H1 |
| 3 | HTTP status capture | 200 / 404 / 500 routes | status lines preserved in WARC | H1 |
| 4 | dedup default | `/dup/one` + `/dup/two` identical bytes | response vs revisit records, shared digest | H2 |
| 5 | dedup enabled | same + ContentDigestHistory chain | revisit produced; responses reduced | H2 |
| 6 | scope default | `/scope-seed` → out-of-scope host | secondary host hits = 0; in-scope crawled | H3 |
| 7 | depth chain | `/depth/1..3` | nested links followed | H1/H3 |
| 8 | known-files | robots.txt + sitemap.xml | sitemap `<loc>` discovered | H1 |
| 9 | politeness default (≥3 runs) | full fixture | same-host gap dist + wall time | H4 |
| 10 | politeness zero (≥3 runs) | full fixture | wall time baseline; multiplier | H4 |
| 11 | robots obey | `/robots-denied/secret` (Disallow) | server hit = 0; recorded blocked | H5 |
| 12 | robots ignore (control) | same, policy=ignore | server hit > 0 | H5 |
| 13 | deployment | engine boot on JDK 26 + REST lifecycle | starts? headless-automatable? | friction |

Fixture: the **Katana pack fixture** (`tests/fixture_server.py`) — three endpoint
classes + scope-seed + depth chain + robots/sitemap + 500/broken routes + a
server-side hit counter — reused verbatim for the shared routes (parity axis),
**extended additively** with two identical-content URLs (`/dup/*`) and a
robots-`Disallow`-ed path (`/robots-denied/*`) for the archival-specific probes.
Ground truth is emitted to JSON; recall/scope/obedience are measured against the
known set and the server-side counter, never Heritrix stdout alone.

## Boundary / compliance notes

- Evidence phase only; no article, no publish.
- All tests on the **local fixture** (127.0.0.1) — no third-party/production hosts.
- Heritrix is polite/robots-respecting by design; the pack *measures* that
  discipline, it does not defeat it.
- Report politeness as distributions (≥3 runs); scope/obedience via server-side
  truth; deployment cost recorded honestly (JDK, engine boot, host proxy artifact).
