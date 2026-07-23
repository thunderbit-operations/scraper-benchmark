# scrapy-playwright — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

All four headline claims reproduced independently in the existing venv (Scrapy
2.17.0 / scrapy-playwright 0.0.48 / playwright 1.61.0 / Python 3.12.13). No
leak-class (D1–D4) issue found. Novelty labeling is accurate against the live
README. Secret scan is clean. The pack is **not yet clean to publish to a public
repo** — two cleanliness fixes and one cosmetic artifact-field fix are required
first (none touch a headline number).

Required fixes before publishing:

1. **Scrub absolute home paths.** 33 files under `artifacts/logs/*.log` plus
   `artifacts/raw/pw_screenshot.json` embed the private absolute path
   `/Users/<user>/Documents/claude/github-open-source-scraping-tools-single-review-research-2026/...`
   (leaks the OS username and a private directory tree). Scrapy writes the full
   `LOG_FILE`/feed path into its settings dump and `pw_screenshot.json` stores an
   absolute `screenshot_path`. Rewrite these to a relative path (or regenerate
   logs with a relative `LOG_FILE`) before any public commit.
2. **Do not commit the venv; add a `.gitignore`.** `.venv/` is **201 MB** (≈99%
   of the 202 MB pack) and there is no `.gitignore` anywhere (the research root
   is not yet a git repo). Add `.venv/` (and ideally `artifacts/logs/` if paths
   can't be scrubbed) to `.gitignore` so the browser build + venv never enter the
   public repo.
3. **Cosmetic artifact fix (does not affect any headline).**
   `correctness-summary.json` → `tests.pw_dynamic_selectorwait.product_recall`
   reports `recall: 0.0` / all 8 names "missing" while the same row has
   `product_cards_found: 8` and 8 `product_names`. Cause: `names_recall()` keys on
   `r.get("name") or r.get("title")`, but the `pw_dynamic` row schema uses the key
   `product_names` (a list). The headline "8/8 cards" is taken from
   `product_cards_found` and is correct; only this derived field is wrong. Fix the
   helper to fall back to `product_names`, or drop the `product_recall` field for
   pw rows, so no reader cites the spurious 0.0.

---

## Headline claim reproduction

| # | Claim (pack number) | My reproduced number | Reproduces? |
|---|---|---|---|
| 1 | Native dynamic, no render → **0 cards** | 0 | **yes** |
| 1 | Playwright + `wait_for_selector` local → **8/8 cards** | 8 | **yes** |
| 1 | Public `quotes.toscrape.com/js/` with Playwright → **10 nodes** | 10 | **yes** |
| 1 | Readiness matrix no-wait / fixed-100 / fixed-1200 / selector → **0 / 0 / 8 / 8** | 0 / 0 / 8 / 8 | **yes (exact)** |
| 1 | Static 12/12, JSON API 8/8, mixed crawl 11 pages / 1 rendered / depth 1·3·7, screenshot 73,877 B | 12/12, 8/8, 11/1, depth 1·3·7, 73,877 B | **yes (exact)** |
| 2 | Default `memusage/max` ≈ **75 MB** | 75.6 MB (75.3/75.8/75.6) | **yes** |
| 2 | `ScrapyPlaywrightMemoryUsageExtension` ≈ **738 MB** | 737.4 MB median (834.7/737.4/736.2) | **yes** |
| 2 | External psutil tree peak ≈ **850 MB** | ~853–858 MB | **yes** |
| 2 | Blind-spot factor **≈ 11×** | 11.3× | **yes** |
| 2 | pw-ext residual shortfall vs external **≈ 13%** | 14.1% | **within noise** |
| 3 | Selective vs all elapsed = **tie** (1.78 vs 1.84s, overlapping) | tie, overlapping (1.76 vs 1.78s, gap 1.3%) | **yes** |
| 3 | Peak RSS **661 vs 852 MB (~29% lower, non-overlapping)** | 664.5 vs 884.7 MB (33.1% lower, non-overlapping) | **yes (direction/magnitude hold; RSS varies)** |
| 3 | Extraction parity selective == all | `same_extraction: true` | **yes** |
| 4 | Page concurrency 1/4/8 → **8.0 / 2.5 / 1.6 s** | 8.04 / 2.56 / 1.67 s | **yes** |
| 4 | `MAX_PAGES_PER_CONTEXT=2` → max concurrent **2**, all **8** render | max 2, 8 rendered | **yes** |
| 4 | `MAX_CONTEXTS=1` → ctx max **1**, all 8 render | ctx 1, 8 rendered | **yes** |
| 4 | Auto-close: `page_count 6 == page_count/closed 6` | 6 == 6 | **yes** |
| 4 | Unclosed under cap=2 → exactly 2 render then **wedge**, `required_external_kill` | rendered_before_wedge=2, timed_out, rc=-1 @ 22s, required_external_kill=True | **yes** |

Every claim reproduces. #2/#3 magnitudes drift within the run-to-run band the pack
already warns about (browser RSS is noisy); order-of-magnitude and direction hold.
I re-ran all three harnesses (`run_correctness.py`, `run_lifecycle.py`,
`run_resource.py` — the last one alone, nothing else CPU-heavy).

---

## Leak-class findings

**D1 — self-contradicting winner sentence: PASS.**
The elapsed selective-vs-all result is reported as a **tie** everywhere
(table verdict "tie", Finding #3 "wall time was a tie", scorecard "wall-time
tie"). The only bolded winner is peak RSS, whose ranges are non-overlapping
(661 vs 852; I reproduced 664 vs 885). The one occurrence of "speed win"
(`research-materials.md:105`) *rejects* the speed framing ("corrects the common
assumption that selective rendering is primarily a speed win"). No "selective is
faster" claim exists. My reproduced elapsed verdict is also `tie_overlapping_ranges`.

**D2 — blind instrument: PASS.**
The three memory numbers are internally consistent and correctly ordered in my
run: default `memusage/max` 75.6 MB < pw-extension `memusage/max` 737.4 MB <
external psutil tree peak 858.0 MB. The external sampler (`sample_tree_rss_peak`)
genuinely sums RSS over the scrapy process **plus all recursive descendants**
(the browser procs), polling at 0.05 s in a separate process — so it measures
what the claim says. All three instruments are reported together on the same
workload, so the pw-extension's own ~13–14% under-read vs external psutil is
visible rather than hidden. Blind-spot factor 11.3× and shortfall 14.1% both
reproduce.

**D3 — mis-attribution: PASS.**
The 0-card results are correctly attributed to the *readiness/wait condition*,
not to "Playwright can't render." On the identical fixture (delay 450 ms) I got
no-wait→0, fixed-100→0, fixed-1200→8, selector→8 — the only variable is the wait,
and the selector-wait run renders 8, disproving any "can't render" reading. The
native 0 (`native_dynamic_nojs`) is correctly attributed to no rendering at all
(plain HTTP). The unclosed-page wedge is attributed to leaked pages under a cap
and proven, not inferred: the side-channel counter shows exactly
`rendered_before_wedge = 2` = the page cap, then the crawl stalls;
`required_external_kill` is computed from the real `returncode == -1 and
timed_out`, not asserted. All reproduced.

**D4 — claim-without-artifact: PASS.**
Every headline number resolves to a summary JSON, log, or the screenshot artifact.
Extraction parity is a stored equality of the two `extraction_signature` maps in
`resource-summary.json` (`same_extraction: true`, both signatures present), not
prose. The "verified" entries in `source-notes.md` / the novelty table each point
to a concrete run (mixed crawl, readiness runs, PNG, cap runs). No un-backed
"cross-verified" sentence. (The one cosmetic exception is the `product_recall`
field in fix #3 above — a wrong *derived* field, not an unbacked claim; the
card-count artifact it should agree with is present and correct.)

---

## Novelty spot-check: PASS

Fetched the live upstream README and confirmed every mechanism the pack tags
`DOCUMENTED` is genuinely documented, so nothing documented is mislabeled as new
and nothing "new" is actually a shipped feature:

- `ScrapyPlaywrightMemoryUsageExtension` — **documented** (pack: existence
  DOCUMENTED / magnitude EXCLUSIVE — correct; the 11× number is measurement).
- `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT`, `PLAYWRIGHT_MAX_CONTEXTS` — **documented**.
- Page-close discipline — **documented**, and the README even states crawls
  "could freeze if the limit is reached and pages remain open indefinitely."
- Per-request proxy — **documented as NOT supported** (pack records it untested,
  not bypassed — correct).
- Selective `meta={"playwright": True}` rendering — **documented**.

The EXCLUSIVE tags are all *quantifications* of documented mechanisms (11×
memory blind spot, the readiness matrix numbers, the memory-not-time RSS gap, the
wedge's specific `CLOSESPIDER_TIMEOUT`-defeating consequence). No brand-new
capability is claimed. This matches the pack's own "nothing here is a new
capability" statement.

---

## Hardcoding lint: PASS

All conclusion fields are computed from run output, not constants:
- `run_resource.py` `verdict` is derived from range overlap + p50 comparison
  (`tie_or_winner`); `p50_gap_pct` is computed.
- `run_lifecycle.py` `required_external_kill = not (returncode == 0 and not
  timed_out)` — derived from the real process result.
- Card/recall/depth counts come from parsed feed rows and log stats.
No literal result numbers (738 / 852 / 661 / 75 / "8/8" / percentages) appear as
constants in the harness scripts or spiders.

---

## Secret / cleanliness scan

- **Credentials: CLEAN.** No `sk-or-`, `sk-ant-`, `OPENAI`/`OPENROUTER`,
  `API_KEY`, private-key blocks, `xox*`, `ghp_`, or AWS keys anywhere outside
  `.venv`. No `.env` / `.pem` / token / secret / credential files.
- **Absolute home paths: HIT (fix #1).** 33 `artifacts/logs/*.log` + 1 JSON
  (`artifacts/raw/pw_screenshot.json`) contain
  `/Users/<user>/Documents/claude/...`. Leaks username + private tree.
- **Large/vendored files: HIT (fix #2).** `.venv/` = 201 MB, no `.gitignore`.
  Must be excluded from the public repo.
- The cited summary JSONs (`correctness-summary.json`, `resource-summary.json`,
  `lifecycle-summary.json`, ground truth) are path-clean except `pw_screenshot.json`.

---

## Residual gaps the writer must not overclaim

1. **Memory numbers are single-machine macOS arm64 and noisy.** My RSS gap came
   out 33% vs the pack's 29%; blind factor 11.3× vs ~11×; shortfall 14.1% vs
   ~13%. Present these as approximate/distributional (as the pack already does),
   never as exact constants.
2. **The wedge *freeze* itself is documented.** The README says crawls "could
   freeze if the limit is reached and pages remain open indefinitely." Only the
   *specific* consequence — that it defeats `CLOSESPIDER_TIMEOUT` and needs an
   external kill — is the pack's added quantification. Do not frame the freeze as
   a wholly novel discovery; frame it as reproducing/quantifying a documented
   hazard.
3. **Untested boundaries stay untested.** Per-request proxy, browser
   disconnect/restart, `JOBDIR` pause/resume, large-scale (100–1,000 page)
   memory growth, and AutoThrottle interaction are all unmeasured (the pack lists
   them). No claim may extend past the small local graph + two public practice
   pages actually exercised.
4. **"Selective rendering is efficient" = memory, not speed.** Keep the payoff
   framed as ~29–33% lower peak RSS with a wall-time tie; do not let it drift into
   a throughput/speed advantage.

---

_Audit re-ran all three harnesses on 2026-07-23 in the pack's own
`.venv/bin/python`. Reproduction transcripts saved to the auditor scratchpad;
the pack's artifact JSONs were overwritten by the reproduction runs (expected)
and remain consistent with the numbers above._

---

## Fixes applied (post-audit, 2026-07-23)

All three required fixes are done; the pack is now clean to publish.

1. **Absolute home-path leak — RESOLVED.** The screenshot record now stores a
   repo-relative path (`PW_SCREENSHOT_REL`); `run_correctness.py` was re-run.
   A sweep of every publish-bound file (`artifacts/raw/*.json`, `*.md`, `notes/`,
   `tests/*.py`) now finds **0** occurrences of `/Users/<user>`. The remaining
   absolute paths live only in `artifacts/logs/*.log`, which are excluded by the
   new `.gitignore` (and by the benchmark repo's `*.log` rule) and are never
   published.
2. **`.venv` + missing `.gitignore` — RESOLVED.** Added `tools/scrapy-playwright/.gitignore`
   excluding `.venv/`, `__pycache__/`, and `*.log`/`artifacts/logs/`. The 201 MB
   venv is recreated from the README's install steps and never enters the repo.
3. **Cosmetic recall mismatch — RESOLVED.** `names_recall()` was split into a
   `recall_from_found()` helper; the `pw_dynamic_selectorwait` entry now computes
   recall from the row's `product_names` list. Re-run shows
   `product_recall.recall = 1.0` against `product_cards_found = 8` (consistent).

Also added `README.md` with reproduction steps (benchmark-repo convention).

**Net status: PASS.** Headline claims reproduced by the independent audit; the
only issues were cleanliness/cosmetic and are now fixed.
