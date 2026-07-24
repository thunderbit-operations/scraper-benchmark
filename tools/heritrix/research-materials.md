# Heritrix — research materials (evidence)

Tool: **Heritrix 3.16.0** (Internet Archive `internetarchive/heritrix3`), the
archival-quality web crawler behind the Wayback Machine. Tested 2026-07-24 on
OpenJDK 26.0.1, macOS arm64. Evidence phase only — no article, no publish.

**What this pack judges:** archival crawl *discipline* and *output boundaries* —
WARC record fidelity, content-digest dedup, SURT scope discipline, default
politeness cost, and robots obedience — on controlled ground truth. It does **not**
judge consumer-scraping features (field extraction, JS rendering); those are out of
Heritrix's role. Numbers below cite fields in `artifacts/raw/*.json`.

## Method (shared ground truth + server-side truth)

A local fixture (`tests/fixture_server.py`) serves a known endpoint set with a
server-side hit counter. It is the **Katana pack fixture reused verbatim** for the
shared routes (three endpoint classes + scope-seed + depth chain + robots/sitemap +
500/broken routes), **extended additively** with two byte-identical-content URLs
(`/dup/one`, `/dup/two`) and a robots-`Disallow`-ed path (`/robots-denied/secret`)
for the archival-specific probes. Ground truth: `artifacts/raw/ground_truth.json`.

Heritrix is driven **headlessly via its REST API** (no Web UI clicks) by
`tests/heritrix_driver.py` + `tests/run_all.py`: one managed engine per run;
per-test job create → PUT `crawler-beans.cxml` → build → launch → unpause → poll to
`FINISHED` → terminate → teardown. Every JSON `observation` field is **computed from
run output** (record counts, server hits, log timestamps) — no conclusion strings
are hardcoded.

Confidence labels: **[measured-3run]** = ≥3 independent process runs with variance;
**[measured-1run]** = single controlled run; **[control]** = paired
positive/negative control.

---

## FINDING-01 — Default profile WARC record fidelity (H1)  ·  `warc-fidelity.json`

On the full fixture (20 fetched URIs) the **stock default profile** wrote, per URI,
one full `response` + one `request` + one `metadata` record, plus one `warcinfo`:

- `record_type_counts` = `{warcinfo: 1, response: 20, request: 20, metadata: 20}`.
- `responses_with_payload_digest` = 20/20 (`sha1:` prefixed); `responses_with_ip` =
  20/20 (`WARC-IP-Address` present).
- `requests_concurrent_to_a_response` = 20/20 — every `request` record is
  `WARC-Concurrent-To` a `response` record (request↔response fully linked).
- HTTP status preserved: response status lines include `200 OK`, `404 Not Found`,
  `500 Internal Server Error` (`response_status_lines_sample`).

Novelty: **DOCUMENTED-behavior, QUANTIFIED.** That Heritrix emits request/response/
metadata WARC records is described on the *Heritrix Output* wiki; what is added here
is the measured per-URI **1:1:1** multiplicity and **20/20 concurrent-to linkage +
digest + IP** against a known endpoint set. `[measured-1run]`

---

## FINDING-02 — Content-digest dedup is off by default; the boundary is a config chain (H2, adversarial)  ·  `dedup.json`

Two distinct URLs serving byte-identical content:

- **Default profile:** `dup_response_records` = 2, `dup_revisit_records` = 0, and
  both responses share **one** payload digest (`identical_payload_digest_shared` =
  2). Heritrix fetches and writes the identical body **twice, in full**.
- **Dedup chain enabled** (added `BdbContentDigestHistory` +
  `ContentDigestHistoryLoader` in the fetch chain + `ContentDigestHistoryStorer`
  after the WARC writer): `dup_response_records` = 1, `dup_revisit_records` = 1, with
  revisit profile `http://netpreserve.org/warc/1.0/revisit/identical-payload-digest`
  — the second capture becomes a WARC `revisit` instead of a full payload.

Novelty: **DOCUMENTED-behavior, QUANTIFIED.** The *Duplication Reduction Processors*
wiki states `skipIdenticalDigests` defaults false and that URL-agnostic dedup
requires the `ContentDigestHistory` loader/storer beans — so "Heritrix dedups" is
true **only after explicit configuration**. Not exclusive; what is added is the
measured default (2 full duplicate payloads / 0 revisit) and the measured effect of
enabling the chain (2→1 responses, +1 revisit). Note: dedup is **write-time** — the
byte is still fetched from origin either way (bandwidth unchanged; storage reduced).
`[measured-1run]` `[control]`

---

## FINDING-03 — Default SURT scope stays on the seed host (H3, parity axis)  ·  `scope.json`

Seeded at `…/scope-seed`, whose page links to an out-of-scope second host
(`localhost:<port>`, a distinct SURT authority from the `127.0.0.1` seed):

- `page_out_hits_on_secondary` = **0** — the out-of-scope host's server counter
  never incremented (server-side proof it was not fetched, not merely absent from
  stdout); `secondary_appeared_in_crawl_log` = false.
- `in_scope_page_a_hits` = 1 — the in-scope host was still crawled, so scope is
  disciplined, not inert.

Novelty: **DOCUMENTED-design, QUANTIFIED (parity).** Default SURT-prefix scope
excluding other hosts is by design; the contribution is server-side-truth
confirmation on the **same fixture Katana used**. **Katana parity:** on this shared
graph both crawlers keep the default crawl on the seed host with **0** out-of-scope
fetches (Katana `scope-summary.json` `default_excludes_out_of_scope_host: true`;
Heritrix here `default_surt_scope_excludes_other_host: true`). The mechanism differs
(Heritrix = SURT-prefix DecideRule from seeds; Katana = DNS field-scope), the
default discipline agrees. `[measured-1run]`

---

## FINDING-04 — Default politeness imposes a ~3.0 s per-host floor (H4)  ·  `politeness.json`

Same fixture, profile-default politeness (`delayFactor 5.0`, `minDelayMs 3000`,
`maxDelayMs 30000`) vs a zeroed-out crawl, 3 runs each:

- **Default:** median same-host inter-request gap = **3036 ms** (min 3021, max
  9107; n=48 gaps) — i.e. the realized gap sits at the **3000 ms `minDelayMs`**
  floor (on a sub-ms-latency local host, `delayFactor × fetch-time` is negligible so
  `minDelayMs` dominates). The full 20-URI single-host crawl spanned **57.66 s**
  (runs 57.66 / 57.66 / 57.70 s — near-zero variance).
- **Zero politeness:** median gap 2 ms; crawl span median **27 ms**.

The wall-time ratio is ~2000× (`default_wall_time_multiplier_over_zero` = 2135.7),
but that ratio is denominator-sensitive (zero-politeness span is tens of ms). The
**defensible statement**: default politeness adds a ~**3.0 s floor per same-host
request** (≈ `minDelayMs`), taking a trivial 20-URI local crawl to ~**57.7 s** —
roughly three orders of magnitude over an unthrottled fetch. This is the archival
discipline being *measured*, not defeated.

Novelty: **DOCUMENTED-formula, QUANTIFIED.** The delay formula is in the docs; the
realized gap distribution pinned to `minDelayMs` and the absolute per-host cost on
ground truth are the added first-party measurement. `[measured-3run]`

---

## FINDING-05 — Robots `Disallow` actually suppresses the fetch (H5, adversarial)  ·  `robots.json`

Home page links to `/robots-denied/secret`; robots.txt has `Disallow:
/robots-denied/`:

- **Default (obey):** `denied_path_server_hits` = **0** (server-side proof the fetch
  was suppressed, not just omitted from output); `robots_txt_fetched` = true;
  `denied_in_crawl_log_as_blocked` = true (recorded with a negative fetch status).
- **Control (`robotsPolicyName=ignore`):** `denied_path_server_hits` = **1** — the
  link is reachable; only the robots policy suppressed it under obey.

Novelty: **DOCUMENTED-design, QUANTIFIED.** Robots obedience is a design promise; the
contribution is the paired server-side-truth verification (0 under obey, 1 under
ignore) that the promise holds on ground truth. `[measured-1run]` `[control]`

---

## FINDING-06 — Deployment cost, and it runs on JDK 26 (friction)  ·  `metadata-snapshot.md`

- **Starts on a very new JDK:** the docs require "Java 17 or later"; Heritrix
  **3.16.0 booted, served its REST API, and completed every crawl on OpenJDK
  26.0.1** with no `--add-opens` / preview flags. Engine reported
  `heritrixVersion: 3.16.0`.
- **Headless-automatable:** the entire job lifecycle is REST (`curl -k --anyauth`);
  no browser is needed. A crawl is a ~750-line Spring `crawler-beans.cxml` in which
  `metadata.operatorContactUrl` and the seed must be set (the stock contact value is
  a placeholder). Distribution ≈ 41 MB / 142 jars.
- **Host artifact (not Heritrix):** on this host a system HTTP proxy
  (`scutil --proxy` → 127.0.0.1:6152, Surge) intercepted even loopback fetches
  (returning 503) despite OS proxy-exceptions and `NO_PROXY` listing 127.0.0.1;
  launching the JVM with `-Djava.net.useSystemProxies=false` fixed it (same crawl
  went 2×503 → 18×200). Verified as proxy-side via a raw-socket request that reached
  the fixture directly. Recorded for reproducibility; **not scored**.

Novelty: **DOCUMENTED requirement + fresh datapoint.** "Java 17+" is documented; the
verified boot+crawl on 26.0.1 and the REST-only automation cost are the added
first-party notes.

---

## Novelty summary (three-way classification)

Every finding here is **documented-behavior that this pack quantifies on shared
ground truth** — none is claimed exclusive/undocumented. The information gain is
first-party measurement + Katana parity, not a secret-behavior claim:

| Finding | Class | Evidence pointer |
|---|---|---|
| 01 WARC record fidelity | Documented → quantified | *Heritrix Output* wiki; `warc-fidelity.json` |
| 02 dedup off by default | Documented → quantified | *Duplication Reduction Processors* wiki (`skipIdenticalDigests=false`); `dedup.json` |
| 03 SURT scope discipline | Documented design → quantified/parity | *Configuring Crawl Scope* wiki; `scope.json` + Katana `scope-summary.json` |
| 04 politeness floor | Documented formula → quantified | politeness docs; `politeness.json` |
| 05 robots obedience | Documented design → quantified | README robots promise; `robots.json` |
| 06 JDK 26 + deployment | Documented req → fresh datapoint | Getting-Started ("Java 17+"); `metadata-snapshot.md` |

## Gaps / not tested (honest)

- **Cross-crawl dedup / recrawl** (`FetchHistoryProcessor` + `PersistLog`, persisting
  a URI history DB across separate crawls) is not exercised — only intra-crawl
  content-digest dedup is measured.
- **Scale / long-run stability** (BDB frontier under millions of URIs, checkpoint/
  restore) is out of scope for a fixture; this pack measures discipline, not scale.
- **JS-rendered capture** (the optional `BrowserProcessor` behaviors) is not tested;
  Heritrix's default capture is non-browser and that is what is measured.
- Politeness `maxDelayMs`/`delayFactor` scaling on a high-latency origin is not
  isolated (local host latency is sub-ms, so `minDelayMs` dominates by construction).
