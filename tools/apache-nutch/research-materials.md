# apache-nutch — evidence pack (research materials)

Independent, reproducible tests for **Apache Nutch 1.22**, the JVM/Hadoop-based,
plugin-driven batch crawler, on the **same controlled fixture** used by the katana
pack (three endpoint classes A/B/C + server-side hit truth). Focus (per queue):
**crawl control + deployment cost** relative to a modern single-binary crawler.

Tested: Nutch **1.22** (bundled Hadoop **3.4.2**), OpenJDK **17.0.20** (the host
default JDK 26.0.1 **cannot run it** — FINDING-01), Python 3.14 harness, macOS 26.5
arm64, **2026-07-24**. Every number below traces to a script in `tests/` and a JSON
under `artifacts/raw/`. Confidence is tagged per finding: *3× repeat* / *single
observation* / *inference*.

---

## Headline

On the same ground truth katana was measured against, Nutch behaves as a
**browserless static crawler whose JS-endpoint reach is a plugin toggle, not a
browser**: default coverage is class A only; enabling `parse-js` recovers the
JavaScript-file-literal endpoints (class B) **without a browser** (recall 0→1.0),
exactly the parity of katana `standard` → `standard -jc`; the runtime-DOM endpoint
(class C) is reached by neither and needs a JS-executing protocol (parity with
`-headless`). **But the dominant, net-new finding is deployment cost: the latest
Nutch release (1.22, 2025-07-20) cannot run at all on the host's current JDK (26).**
Its bundled Hadoop 3.4.2 sits **one patch below** the fix (Hadoop 3.4.3/3.5.0), so
`UserGroupInformation.getCurrentUser()` hits the JDK-24-removed `Subject.getSubject`
and the crawl cycle dies before fetching a byte; the `-Djava.security.manager=allow`
escape hatch is itself rejected by the VM. A working crawl requires downgrading to an
LTS (Java 17), then paying a ~395 MB / 188-jar / 78-plugin install and a batch cycle
that is **N fresh JVMs** (~1.77 s startup floor each) — against katana's single Go
binary and single process.

---

## FINDING-01 — Latest Nutch cannot run on the current JDK; forced LTS downgrade (headline)

**Measurement** (`run_deployment_cost.py`, `deployment-cost-summary.json` → `jdk_matrix`):

| JDK | invocation | result |
|---|---|---|
| **26.0.1** (host default) | `bin/nutch inject` | **FAIL** rc=255 — `java.lang.UnsupportedOperationException: getSubject is not supported` at `hadoop.security.UserGroupInformation.getCurrentUser` |
| **26.0.1** | `+ -Djava.security.manager=allow` | **FAIL** rc=1 — VM refuses to start: `Enabling a Security Manager is not supported` |
| **17.0.20** (LTS) | `bin/nutch inject` | **OK** rc=0 — `Total new urls injected: 1` |

The crawl cycle initialises a Hadoop `LocalJobRunner`; the very first job
(`inject`) calls `UserGroupInformation.getCurrentUser()` → `Subject.getSubject()`,
which JDK 24 removed (JEP 486 SecurityManager removal) and which now throws
unconditionally. The historical `-Djava.security.manager=allow` bridge is also gone:
the VM aborts at init. Nutch 1.22 bundles **hadoop-common-3.4.2** (all 13
`hadoop-*-3.4.2.jar`); the upstream fix that moves off `Subject.getSubject` landed in
**Hadoop 3.4.3 and 3.5.0** — Nutch 1.22 is exactly one patch below it.

**Confidence:** single observation per JDK, but each is a deterministic hard error
with the exact stack captured (`artifacts/logs/jdk_probe_*.log`).

**Novelty:** the *root cause* (`getSubject` on JDK 24+ in Hadoop UGI) is a **known
Hadoop issue** — HADOOP-19212, HADOOP-19486, HDFS-17778, fixed in 3.4.3/3.5.0.
**EXCLUSIVE** here: tying it to a *specific Nutch release* — Nutch **1.22 ships
Hadoop 3.4.2, one patch under the fix, so the latest Nutch is unrunnable on JDK 24+
and the security-manager escape hatch is dead** — a Nutch-level statement absent from
the SERP (searches for Nutch + getSubject return only Hadoop/Artemis, "no specific
references to Apache Nutch").

---

## FINDING-02 — Coverage split: `parse-js` recovers JS-literal endpoints without a browser (parity with katana `-jc`)

**Measurement** (`run_discovery.py`, `discovery-summary.json`; per-class recall from
server-side fetch truth, 3 independent process repeats):

| Scenario (plugin.includes) | class A (HTML) | class B (JS-literal) | class C (runtime-DOM) |
|---|---:|---:|---:|
| **default** (`parse-(html\|tika)`) | **1.0** (4/4) | **0.0** (0/2) | **not found** |
| **parse-js** (`parse-(html\|tika\|js)`) | **1.0** (4/4) | **1.0** (2/2) | **not found** |

Both class-B endpoints — `fetch('/api/js-endpoint-7')` and `const other =
"/api/js-endpoint-8"` inside the linked `app.js` — are fetched once `parse-js` is
enabled, confirming the regex heuristic catches both a call-argument literal and an
assignment literal. `app.js` itself is fetched in both scenarios (Nutch extracts
`<script src>` as an outlink), so the delta is purely the JS **content** scan.
Result is **identical across all 3 repeats** (`coverage_deterministic: true`).

**Parity with katana (same fixture):** Nutch `default` == katana `standard` (A only);
Nutch `parse-js` == katana `standard -jc` (A+B, browserless JS-literal recovery via
regex — Nutch's is "two-pass regex, idea from Heritrix," katana's is jsluice); class
C needs a JS-executing protocol just as katana needs `-headless`. Cross-tool note:
katana's `-jc` went **inert under `-headless`** (0/2); Nutch's `parse-js` is not mode-
gated — it recovers B whenever enabled.

**Confidence:** 3× repeat, deterministic.

**Novelty:** the `parse-js` plugin and its exclusion from the default `plugin.includes`
are **DOCUMENTED** (Nutch wiki AboutPlugins; `nutch-default.xml`). **EXCLUSIVE:** the
quantified per-class recall on shared ground truth and the explicit standard/`-jc`/
`-headless` parity mapping to a modern crawler.

---

## FINDING-03 — The runtime-DOM class needs a JS-executing protocol; `protocol-htmlunit` is not drop-in (bounded probe)

**Measurement** (`run_discovery.py` → `scenario_htmlunit_probe`): swapping
`protocol-http` → `protocol-htmlunit` (Nutch's pure-Java JS-executing protocol) loaded
and ran without crashing, but in the same 4-round harness that gives `parse-html` full
class-A coverage it **completed only 1 round**, fetched only the seed `/` and (as a
render side-effect) `app.js`, and reached **none** of A/B/C; round-2 `generate` reported
`0 records selected for fetching` (`artifacts/logs/htmlunit_generate_2.log`).

**Interpretation (scoped):** this is a **bounded, under-configured probe, not a verdict
on HtmlUnit's capability.** It establishes only that the runtime-DOM class (C) is **not
reachable by any out-of-the-box static plugin set, and swapping in the JS protocol is
not a drop-in** — it needs additional tuning that was not pursued (design boundary; not
measured to completion). Class C therefore stays *unreached* in every configuration
tested here.

**Confidence:** single observation, explicitly hedged.

**Novelty:** "a browserless crawler can't run JS; use protocol-selenium/htmlunit" is
**DOCUMENTED**. The measured non-drop-in behavior is a minor **EXCLUSIVE** observation,
scoped as above.

---

## FINDING-04 — Crawl depth is the number of rounds (one level per round)

**Measurement** (`run_scope.py` → `depth`): the chain `/depth/1 → /depth/2 → /depth/3`
is fetched exactly one level deeper per round:

| rounds run | deepest depth-chain URL fetched |
|---:|---|
| 2 | `/depth/1` |
| 3 | `/depth/2` |
| 4 | `/depth/3` |

`depth_equals_rounds: true`. Nutch has no single `--depth N` flag; depth is controlled
by how many `generate→fetch→parse→updatedb` rounds you run (round R fetches the frontier
discovered at round R-1). This is a per-round cost multiplier for FINDING-07.

**Confidence:** single observation, but monotonic and mechanistically clean.

**Novelty:** **DOCUMENTED** (well-known Nutch batch semantics); measured here for
completeness and to anchor the cost model.

---

## FINDING-05 — The shipped default follows external links (out of scope); scope is opt-in

**Measurement** (`run_scope.py` → `scope`; judged from Nutch's own crawldb **and** the
out-of-scope host's server-side counter, which agree):

| config | out-of-scope host status | fetched? |
|---|---|---|
| `db.ignore.external.links=false` (**shipped default**) | crawldb `db_fetched` + secondary hit +1 | **YES — out of scope** |
| `db.ignore.external.links=true` | crawldb `absent` + secondary +0 | no |
| host `regex-urlfilter` (`+^http://127.0.0.1:` / `-.`) | crawldb `absent` + secondary +0 | no |

Seeded from a page linking one in-scope path and one link to a **different host**
(`localhost` vs the crawl's `127.0.0.1`), the shipped-default crawl fetched the foreign
host. Staying in scope is **opt-in**: set `db.ignore.external.links=true` **or** add a
host `regex-urlfilter` rule. Both mechanisms fully block it (crawldb + server agree).

**Confidence:** single observation, cross-checked by two independent signals (crawldb
status and a separate server-process hit counter). **Run in isolation:** this probe must
be run on its own — sharing the secondary fixture with a concurrent `discovery` run causes
a transient round-2 fetch failure that flips the out-of-scope link to `db_unfetched` (a
load artifact of the shared local server, not Nutch scope behavior). The two-signal design
stays self-consistent either way; the reported result is the isolated single-run.

**Novelty:** the default value `false` is **DOCUMENTED** in `nutch-default.xml`.
**EXCLUSIVE:** the demonstrated on-ground-truth consequence — a default Nutch crawl
leaves the seed host — and that both remedies verifiably contain it.

---

## FINDING-06 — Deployment footprint and the mandatory first-fetch config step

**Measurement** (`run_deployment_cost.py` → `footprint`, `config_steps`):

- Unpacked distribution **≈ 395 MB**; `lib/` = **188 jars / ≈ 113 MB** (of which 13 are
  bundled Hadoop 3.4.2 + shaded guava/protobuf); **78 plugin dirs**; **35 conf files**.
  Comparator: katana is a single Go binary (~50 MB, no JVM, 0 external jars).
- **First fetch is refused out of the box.** The shipped `nutch-site.xml` is empty and
  `http.agent.name` defaults to `""`; a crawl with it unset fetched **0 paths** and
  logged `ERROR Fetcher: No agents listed in 'http.agent.name' property.` Setting
  `http.agent.name` alone flips it to a working fetch (home + robots fetched).
- Minimal working config = 3 artifacts: `conf/nutch-site.xml` (agent name + plugin set
  + scope), `conf/regex-urlfilter.txt` (host scope), and a seed URL file.

**Confidence:** single observation (deterministic filesystem + a proven refusal log).

**Novelty:** "Nutch is heavyweight / complex" is **DOCUMENTED** qualitatively.
**EXCLUSIVE:** the specific counts (395 MB / 188 jars / 78 plugins / 35 conf) and the
demonstrated empty-`http.agent.name` fetch refusal as a concrete first-run gate.

---

## FINDING-07 — The batch cycle is N fresh JVMs; most wall time is process startup

**Measurement** (`run_deployment_cost.py` → `per_phase_timing`, 3 runs):

| phase (per round) | p50 seconds |
|---|---:|
| inject (once) | 1.81 |
| generate | 3.93 |
| fetch | 2.82 |
| parse | 1.78 |
| updatedb | 1.81 |
| **one round total** | **12.14** |

Effective **per-job JVM+Hadoop-init floor ≈ 1.77 s** (the cheapest trivial-work phase;
`bin/nutch` with no command is bash-only at ~0.004 s and does **not** start a JVM — it
is not the floor). Each round launches a **fresh JVM per command** (generate, fetch,
parse, updatedb), so a depth-4 crawl of this tiny fixture is `inject + 4 rounds` ≈
**~45 s** (observed in the discovery crawls: default 45.8 s, parse-js 45.0 s) —
dominated by ~17 JVM starts, not by fetching. On the same fixture katana's whole
`standard` crawl is a single ~13 s process (katana pack). The gap is architectural
(batch/JVM/Hadoop vs one native binary), not throughput of any single fetch.

**Confidence:** 3× repeat with min/p50/max reported; low variance
(one-round total 12.14–12.22 s).

**Novelty:** overhead expectation is **DOCUMENTED** qualitatively; the measured floor
(~1.77 s/JVM), per-phase distribution, and the "~45 s vs ~13 s same-fixture" figure are
**EXCLUSIVE**.

---

## FINDING-08 — Robustness: crawl continues past 500 and 404 with distinct status each

**Measurement** (`run_robustness.py` → `robustness`): a 3-round crawl over a home page
linking `/failure/500` (HTTP 500) and `/broken-xyz` (404) completed all rounds with
every non-`generate` phase rc=0, all four class-A pages fetched, and each error URL
carrying a distinct crawldb record:

| URL | crawldb status | protocol code |
|---|---|---|
| `/failure/500` | `db_unfetched` | 500 |
| `/broken-xyz` | `db_gone` | 404 |

The 500 is kept as `db_unfetched` (eligible for retry); the 404 is marked `db_gone`.
The crawl is not derailed by either.

**Confidence:** single observation, deterministic.

**Novelty:** **DOCUMENTED** (standard crawler resilience); the exact status/protocol
mapping on ground truth is a minor **EXCLUSIVE** quantification.

---

## FINDING-09 — A normal crawl does not consume sitemap.xml; it is a separate `bin/nutch sitemap` step (parity contrast with katana `-kf`)

**Measurement** (`run_robustness.py` → `sitemap_behavior`):

- **Normal crawl:** `/robots.txt` fetched (politeness), but `/sitemap.xml` **not**
  fetched and **0/2** sitemap-only `<loc>` endpoints reached — `auto_consumes_sitemap:
  false`.
- **`bin/nutch sitemap <crawldb> -sitemapUrls …`:** rc=0, fetches `/sitemap.xml`, and
  injects **2/2** `<loc>` endpoints into the crawldb — **recall 1.0**.

Parity contrast: katana's `-kf` requests robots/sitemap **inside** a normal crawl (but
on the same fixture recovered **0/2** `<loc>` on an IP host due to its RootHostname
bug); Nutch **separates** sitemap ingestion into an explicit command that achieves
**full** recall — a different crawl-control model (extra step, but it works).

**Confidence:** single observation, deterministic.

**Novelty:** the separate `sitemap` command is **DOCUMENTED**. **EXCLUSIVE:** the
measured "normal crawl ignores sitemap (0/2) vs command 2/2" split and the side-by-side
parity contrast with katana `-kf`.

---

## FINDING-10 — `fetcher.server.delay` is honored (server-side timing)

**Measurement** (`run_robustness.py` → `politeness`; inter-fetch gaps to the same host
from the fixture's own timestamps, `fetcher.threads.per.queue=1`):

| delay setting | min gap | median gap |
|---:|---:|---:|
| 0.0 s | 0.002 s | 0.002 s |
| 1.0 s | 1.006 s | 1.009 s |

With the delay set, consecutive same-host fetches are spaced ≥ the configured value;
`delay_is_honored: true`. (The shipped default is 5.0 s, set to 0.0 elsewhere in this
pack so it doesn't dominate wall time.)

**Confidence:** single observation; the min-gap ≥ setting is a clean signal.

**Novelty:** **DOCUMENTED** (documented knob); measured confirmation on ground truth.

---

## Novelty summary table

| Finding | Claim | Class | Evidence / upstream |
|---|---|---|---|
| 01 | Nutch 1.22 (Hadoop 3.4.2) can't run on JDK 24+; secmgr escape rejected; LTS forced | **EXCLUSIVE** (Nutch-specific) + KNOWN-ISSUE (Hadoop) | measured `jdk_matrix`; HADOOP-19212/19486, HDFS-17778 (fixed 3.4.3/3.5.0) |
| 02 | default=A-only; parse-js recovers B (0→1.0) browserless; C unreached | mechanism DOCUMENTED, quantification+parity **EXCLUSIVE** | `discovery-summary.json`, AboutPlugins wiki |
| 03 | protocol-htmlunit not drop-in; C unreached in all tested configs | DOCUMENTED (+minor EXCLUSIVE, hedged) | `scenario_htmlunit_probe` |
| 04 | depth == number of rounds | DOCUMENTED | `scope-summary.json` depth |
| 05 | shipped default follows external host; scope is opt-in | value DOCUMENTED, consequence **EXCLUSIVE** | crawldb + secondary agree |
| 06 | 395 MB/188 jars/78 plugins; empty http.agent.name refuses fetch | qualitative DOCUMENTED, counts **EXCLUSIVE** | `footprint`, `config_steps` |
| 07 | per-job JVM floor ~1.77 s; round ~12.1 s; depth-4 ~45 s vs katana ~13 s | expectation DOCUMENTED, numbers **EXCLUSIVE** | `per_phase_timing` |
| 08 | crawl survives 500(db_unfetched)/404(db_gone) | DOCUMENTED (+minor EXCLUSIVE) | `robustness` |
| 09 | normal crawl ignores sitemap 0/2; `bin/nutch sitemap` 2/2 | command DOCUMENTED, split+parity **EXCLUSIVE** | `sitemap_behavior` |
| 10 | fetcher.server.delay honored (median 1.009 s @ 1.0) | DOCUMENTED | `politeness` |

No finding is labeled "undocumented / nobody mentions." The one net-new headline
result (FINDING-01) is explicitly split into its known-at-Hadoop-level root cause and
its exclusive Nutch-1.22-specific quantification.

---

## Part-6 self-check (worker, pre-audit)

1. **Winner sentences vs own table:** the only cross-tool "gap" claims are the ~45 s vs
   ~13 s crawl (architectural, both numbers cited: Nutch `per_phase_timing` +
   discovery totals, katana pack) and coverage parity (recall table, exact). No
   "fastest/best" adjectives; differences reported as measured values, not verdicts.
2. **Every claimed cross-check has an artifact:** the JDK matrix, coverage, scope,
   footprint, timing, robustness, sitemap, and politeness numbers each come from a
   `tests/` runner and a named field in `artifacts/raw/*.json`; the scope "fetched"
   claim is corroborated by two independent signals (crawldb status **and** a separate
   server-process counter) after an earlier single-signal read proved fragile — the
   fragile signal was replaced, not trusted.
3. **Instrument calibrated before use:** the mislabeled "JVM floor" (bare `bin/nutch` =
   bash only, ~0.004 s, no JVM) was caught and replaced with the derived per-job floor
   (min trivial-work phase, ~1.77 s), and the artifact says so explicitly. Server-side
   hit truth was validated by the deterministic 3× coverage repeat.
4. **Attribution ruled out harness/fixture first:** the scope result was re-derived
   after confirming (a) the fixture actually serves the out-of-scope link and (b) the
   crawler's own crawldb marks it `db_fetched` — i.e. the initial `out_delta=0` was a
   cross-process HTTP-timing artifact of the *measurement*, not Nutch behavior; the
   corrected reading (default **does** follow external) is backed by Nutch's own record.
   The htmlunit non-result is scoped as an under-configured probe, not a capability
   verdict.
5. **Novelty tags + self-praise lint:** every finding carries a novelty class; the
   single EXCLUSIVE headline is split from its known Hadoop root cause. `grep -iE
   'honest|independent|strongest|trustworthy'` over the evidence prose surfaces only
   method-neutral **"independent"** ("two independent signals", "N independent process
   repeats" — instrument-independence, not a quality claim on Nutch); no self-awarded
   "honest / strongest / trustworthy" finding labels remain.

## Gaps / not tested

- **Solr indexing** (`index`/`clean`) — out of scope (discovery/cost focus); local
  mode covers inject→updatedb only.
- **protocol-htmlunit/selenium tuned** to actually render class C — not pursued
  (FINDING-03 is a bounded probe).
- **Distributed / HDFS mode**, `-resume`/hostdb, incremental re-crawl scheduling — not
  tested; all claims are **local-mode, single-host, tiny-fixture** on macOS arm64.
- **robots `Crawl-delay`** parsing (only the `fetcher.server.delay` knob was measured).
- Timings are macOS arm64 / JDK 17.0.20; absolute seconds will vary by host.
