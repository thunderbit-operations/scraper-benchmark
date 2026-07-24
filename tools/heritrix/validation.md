# Heritrix — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

Independent audit of the Heritrix 3.16.0 archival-crawl-discipline pack (OpenJDK
26.0.1, macOS arm64). I re-ran the **entire** `tests/run_all.py` harness from
scratch with a managed engine (`-Djava.net.useSystemProxies=false`) — all five
concerns, both dedup arms, both robots arms, and **all 3×3 politeness runs** — and
**every headline reproduced** against ground truth / server-side hit counters. No
leak-class (D1–D4) issue, no evidence-integrity issue. Novelty labeling is
conservative and correct (nothing tagged exclusive — appropriate for this pack).
Secret / abspath / vendor scans are clean; the 41 MB release + all WARC/jobs output
are properly git-ignored. The 503→proxy attribution is **verified correct** and does
not move the score. Open items are cosmetic/precision only — **none touches a
headline number.**

---

## Required fixes before publishing (all cosmetic — no headline affected)

1. **Deployment-friction scorecard line leans on the explicitly-unscored host
   proxy.** `scorecard.md` row 10 justifies the 5/8 deployment score partly with
   "*host system-proxy needed a JVM flag*", yet the README, `research-materials.md`
   FINDING-06, and `metadata-snapshot.md` all state the proxy interaction is a host
   artifact **"not scored against Heritrix."** Citing it inside a scored dimension's
   evidence contradicts that quarantine. The score itself is **not** proxy-driven —
   the 41 MB / 142-jar Java distribution + Jetty + ~750-line Spring `crawler-beans.cxml`
   fully justify 5/8 on their own — so the fix is wording only: drop the proxy clause
   from the scored rationale (leave it in the honesty note where it belongs). I did
   **not** edit the scorecard myself (it is score-adjacent, outside an auditor's
   cosmetic remit); the writer should apply. Score/weight unchanged.

2. **"honest/honestly" section headers** (`metadata-snapshot.md` "recorded honestly"
   / "Reproducibility notes (honest)"; `research-materials.md` "Gaps … (honest)").
   Borderline-descriptive (they name disclosure discipline, not a self-awarded
   quality) and evidence-phase only, so **not a blocker** — but zero the adjectives in
   any final draft per methodology D12 (same call the katana audit made).

Writer-caveats (leave as measured, do not overclaim):

- **Scope test is single-armed.** Unlike the katana sibling (which had a widened-scope
  positive control giving `page_out_hits: 1`), the Heritrix scope concern runs only
  the default-scope arm. "0 out-of-scope hits" is adequately distinguished from a mere
  reachability failure by `secondary_appeared_in_crawl_log: false` (scope-rejected at
  discovery, never queued) **plus** `in_scope_page_a_hits: 1` (the crawler was alive
  and following links from that same seed page) — so the finding stands, but it is
  one control short of full katana parity. Frame as documented-design + parity result,
  not as an adversarial two-arm proof.
- **"Dedup is write-time, bandwidth unchanged."** Correct and doc-grounded (a
  content-digest `revisit` is post-fetch by definition), but this pack has **no
  dup-arm server-hit counter** proving both `/dup/*` URLs were still fetched under the
  dedup-enabled config — it is inferred from WARC semantics, not measured here. Keep
  it as a mechanism note, not a measured result.

---

## Independent reproduction (my full re-run of `tests/run_all.py`)

All 12 jobs completed (`warc-fidelity`, `dedup-default`, `dedup-enabled`,
`scope-default`, `polite-{default,zero}×3`, `robots-{obey,ignore}`). Engine reported
`heritrixVersion 3.16.0` on OpenJDK 26.0.1 — **boots + serves REST + crawls on JDK 26
with no `--add-opens`/preview flags**, confirming FINDING-06.

### H1 — WARC record fidelity — **reproduced identically**

| field | worker | my re-run |
|---|---|---|
| `record_type_counts` | warcinfo 1 / response 20 / request 20 / metadata 20 | **identical** |
| `responses_with_payload_digest` | 20/20 (`sha1:`) | **20/20** |
| `responses_with_ip` | 20/20 | **20/20** |
| `requests_concurrent_to_a_response` | 20/20 | **20/20** |
| status lines | 200 / 404 / 500 | **200 / 404 / 500** |

Opened the WARC via the harness parser and confirmed the 1:1:1 response/request/
metadata multiplicity, `sha1:` payload digests, `WARC-IP-Address`, and full
`WARC-Concurrent-To` linkage. The three dedup bean classes referenced by
`enable_dedup` (`BdbContentDigestHistory`, `ContentDigestHistoryLoader`,
`ContentDigestHistoryStorer`) exist in `heritrix-modules-3.16.0.jar` (verified).

### H2 — content-digest dedup (two arms) — **reproduced identically** (the adversarial headline)

| arm | `dup_response` | `dup_revisit` | shared digest | revisit profile |
|---|:--:|:--:|:--:|---|
| **default** | **2** | **0** | 2 | — |
| **dedup chain enabled** | **1** | **1** | 1 | `…/revisit/identical-payload-digest` |

The stock default profile writes the byte-identical body **twice, in full, 0
revisit**; adding the `ContentDigestHistory` loader/storer chain converts the second
capture into a WARC `revisit`. Exactly as claimed.

### H3 — SURT scope discipline (server-side truth) — **reproduced**

`page_out_hits_on_secondary = 0` (out-of-scope host's own counter never incremented),
`in_scope_page_a_hits = 1`, `secondary_appeared_in_crawl_log = false`. **Katana
parity confirmed:** katana `artifacts/raw/scope-summary.json`
(`default_excludes_out_of_scope_host: true`, `page_out_hits: 0`) and Heritrix here
both keep the default crawl on the seed host with **0** out-of-scope fetches — the
parity pointer is a real artifact, not a phantom.

### H4 — politeness floor — **reproduced (and validates the pack's framing choice)**

| | worker | my re-run |
|---|---|---|
| default same-host gap median | 3036 ms | **3041 ms** (≈ `minDelayMs` 3000) |
| default wall median | 57 663 ms | **57 777 ms** |
| zero-politeness wall median | 27 ms | **35 ms** |
| wall-time multiplier | 2135.7 | **1650.8** |

The **defensible** numbers — the ~3.0 s per-host floor and the ~57.7 s absolute crawl
span — reproduced tightly. The multiplier differs (2135.7 → 1650.8) **only because
the zero-politeness denominator is tens of ms and unstable run-to-run** — which is
precisely the "denominator-sensitive" caveat the pack itself raised. This *validates*
the worker's decision to headline the absolute floor rather than the ratio. Note the
multiplier is never bolded and never used as a headline anywhere in the pack.

### H5 — robots obedience (paired control) — **reproduced**

Obey: `denied_path_server_hits = 0`, `robots_txt_fetched = true`,
`denied_in_crawl_log_as_blocked = true`. Ignore control:
`denied_path_server_hits = 1`. The `Disallow` genuinely suppresses the fetch
(server-side proof), and the ignore policy reaches it.

_My reproduction overwrote `artifacts/raw/*.json`; **all observation booleans matched
the worker's exactly** (only the multiplier float drifted, per above). I restored the
worker's originals so the committed md text ↔ JSON stay consistent._

---

## 503 → Surge proxy attribution — **verified correct, and not scored**

The host **does** run a Surge system proxy — `scutil --proxy` → `HTTPProxy
127.0.0.1:6152`, live `LISTEN` (PID 87241). I reproduced the mechanism directly with
raw sockets against a live fixture:

- **Direct raw-socket** to the loopback fixture → `HTTP/1.0 200 OK` (fixture is
  reachable; not the fixture's fault).
- **Identical request routed through Surge (127.0.0.1:6152)** → `HTTP/1.1 503 Service
  Unavailable`.

So the 503s Heritrix's Java client saw are the **proxy's**, not Heritrix's, and
`-Djava.net.useSystemProxies=false` is the correct remedy — the worker's raw-socket
attribution is accurate. My managed-engine re-run used that flag and got 20 clean
fetches (0×503). **Not-scored check:** substantively the proxy does not move any
number — the crawl-success dimensions (WARC fidelity 14/14, etc.) are unaffected, and
the deployment score of 5/8 is fully justified by Heritrix-intrinsic friction. The
only place the artifact leaks into a *scored* line is the wording in fix #1 above.

---

## Four leak-classes (Part 6)

- **D1 — self-contradicting winner sentence: PASS.** Scorecard sums cleanly (weights
  = 100, scores = 85). No "Heritrix wins/best" sentence — the pack is role-scoped to
  archival discipline. Dedup is *marked down* (8/12) for the default duplicate write,
  not spun as a win. The one comparative ratio (politeness multiplier) is explicitly
  hedged and never bolded; headlines use absolute values (3.0 s floor, 57.7 s).
- **D2 — blind instrument: PASS.** Politeness timer proves sub-second sensitivity via
  the zero-politeness positive control (median gap 2 ms, wall 27–35 ms) — it is not
  blind. Scope/robots/dedup all use **server-side hit counters or WARC record counts**
  (fetch-truth), not Heritrix stdout. Robots and dedup each carry a paired
  positive/negative control; scope carries only the default arm (writer-caveat above).
- **D3 — mis-attribution: PASS.** The one attribution risk (503) is independently
  verified proxy-side (raw-socket, above), and the fixture is `HardenedFixtureServer`
  with a deep backlog so connection drops don't confound. No measured Heritrix
  behavior is misattributed.
- **D4 — claim-without-artifact: PASS.** Spot-checked 6 headline numbers → JSON
  fields: record counts → `warc-fidelity.json.record_type_counts`; 20/20 digest+IP+
  concurrent → same file; dedup 2/0 → 1/1 → `dedup.json.default`/`.dedup_enabled`;
  gap 3036 ms / 57.7 s → `politeness.json`; scope 0 → `scope.json.page_out_hits_on_secondary`;
  robots 0/1 → `robots.json`. All resolve. The only un-metered claim is the dedup
  "bandwidth unchanged" mechanism note (writer-caveat above).

## Novelty (three-gate) — appropriately DOCUMENTED

All six findings are tagged **"Documented → quantified"** (or documented-design →
quantified/parity); **none** is claimed exclusive/undocumented. This is the correct
posture for this pack — the contribution is first-party quantification on shared
ground truth + katana parity, not a secret-behavior claim. The underlying facts
(request/response/metadata WARC records; `skipIdenticalDigests=false` + dedup needs
the `ContentDigestHistory` beans; default SURT scope excludes other hosts; the
delay-factor/minDelay formula; robots-obey default; "Java 17+") are all genuinely
documented Heritrix behavior. **No novelty inflation** — the gate's failure mode
(crowning documented behavior as exclusive) is absent by construction.

## Hardcoding lint — PASS

Every `observation` field is a boolean/float computed from run output: WARC counts
from the parser, dup stats from `Counter`, gaps from log timestamps, scope/robots
from the live server-side `_HITS` counter, multiplier from `dm/zm`. No literal result
constant (`20`, `3036`, `2135.7`, `0`, `1`) is written into the harness. The endpoint
sets in `fixture_server.py` are legitimately **pre-registered ground truth**
(methodology Part 3), not stored outcomes.

## Secret / abspath / vendor scan — CLEAN

- **Credentials: clean.** No API keys, tokens, private-key blocks in any
  publish-bound file (`*.md`, `tests/*.py`, `artifacts/raw/*.json`). `admin:admin` is
  the documented default for a throwaway local engine, not a secret.
- **Absolute paths: clean.** No `/Users/richardli`, `/var/folders`, `/private/var`,
  or `/tmp/` in the publish set — the `redact()` helper folds `$HOME`→`~` and
  `$TMPDIR`→`<TMP>` (verified: `warc-fidelity.json.launch_dir` reads `~/…`).
- **Proxy address:** `127.0.0.1:6152` / "Surge" appears only in the 3 intentional
  honesty-disclosure spots — a loopback address, not a secret.
- **Vendor / WARC / jobs not in publish set.** Publish-bound files total **112 K**;
  the 41 MB release + `heritrix-3.16.0/jobs/` (WARC output) are covered by
  `.gitignore` (`vendor/`, `heritrix-*/`, `*.warc.gz`, `jobs/`, `**/logs/`, `.venv/`).
  No stray WARC/jobs/logs exist outside the git-ignored `vendor/`.

---

## Cleanup

Engine JVM exited (no `heritrix`/`org.archive` process; port 8443 free). My re-run's
crawl output (`vendor/heritrix-3.16.0/jobs/*`, 2.2 MB across the 12 jobs, +
`engine-boot.log`) was removed by **exact-path `rm` inside the git-ignored `vendor/`
dir** — no `pkill -f fixture_server.py` was ever used, so no parallel worker's fixture
(nutch/archivebox/browsertrix/browserless) was touched. No stray harness python. The
committed `artifacts/raw/*.json` hold the worker's original numbers (restored after my
verifying re-run).

**Net status: PASS WITH FIXES.** All five headlines reproduced independently against
ground truth / server-side truth; the 503→Surge attribution is verified correct and
does not move the score; novelty is conservatively DOCUMENTED; hardcoding, secret,
abspath, and vendor scans are clean. The only open items are one wording
inconsistency in the deployment-friction evidence line (fix #1) and final-draft
adjective hygiene (fix #2) — neither alters a measured value.

_Audit re-ran `tests/run_all.py` end-to-end on 2026-07-24 with a managed engine;
raw-socket proxy check run separately. Auditor-generated WARC/jobs cleaned; worker
artifacts restored; no lingering processes._
