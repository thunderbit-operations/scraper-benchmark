# browsertrix-crawler — Independent Audit (validation)

**VERDICT: PASS**

Every headline reproduced independently, with Docker, in this session (Browsertrix
Crawler **v1.14.0** / image digest `sha256:9d6800a8…` / Docker 29 on colima /
Python 3.14.2 / macOS arm64). I re-ran `run_capture.py` and `run_scope.py` from
scratch and — most importantly for the adversarial H2 claim — **opened the produced
WARC with my own parser that does not import the pack's `warc_utils.py`**, and the
per-class capture split and the archive byte-accounting reproduce exactly. No
leak-class (D1–D4) issue, no evidence-integrity issue. Novelty labeling is accurate
and conservatively hedged (base mechanism `DOCUMENTED`, only the per-class
quantification `EXCLUSIVE`). Hardcoding lint clean. Secret/abspath scan clean;
`.gitignore` present and comprehensive; **no WARC/WACZ/crawls mixed into the publish
set** (128 KB). This pack is materially cleaner than its katana sibling (which was
PASS-WITH-FIXES): the abspath leak, missing `.gitignore`, and "strongest" self-praise
that dinged katana are all already absent here. The only open items are pre-final-
**blog**-draft writer notes (below); **none touches a headline number**, so no
required pack fix.

---

## Independent reproduction (my re-runs)

### H1 — capture matrix + parity (reproduced, both instruments agree)

Re-ran `run_capture.py` (crawl rc=0, 28.62 s). Capture matrix, cross-checked WARC
response records ↔ server-side `(host,path)` hits:

| Class | In WARC | Server-fetched | Verdict |
|---|:--:|:--:|---|
| A — HTML `<a href>` | 4/4 | 4/4 | captured |
| A — depth chain | 3/3 | 3/3 | captured |
| **B — JS-literal, uncalled** | **0/2** | **0/2** | **not captured** |
| C — runtime-DOM link | yes | yes | captured |
| D — runtime `fetch()` | yes | yes | captured |

Server-side hit paths contain **neither** `/api/js-endpoint-7` nor `-8`. The two
instruments agree in every cell.

**Parity vs katana (same fixture, identical endpoint names).** katana's matrix:
`standard` misses class C, `-headless` catches it (`fetched /runtime-only/endpoint42`),
`standard -jc` recovers class B (2/2). Browsertrix (real browser) **catches C**
(matching the CDP/headless family, unlike a static crawl) and is the **inverse on B**
(0/2 where static `-jc` gets 2/2). Parity holds and the inversion is the net-new axis.

I also confirmed C/D are **genuinely runtime-assembled, not literal matches**: the
contiguous strings `/runtime-only/endpoint42` and `runtime-xhr-99` appear in the WARC
**only** as their own fetched response records (count 1 each); the home and
`/dynamic/runtime` HTML bodies contain only the assembly fragments (`(6 * 7)`), never
the contiguous path. So the capture required JS execution — a real parity win, not a
string coincidence.

### H2 — WARC opened by hand (the core adversarial claim; **verified**)

I decompressed `archive/*.warc.gz` and walked all 40 records with an **independent**
parser (record counts matched the pack: 1 warcinfo / 13 response / 14 request /
11 resource / 1 revisit; response bytes summed to 5339 exactly). Findings:

- **`app.js` IS archived** — one `response` record, `WARC-Target-URI …/static/app.js`,
  222-byte JS body — and **both** class-B literals `/api/js-endpoint-7` and
  `/api/js-endpoint-8` are present verbatim in that body (the uncalled `loadData()`
  function). Confirmed by printing the body.
- **Neither endpoint is the `WARC-Target-URI` of ANY of the 40 records** (0 response,
  0 request each).
- Each literal string occurs **exactly once in the entire WARC, and both occurrences
  are inside app.js's response body** — nowhere else.

This nails the attribution: the archiver stored the file that references B, yet never
issued a request for the endpoints → it captures **executed traffic, not references**,
the inverse of a static JS parser. The alternative explanation ("app.js wasn't
fetched") is explicitly ruled out. **H2 confirmed on my own instrument, not the
worker's.**

### H3 — archival cost (byte account re-derived from my parse)

From my independent record walk (content bytes, share of 17,024 total content):
`request` 6,912 (40.6%) **> `response`** 5,339 (31.4%) > `resource` 4,527 (26.6%) >
`revisit` 154 (0.9%) > `warcinfo` 92 (0.5%). All 11 `resource` records are
`urn:pageinfo:` (one per page). request + pageinfo = 2.14× the response payload.
On-disk: WARC.gz 24,259 B = **4.54×** payload; WACZ 53,675 B = **10.05×** payload;
WACZ member walk shows `logs/…log` = 16,114 B = **30.0%** of the WACZ. Every H3
number reproduces from the raw archive; the "small-fixture, does-not-extrapolate"
hedge is stated in the pack.

### H5 — scope discipline (reproduced, server-side Host-header truth)

Re-ran `run_scope.py`: `--scopeType prefix` → out-of-scope host fetched **0×**
(`out_of_scope_page_out_hits = 0`); `--scopeType any` → fetched **2×**. Two controls
(default vs widened) prove the negative under prefix is real discipline, not a missed
link. Adjacent leak issue #788 noted but not reproduced under prefix — correctly not
claimed.

### Cost distribution (self-consistency; not re-run)

I did not re-run `run_cost.py` (kept the worker's 3-run `cost-summary.json`). It is
internally coherent: response payload identical (5,339 B ×3), WARC.gz 24,174–24,262
(<0.4%), WACZ 53,446–53,533, elapsed 28.22–30.27 s; ratios of medians 4.542× / 10.025×.
My capture-run WACZ (53,675) differs from the worker's (53,677) by 2 bytes — inside
the documented <0.4% spread. Consistent.

---

## Four escape categories (Part 6)

**D1 — self-contradicting winner sentence: PASS.** There is no "browsertrix captures
everything" sentence to be contradicted by B 0/2 — the headline states outright that
B is **not** captured and that "Real browser = captures everything JS" is over-stated.
The scorecard *marks down* exactly this (Static-reference boundary 7/10, Archival cost
7/10). The only bolded comparatives are within-archive composition percentages (sum to
100%) and cost ratios with non-overlapping 3-run ranges — legitimate. Weights sum to
100; scores sum to 86.

**D2 — blind instrument: PASS.** Capture is measured three independent ways: WARC
response records, the fixture's server-side `(host,path)` counter (fetch-truth,
independent of browsertrix's logs and of the archive), and a body-search of the
archived `app.js`. C/D paths are assembled at runtime, so a "found" cannot be a literal
match — I verified that independently. Scope has a prefix/any double control. Cost is a
3-run distribution. No blind instrument.

**D3 — mis-attribution: PASS.** The B-not-captured conclusion is attributed to
"archiver records executed traffic, not references" **only after** confirming app.js is
archived and its literals are present (I reproduced that from the WARC). The cost
composition is labelled a size-regime observation, not a defect. `autofetch` was checked
and noted not to recover B. Correct root-causing.

**D4 — claim-without-artifact: PASS.** Spot-checked >5 headline numbers, all resolve to
an artifact field I could re-derive: A 4/4 → `capture_matrix.A_html`; B 0/2 +
literals-in-archived-js → `capture_matrix.B…` + `class_b_boundary` (independently
WARC-verified); C 206 B / D 201 B bodies → `replay_fidelity.archived_response_bytes`
(matched my parse); WACZ 10.05× → `cost_ratios`; request 40.6% → `record_type_content_bytes`
(re-derived); prefix 0 / any 2 → `scope-summary.json`. The one un-run item (full pywb
replay render) is explicitly PARKED, not claimed.

---

## Novelty (three-gate) — accurate, not inflated

The pack labels the base facts (real browser captures dynamic content; WARC→WACZ
lossless; `scopeType` flag; `urn:pageinfo:` records exist, #786) as **DOCUMENTED**, and
claims **EXCLUSIVE** only for the *quantifications*: (1) the per-endpoint-class capture
split with the archived-file-contains-literal-but-endpoint-not-fetched inversion, and
(2) the archive record-type byte composition on ground truth. This is exactly the
methodology-endorsed "mechanism documented → quantified demonstration is the
contribution" pattern, not a false new-capability claim. The class-C bound is correctly
hedged to the synchronous-load case with #723 flagged for the untested behavior-time
case. No novelty inflation.

## Anti-hardcoding: PASS

Grepped the harness for result constants (`0.314`, `40.6`, `31.4`, `10.0`, `4.54`,
`5339`, `6912`, `0/2`, `2.1`) — **none present**. `recall()` is set-difference logic;
`class_capture` is set membership; `cost_block` computes every ratio; `class_b_boundary`
and `replay_fidelity` search the WARC. The endpoint sets are pre-registered ground
truth (methodology Part 3 endorses writing the expected set first), not stored results.

## Secret / cleanliness / WARC scan

- **Credentials: CLEAN.** No `sk-…`, `ghp_`, `xox*`, AWS keys, private-key blocks in
  any publish-bound `*.md` / `tests/*.py` / `artifacts/raw/*.json`.
- **Absolute host paths: CLEAN.** `warc_utils.redact` folds `$HOME→~` and
  `$TMPDIR` / `/var/folders` / `/private/var/folders`→`<TMP>`; the docker `cmd` (which
  holds the abspath `-v <CRAWLS_DIR>:/crawls`) is **not** persisted to any summary. A
  full-tree grep for `/Users/richardli` and `/var/folders` in committed files finds only
  legitimate redaction-prefix code references — no leaked path. (This is the leak that
  made katana PASS-WITH-FIXES; it is genuinely absent here.)
- **`.gitignore`: PRESENT** and comprehensive (`artifacts/crawls/`, `*.warc.gz`,
  `*.wacz`, `*.cdxj`, `artifacts/logs/`, `*.log/.out/.stdout/.stderr`, `.venv/`,
  `__pycache__/`).
- **No large/vendored files in publish set.** After my re-runs I deleted the
  `artifacts/crawls/` tree (116 MB) and `artifacts/logs/`; pack is back to **128 KB**;
  `find` for `*.warc* / *.wacz / *.cdxj` returns nothing. Docker image left in place
  (not part of the pack). No lingering containers (`--rm`); no lingering fixture
  processes (the harness stops its own server in `finally`).

---

## Residual notes for the writer (non-blocking; do before any final BLOG draft)

1. **Neutralize evidence-phase self-praise adjectives.** `grep -iE 'honest|independent'`
   surfaces "Independent, reproducible tests" (README:3), "recorded honestly"
   (research-materials:60, pretest:122), and several "three independent instruments" /
   "independent of browsertrix logs". These are borderline-**descriptive** (instrument
   independence / disclosure discipline), evidence-phase only — the same category the
   katana audit ruled non-blocking — but zero the adjectives in the published article per
   Part 4 / D12. (Note: the Part-6 self-check at research-materials:295–297 slightly
   overstates that the lint "surfaces only best-supported/neutral usages"; "honest/
   independent" do occur. The substantive claim — no self-award on a *measurement* —
   still holds. The worker already used "best-supported", not "strongest" — katana's fix
   was pre-applied here.)
2. **Verify the cited issue numbers before the final draft.** #723 (behavior-time
   injection bound), #786 (`urn:pageinfo:`), #788 (scope leak), #957 (direct-fetch
   capture) are used as adjacent/supporting hedges, not headline load-bearing; I did not
   independently fetch them this session. Confirm each still resolves and says what the
   novelty table implies (as the katana audit did for #1324).
3. **Keep the stated hedges.** Small-fixture cost does not extrapolate to large pages;
   class-C claim is synchronous-load only; full pywb replay render is PARKED
   (body-in-archive is verified, rendered replay is not). All already flagged in Gaps.

---

_Audit re-ran `run_capture.py` and `run_scope.py` on 2026-07-24 in system Python
3.14.2, drove the real `webrecorder/browsertrix-crawler:latest` container via colima,
and parsed the produced WARC/WACZ with an independent parser. The pack's
`capture-summary.json` / `scope-summary.json` / `ground_truth.json` were overwritten by
the reproduction runs (expected) and remain consistent with the numbers above;
`cost-summary.json` retains the worker's 3-run data (verified self-consistent). All
crawl output was deleted after the numbers were captured; pack restored to 128 KB._

**Net status: PASS.** All headlines reproduced by the independent audit — including the
H2 archive deep-dive on my own parser — the three hard gates pass, and the only open
items are non-blocking writer notes for the eventual blog draft.
