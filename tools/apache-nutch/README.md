# apache-nutch — evidence pack

Independent, reproducible tests for **Apache Nutch 1.22**, the JVM/Hadoop-based,
plugin-driven **batch web crawler**. Part of the Thunderbit open-source
scraping-tool benchmark. Focus (per queue): **crawl control + deployment cost**
relative to a modern single-binary crawler. Nutch is judged on discovery coverage +
crawl discipline + deployment cost — not structured-data or content extraction.

Every number in `research-materials.md` traces to a script in `tests/` and a JSON
artifact under `artifacts/raw/`. The fixture is the **same same-fixture used by the
katana pack** (three endpoint classes + server-side hit truth), so discovery
coverage is directly comparable across tools.

Tested (as-of 2026-07-24): Nutch **1.22** (bundled Hadoop **3.4.2**), OpenJDK
**17.0.20** (the host default **JDK 26.0.1 cannot run it** — see Headline), Python
3.14 harness, macOS 26.5 arm64.

## Headline

On the same ground truth katana was measured against, Nutch is a **browserless
static crawler whose JS-endpoint reach is a plugin toggle, not a browser**: default
coverage is class A (HTML) only; enabling `parse-js` recovers the JavaScript-file
literal endpoints (class B) **without a browser** (recall 0→1.0) — the parity of
katana `standard` → `standard -jc`; the runtime-DOM endpoint (class C) is reached by
neither and needs a JS-executing protocol (parity with `-headless`). **The dominant
net-new finding is deployment cost: the latest Nutch (1.22) cannot run on the host's
current JDK (26)** — its bundled Hadoop 3.4.2 is one patch below the JDK-24+ fix
(3.4.3/3.5.0), so `Subject.getSubject` (removed by JEP 486) kills the crawl before it
fetches a byte, and `-Djava.security.manager=allow` is itself rejected. A working
crawl needs an LTS downgrade (Java 17), a ≈395 MB / 188-jar / 78-plugin install, and a
batch cycle that is N fresh JVMs (~1.77 s startup floor each) — vs katana's single Go
binary and single process.

## Reproduce

```bash
# Nutch 1.x binary distribution unpacked somewhere OUTSIDE this pack:
export NUTCH_HOME=/path/to/apache-nutch-1.22
export NUTCH_JAVA_HOME=/opt/homebrew/opt/openjdk@17     # LTS <= 21 REQUIRED (JDK 24+ fails)

# 1) discovery matrix: default vs parse-js vs htmlunit probe; 3 repeats; ~5 min
python3 tests/run_discovery.py

# 2) deployment cost: JDK matrix + footprint + config-steps + per-phase timing
#    RUN ALONE (timing-sensitive); ~75 s
JDK_NEW_HOME=/opt/homebrew/opt/openjdk JDK_LTS_HOME=/opt/homebrew/opt/openjdk@17 \
  python3 tests/run_deployment_cost.py

# 3) scope + depth (depth==rounds, 3 scope scenarios); ~3 min
python3 tests/run_scope.py

# 4) robustness + sitemap + politeness; ~3 min
python3 tests/run_robustness.py
```

Harnesses are Python-3 stdlib only (no pip deps). The fixture
(`tests/fixture_server.py`) binds `127.0.0.1` on a random port and defines every
discoverable path, so recall is measured against a known set — never guessed. All
crawl state (crawldb/segments) is created under an OS temp dir **outside** this pack
and cleaned up; artifacts land in `artifacts/raw/*.json` (per-run stdout under
`artifacts/logs/`, gitignored).

## What the pack establishes

- **JDK block (headline):** Nutch 1.22 `inject` fails on JDK 26 (`getSubject is not
  supported`); works on JDK 17. Bundled Hadoop 3.4.2 is one patch below the fix.
- **Coverage:** default = class A only; `parse-js` recovers class B 2/2 browserless
  (deterministic across 3 repeats); class C unreached by any static config.
- **Crawl control:** depth == number of rounds; shipped default (`db.ignore.external
  .links=false`) **follows** external hosts — scope is opt-in via that flag or a host
  `regex-urlfilter`.
- **Deployment cost:** ≈395 MB / 188 jars / 78 plugins; empty `http.agent.name`
  refuses the first fetch; one round ≈12.1 s (N fresh JVMs, ~1.77 s floor).
- **Robustness / known-files / politeness:** crawl survives 500 (`db_unfetched`) and
  404 (`db_gone`); normal crawl ignores sitemap (0/2) but `bin/nutch sitemap` injects
  2/2; `fetcher.server.delay` honored.

## Pack contents

- `pretest-information-gain.md` — SERP/consensus scan, gap, hypotheses, gate verdict.
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check, gaps.
- `scorecard.md` — provisional dimension scores (65/100), evidence-anchored.
- `metadata-snapshot.md` — versions, JDK matrix, exact commands, reproducibility.
- `tests/` — `fixture_server.py` + `nutch_driver.py` + four runners.
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout (gitignored).

Evidence phase only: no article, no publishing. Independent audit (`validation.md`)
is produced separately and is not part of this worker's deliverable.
