# apache-nutch — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

Every headline claim reproduced independently on this host (Nutch **1.22** / bundled
Hadoop **3.4.2** / OpenJDK **26.0.1** + **17.0.20** / Python 3.14 / macOS arm64). I
**personally re-ran the JDK-block headline** (the pack's dominant net-new finding),
re-ran the **coverage** and **scope/depth** harnesses from scratch, and spot-verified
H4/H5 against committed logs. The coverage split, the JDK matrix, the footprint, and
(in a clean isolated run) the external-link-following scope finding all reproduce. No
leak-class (D1–D4) failure and no evidence-integrity problem. Novelty labeling is
accurate and conservatively hedged. Secret/abspath scan is **clean** and hygiene here
is **stronger than the katana sibling** (redacted JSON summaries + a correct
`.gitignore` + logs excluded; no package/jars/crawldb in the pack). The open items are
**cosmetic** (two self-descriptor adjectives — I fixed them in place) plus **one
reproducibility caveat** (the scope finding is load-sensitive; it needs the harness run
in isolation). **None touches a headline number.**

---

## Required fixes before publishing (none affect a headline)

1. **Scope finding (FINDING-05) is load-sensitive — add an isolation note / keep the
   hedge.** In my **first** scope re-run — which I ran *concurrently* with the
   discovery harness — the shipped-default external URL came back
   `external_url_crawldb_status = db_unfetched`, `secondary_out_hits_delta = 0`,
   `out_of_scope_host_fetched = false` (i.e. the crawl did **not** reach the foreign
   host). Re-running `run_scope.py` **alone**, it reproduced the worker's result
   exactly: `db_fetched` + secondary delta `1` → **follows external**. The cause is
   cross-process contention on the secondary `localhost` fixture (a transient round-2
   fetch failure), not a Nutch behavior change — and the pack's **dual-signal design
   held up**: both signals agreed in both runs (never a false positive). Fix owed: the
   finding is currently presented as a clean `db_fetched`; the writer should keep the
   existing "single observation" hedge **and** state that the scope harness must be run
   without concurrent load (the same "RUN ALONE" discipline the timing test already
   documents). The finding's *direction* (shipped default `db.ignore.external.links=false`
   + `+.` urlfilter follows external links; both remedies contain it) is mechanistically
   sound and correct.
2. **Self-descriptor adjectives (D12) — FIXED by auditor.** Two "(honest)" self-labels
   existed despite the Part-6 self-check claiming the lint "is clean": `Interpretation
   (honest)` (research-materials.md) → I changed to `(scoped)`; `## Reproducibility notes
   (honest)` (metadata-snapshot.md) → I dropped the `(honest)`. Remaining owed: the
   self-check item 5 wording ("grep … is clean") slightly **overstated** it — correct that
   sentence, and optionally neutralize `Novelty honesty:` (pretest-information-gain.md:119).
   All other `independent` occurrences are legitimate technical usage (independent
   *processes*, *signals*, *server counter*) — leave them.
3. **Metadata as-of refresh.** `metadata-snapshot.md` (stars 3,270 / release 1.22 /
   last push 2026-07-23) is dated 2026-07-24; refresh within 48 h of any final draft
   (the pack already says so).

---

## Independent reproduction (my re-runs)

### 1. JDK block (headline) — reproduced MANUALLY, exact stack

Ran `bin/nutch inject` directly under each JDK against the real Nutch 1.22 install
(`/private/tmp/claude-501/nutch-build/apache-nutch-1.22`, bundled `hadoop-common-3.4.2.jar`
confirmed):

| JDK | invocation | my result | pack |
|---|---|---|---|
| **26.0.1** | `inject` | **rc=255**, `java.lang.UnsupportedOperationException: getSubject is not supported` at `Subject.java:277` → `UserGroupInformation.getCurrentUser(...:588)` → `Injector.inject(...:473)` | ✓ identical |
| **26.0.1** | `+ -Djava.security.manager=allow` | **rc=1**, `A command line option has attempted to allow or enable the Security Manager. Enabling a Security Manager is not supported.` | ✓ identical |
| **17.0.20** | `inject` | **rc=0**, `Injector: Total new urls injected: 1` | ✓ identical |

My fresh JDK-26 stack matches the worker's committed `jdk_probe_jdk_new_plain.log`
line-for-line (same `Subject.java:277 / UGI:588 / Injector:473`). Attribution
(JEP 486 SecurityManager removal → `Subject.getSubject` throws; fixed in Hadoop
3.4.3/3.5.0 per HADOOP-19212/19486/HDFS-17778; Nutch 1.22 bundles 3.4.2 = one patch
below) is **accurate and reproduced**. The EXCLUSIVE half (Nutch-1.22-specific tie) is
grounded in the measured bundled version; the KNOWN-ISSUE half (Hadoop-level) is
correctly attributed. (I did not independently re-run the SERP "no Nutch-specific
reference" search — but the finding's measured core reproduces and is conservatively
split.)

### 2. Coverage H1/H2 — reproduced (full `run_discovery.py`, JDK 17, 3 repeats)

| Scenario | A html | A depth | B js-literal | C runtime-DOM | deterministic |
|---|---:|---:|:--:|:--:|:--:|
| **default** (`parse-(html\|tika)`) | 4/4 (1.0) | 3/3 | **0/2 (0.0)** | **not found** | — |
| **parse-js** (`parse-(html\|tika\|js)`) | 4/4 (1.0) | 3/3 | **2/2 (1.0)** | **not found** | — |
| across 3 repeats | | | 0.0→1.0 ×3 | no ×3 | **true** |

- `parsejs_recovers_B_without_browser = true`, `no_static_plugin_reaches_C = true`,
  `coverage_deterministic = true` — reproduced identically to the committed JSON.
- **Server-side fetch truth** (independent of Nutch stdout): the parse-js run fetched
  **both** `/api/js-endpoint-7` (the `fetch('…')` call-arg literal) **and**
  `/api/js-endpoint-8` (the `const x = "…"` assignment literal); the default run
  fetched **neither**. The class-B "catches both literal forms" claim holds on hit-truth.
- **htmlunit probe** reproduced as a bounded 1-round result (A 0.0, B 0.0, C false;
  only `/`, `/static/app.js`, `/robots.txt` fetched) — honestly scoped, not a verdict.
- **Katana parity** is accurate against katana's own audited numbers (`validation.md`):
  Nutch default == katana `standard` (A only, B 0/2); Nutch parse-js == katana
  `standard -jc` (A+B browserless); class C needs a JS-executing protocol as katana
  needs `-headless`. The cross-tool note that katana's `-jc` goes **inert under
  `-headless`** while Nutch's `parse-js` is not mode-gated is consistent with both packs.

*(Audit note: my first "done" detection was a false positive — `ps aux` truncates the
COMMAND column, so the harness looked finished when it was still mid-run; the summary is
written only at the end, so an early read returns the pre-existing file. I re-verified
via non-truncating `ps -ax -o command` and confirmed the JSON's `run_started_at` changed
before comparing. The numbers above are from the genuinely re-run output.)*

### 3. Scope + depth H3 — reproduced (isolated `run_scope.py`, JDK 17)

| Config | crawldb status of external URL | secondary hit Δ | out-of-scope fetched? |
|---|---|:--:|:--:|
| `db.ignore.external.links=false` (**shipped default**) | **db_fetched** | **1** | **YES** |
| `db.ignore.external.links=true` | absent | 0 | no |
| host `regex-urlfilter` (`+^http://127.0.0.1:` / `-.`) | absent | 0 | no |

Both containment signals agree; `shipped_default_stays_in_scope = false`. Depth:
`2→/depth/1, 3→/depth/2, 4→/depth/3`, `depth_equals_rounds = true` — reproduced.
(See required-fix #1 for the load-sensitivity caveat.)

### 4. Deployment cost / robustness / politeness (H4/H5) — verified

- **Footprint reproduced manually:** 188 lib jars, 78 plugin dirs, 35 conf files,
  `hadoop-common-3.4.2.jar`, ≈384–396 MB — matches `footprint`.
- **Config gate:** committed `cfg_empty_fetch_1.log` contains
  `ERROR Fetcher: No agents listed in 'http.agent.name' property.`; `cfg_ok` fetches
  home — backs `config_steps`.
- **Sitemap command:** committed `sm_cmd_sitemap.log` shows
  `Total new sitemap entries added: 2` (filtering/normalizing disabled, 0 failed
  fetches) — backs `loc_recall 1.0`.
- **JVM floor / robustness / politeness** taken from the internally-consistent
  artifacts (per the task's "cost/robustness re-run optional" allowance); the JVM-per-
  command architecture I witnessed directly (each `inject` ≈ 2 s under JDK 17).

---

## Leak-class findings (Part 6)

**D1 — self-contradicting winner sentence: PASS.** Scorecard weights sum to **100**,
scores to **65** (verified). The headline frames Nutch as the *heavier, slower* tool
(cannot run on host JDK; ≈395 MB; ~45 s depth-4 vs katana ~13 s) — Nutch **loses** every
cross-tool comparison, so there is no inflated winner sentence. Full marks appear only
where earned (static A 12/12 deterministic, robustness 6/6, politeness 6/6); every other
dimension is docked with a cited reason. The one Nutch-favorable contrast (sitemap
command 2/2 vs katana `-kf` 0/2 on the IP host) is measured, apples-to-apples on the same
fixture, and hedged ("extra step, but it works"). 65 is self-consistent — low but not
nihilistic.

**D2 — blind instrument: PASS.** Coverage/scope are judged from **server-side fetch
truth + crawldb**, independent of Nutch's own stdout. Politeness has a working positive
control: `delay=0.0 → 0.002 s` median gap (the instrument reads the near-zero floor),
`delay=1.0 → 1.009 s`. The 3× deterministic coverage repeat validates the hit-truth
instrument. The htmlunit non-result is disclosed as under-configured, not laundered.

**D3 — mis-attribution: PASS.** (a) The JDK-block root cause is reproduced at the exact
stack and the bundled Hadoop version is confirmed on disk — attribution is real, not
inferred. (b) **Both self-reported harness-bug fixes are correct:** the "JVM floor" is
now the derived min over trivial-work phases (**1.772 s**), with bare `bin/nutch`
(bash-only, 0.004 s, no JVM) explicitly separated and labeled "NOT the floor"; the scope
signal was re-keyed from a fragile cross-process HTTP delta to the **crawldb dual
signal** — I confirmed the code path and reproduced both signals agreeing. Neither fix
over-corrects.

**D4 — claim-without-artifact: PASS.** Spot-checked 10 headline numbers; all resolve to a
JSON field — coverage split (`coverage_contrast`), JVM floor
(`effective_per_job_jvm_floor_seconds=1.772`), scope `db_fetched`
(`scope.default_external_on`), footprint counts, 500→`db_unfetched`/404→`db_gone`
(`robustness`), sitemap `loc_recall=1.0`, delay `median 1.009`. The two un-artifacted
qualitative statements (htmlunit "not drop-in", heavyweight) are explicitly hedged/DOCUMENTED.

---

## Novelty classification (three-gate) — accurate

Only **FINDING-01's Nutch-1.22-specific quantification** (bundled Hadoop 3.4.2 one patch
below the fix ⇒ latest Nutch unrunnable on JDK 24+; secmgr escape dead) and the
**same-fixture parity numbers** (FINDING-02/05/06/07/09 quantifications) are labeled
**EXCLUSIVE**. Every *mechanism* — parse-js plugin + default exclusion, batch/round
depth model, the Hadoop-JDK `getSubject` root cause, `db.ignore.external.links=false`
default, heavyweight footprint (qualitative), the separate `bin/nutch sitemap` command,
`fetcher.server.delay` — is correctly **DOCUMENTED**. FINDING-01 is properly **split**
into KNOWN-ISSUE (Hadoop) + EXCLUSIVE (Nutch tie). No finding is labeled
"undocumented / nobody mentions." Classification matches the task's expected split.

## Anti-hardcoding lint: PASS

All conclusion fields are computed from run output: `class_recall` = set membership over
**pre-registered** ground-truth endpoint sets (methodology Part-3-endorsed, not hardcoded
results); `coverage_contrast`, `parsejs_recovers_B_without_browser`,
`no_static_plugin_reaches_C` from lambdas over measured recall; `depth_equals_rounds` from
a monotonic count check; scope `out_of_scope_host_fetched` from crawldb status OR secondary
delta; `effective_per_job_jvm_floor_seconds` = `min` over measured trivial phases; footprint
from filesystem `rglob`. No literal result constant (`0.0`, `2/2`, `1.772`, `12.1`) is
written into a harness.

## Secret / abspath / package scan: CLEAN

- **Credentials:** none (`sk-ant`/`sk-or`/`ghp_`/`AKIA`/`api_key`/`secret`/private-key — all clean).
- **Username / temp abspaths:** **no `/Users/richardli`**, no real `/var/folders` or
  `/private/tmp` paths in publish-bound files — JSON summaries fold them to `~`/`<TMP>`.
  The only absolute paths are generic Homebrew JDK locations
  (`/opt/homebrew/opt/openjdk[@17]`) in reproduction instructions — machine-generic,
  not user-identifying, **not a leak**.
- **Package / large binaries:** **none in the pack.** Total 2.6 MB (2.4 MB of that is the
  **gitignored** `artifacts/logs/`); no `apache-nutch-*/`, `*.jar`, `crawldb/`, or
  `segments/`. The 384 MB Nutch install lives in an OS temp dir outside the pack. The raw
  logs *do* carry absolute paths but are excluded by `.gitignore` (`*.log` +
  `artifacts/logs/`) with an explicit "JSON summaries carry the numbers" note — by design.
  **Hygiene is stronger than katana** (which shipped no `.gitignore` and leaked abspaths
  into committed raw JSON).

---

## Fixes applied by auditor (2026-07-24)

- `research-materials.md`: `**Interpretation (honest):**` → `**Interpretation (scoped):**`
- `metadata-snapshot.md`: `## Reproducibility notes (honest)` → `## Reproducibility notes`
- Restored the two overwritten raw JSONs (`discovery-summary.json`, `scope-summary.json`)
  to the worker's original committed bytes after confirming my re-runs matched; stopped all
  Nutch/Hadoop/fixture processes (precise PID kills only) and removed all temp crawl state.
  No headline, score, or artifact number was altered.

**Net status: PASS WITH FIXES.** All headlines reproduced by the independent audit
(JDK block re-run manually at the exact stack; coverage and scope/depth re-run from
scratch); the only open items are one reproducibility caveat (scope load-sensitivity)
and cosmetic adjective wording (already applied). Evidence integrity, novelty, anti-
hardcoding, and secret/package hygiene are clean.
