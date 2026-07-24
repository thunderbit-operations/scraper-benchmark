# Heritrix — archival crawl discipline evidence pack

Evidence-only evaluation of **Heritrix 3.16.0** (Internet Archive
`internetarchive/heritrix3`), the archival-quality web crawler behind the Wayback
Machine. Focus: **archival crawl discipline and output boundaries** — WARC record
fidelity, content-digest dedup, SURT scope, default politeness cost, and robots
obedience — measured on controlled ground truth. Not a consumer-scraping review, not
a cross-tool ranking, not published copy.

Tested 2026-07-24 on **OpenJDK 26.0.1**, macOS arm64.

## Headlines (each cites a field in `artifacts/raw/*.json`)

- **WARC fidelity:** the stock default profile wrote, for 20 fetched URIs, 20
  `response` + 20 `request` + 20 `metadata` records + 1 `warcinfo`; every response
  carried a `sha1` payload digest, capture IP, and full request↔response
  `WARC-Concurrent-To` linkage (`warc-fidelity.json`).
- **Dedup is off by default:** two URLs with byte-identical content produced **2 full
  response payloads and 0 revisit** records out of the box; adding the
  `ContentDigestHistory` loader/storer chain converts the second into a WARC
  `revisit` (identical-payload-digest) (`dedup.json`).
- **Scope discipline:** default SURT-prefix scope fetched a linked out-of-scope host
  **0** times (server-side truth) while still crawling the in-scope host
  (`scope.json`). Same default discipline as Katana on the shared fixture.
- **Politeness:** the profile default imposes a **~3.0 s floor per same-host request**
  (median gap 3036 ms ≈ `minDelayMs` 3000), taking a trivial 20-URI local crawl to
  **~57.7 s** vs ~27 ms unthrottled (`politeness.json`).
- **Robots obedience:** a `Disallow`-ed path was fetched **0** times under default
  obey and **1** time under `policy=ignore` control; recorded blocked (`robots.json`).
- **Deployment:** boots + crawls on **JDK 26.0.1** (docs require "Java 17+"), fully
  **headless via REST** (no Web UI), but a 41 MB Java distribution + ~750-line Spring
  job config (`metadata-snapshot.md`).

**Provisional scorecard: 85 / 100** (`scorecard.md`) — archival discipline only.

## Layout

```
notes/pretest-information-gain.md   pre-test gate: consensus, gap, hypotheses, matrix
research-materials.md               findings (FINDING-01..06) with novelty tags + Gaps
scorecard.md                        pack-local weighted dimensions (85/100)
metadata-snapshot.md                version, JDK, exact commands, deployment cost, repro notes
tests/fixture_server.py             Katana fixture reused + additive dup/robots-denied routes
tests/heritrix_driver.py            managed engine + REST job lifecycle + WARC/crawl.log parsers
tests/run_all.py                    orchestrator: 5 concerns → artifacts/raw/*.json
artifacts/raw/*.json                measured outputs (observation fields computed, not hardcoded)
```

## Reproduce

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk && export PATH="$JAVA_HOME/bin:$PATH"  # JDK 17+

# One-time: download the release into the git-ignored vendor/ dir (NOT committed)
mkdir -p vendor && cd vendor
curl -sL -o heritrix-3.16.0-dist.tar.gz \
  https://github.com/internetarchive/heritrix3/releases/download/3.16.0/heritrix-3.16.0-dist.tar.gz
tar xzf heritrix-3.16.0-dist.tar.gz && cd ..

# Run the whole harness (~5-7 min incl. 3x default-politeness runs)
python3 tests/run_all.py
```

The harness starts the fixture(s) and a **managed Heritrix engine**, runs the five
concerns, then tears down every job and stops the engine JVM in a `finally` block.
`vendor/` (the release + all `jobs/` WARC output) is git-ignored; the JSON summaries
carry the numbers.

## Honesty notes

- Every finding is **documented Heritrix behavior that this pack quantifies** on
  shared ground truth — none is claimed exclusive/undocumented. The information gain
  is first-party measurement + Katana parity (see `research-materials.md` novelty
  table).
- The engine is launched with `-Djava.net.useSystemProxies=false` because **this
  host** runs a system HTTP proxy that intercepted loopback fetches (host artifact,
  verified proxy-side, **not** scored against Heritrix; see `metadata-snapshot.md`).
- `observation` fields in the JSON are computed from run output (record counts,
  server hits, log timestamps); no conclusion strings are hardcoded.
- On-disk paths are redacted (`$HOME`→`~`, `$TMPDIR`/`/var/folders`→`<TMP>`).
- Gaps (cross-crawl recrawl dedup, scale/long-run, JS capture, sitemap-loc recall)
  are listed explicitly in `research-materials.md`.
