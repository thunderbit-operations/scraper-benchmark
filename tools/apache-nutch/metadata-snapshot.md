# apache-nutch — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [apache/nutch](https://github.com/apache/nutch) |
| Stars | **3,270** |
| Open issues | **8** |
| License | **Apache-2.0** |
| Default branch | **master** |
| Last push | **2026-07-23T19:31:32Z** |
| Latest release | **1.22**, released **2025-07-20** |
| Version tested | **1.22** (== latest release; binary dist `apache-nutch-1.22-bin.tar.gz`) |

## Environment actually used

| Item | Value |
|---|---|
| Nutch | **1.22** (binary distribution, unpacked to a temp dir) |
| Bundled Hadoop | **3.4.2** (all `hadoop-*-3.4.2.jar` under `lib/`) — one patch **below** the JDK-24+ fix (Hadoop 3.4.3 / 3.5.0) |
| JDK — host default | **OpenJDK 26.0.1** (Homebrew `openjdk`) → **crawl cycle BLOCKED** (see below) |
| JDK — working | **OpenJDK 17.0.20** (Homebrew `openjdk@17`, keg-only) → crawl cycle runs |
| Python (harness) | **3.14.2** (stdlib only; no third-party deps) |
| Platform | **macOS 26.5.2 arm64** (Darwin 25.5.0) |
| Test date | **2026-07-24** |

`openjdk@17` was installed keg-only via Homebrew (`brew install openjdk@17`); it is
**not** symlinked into the system Java wrappers and does not change the host default
JDK. All Nutch runs pass `NUTCH_JAVA_HOME=/opt/homebrew/opt/openjdk@17`.

## JDK compatibility (measured, `tests/run_deployment_cost.py`)

| JDK | invocation | result |
|---|---|---|
| **26.0.1** | `bin/nutch inject` | **FAIL** rc=255, `java.lang.UnsupportedOperationException: getSubject is not supported` (Hadoop `UserGroupInformation.getCurrentUser` → `Subject.getSubject`) |
| **26.0.1** | `+ -Djava.security.manager=allow` | **FAIL** rc=1, VM won't start: `A command line option has attempted to allow or enable the Security Manager. Enabling a Security Manager is not supported.` |
| **17.0.20** | `bin/nutch inject` | **OK** rc=0, `Total new urls injected: 1` |

Root cause is the JDK-24 SecurityManager removal (JEP 486); `Subject.getSubject`
throws unconditionally and the `-Djava.security.manager=allow` escape hatch is
itself rejected. Fixed upstream in Hadoop **3.4.3 / 3.5.0** (HADOOP-19212 /
HADOOP-19486 / HDFS-17778); Nutch 1.22 ships **3.4.2**.

## On-disk footprint (measured)

| Item | Value |
|---|---|
| Unpacked distribution | **≈ 395 MB** |
| `lib/` jars | **188** jars, **≈ 113 MB** |
| Bundled Hadoop jars | **13** (`hadoop-*-3.4.2` + shaded guava/protobuf) |
| Plugin dirs | **78** |
| `conf/` files | **35** |
| `bin/` scripts | `crawl`, `nutch` |

Comparator: katana ships as a single Go binary (~50 MB, no JVM, no external jars).

## Exact commands run

Nutch install is taken from `$NUTCH_HOME`; JDK from `$NUTCH_JAVA_HOME`. The fixture
(`tests/fixture_server.py`, reused from the katana pack — three endpoint classes +
server-side hit truth) binds `127.0.0.1` on a random free port. All crawl state
(crawldb/segments) is created under an OS temp dir **outside** this pack.

```bash
export NUTCH_HOME=/path/to/apache-nutch-1.22
export NUTCH_JAVA_HOME=/opt/homebrew/opt/openjdk@17     # LTS <= 21 required

# 1) discovery matrix: default vs parse-js vs htmlunit probe; 3 repeats; ~5 min
python3 tests/run_discovery.py

# 2) deployment cost: JDK matrix (needs JDK_NEW_HOME + JDK_LTS_HOME), footprint,
#    config-steps, per-phase timing (>=3 runs) — RUN ALONE (timing); ~75 s
JDK_NEW_HOME=/opt/homebrew/opt/openjdk JDK_LTS_HOME=/opt/homebrew/opt/openjdk@17 \
  python3 tests/run_deployment_cost.py

# 3) scope + depth: depth==rounds (rounds 2/3/4) + 3 scope scenarios; ~3 min
python3 tests/run_scope.py

# 4) robustness + sitemap + politeness; ~3 min
python3 tests/run_robustness.py
```

Each crawl round is `generate → fetch → parse → updatedb` (after an initial
`inject`); segment path is the newest dir under `segments/`.

## Reproducibility notes

- **A JDK ≤ 21 (LTS) is mandatory.** On the host default JDK 26 the crawl cannot
  run at all; results were produced on `openjdk@17`. Nutch's own README/CI target
  Java 17.
- **`http.agent.name` must be set** or the fetcher refuses (`ERROR Fetcher: No
  agents listed in 'http.agent.name'`). The shipped `nutch-site.xml` is empty.
- **Scenario configs** are built by copying the shipped `conf/` into a temp dir and
  overwriting `nutch-site.xml` (+ `regex-urlfilter.txt`), passed via
  `NUTCH_CONF_DIR`. `fetcher.server.delay` is set to `0.0` for non-politeness tests
  to avoid the shipped 5.0 s per-request wait dominating wall time.
- **Path redaction**: every artifact folds `$HOME`→`~` and the OS temp root
  (`$TMPDIR` / `/var/folders` / `/private/tmp`)→`<TMP>` before writing.
- **Native-access warning**: on JDK 17 the run also prints Hadoop's
  `System::loadLibrary` restricted-method warning; it is a warning only and does
  not affect local-mode results.
- **Cleanup**: fixture servers are stopped and all temp crawl dirs removed at the
  end of every harness; no Nutch package, crawldb, or segment is committed.
