# playwright-mcp — Independent Audit (validation)

**VERDICT: PASS WITH FIXES**

I re-ran **all four harnesses** from scratch in the pack's own `.venv`
(`@playwright/mcp` **v0.0.78** / bundled Playwright server 1.62.0-alpha /
Chromium build 1232 = Chrome-for-Testing 151 / Node v22.22.3 / Python 3.14.2 /
tiktoken 0.13.0 / macOS arm64). **Every headline number reproduced byte-for-byte**
— the H1 cost gradient, the H2 visibility boundary map (including the load-bearing
`aria-hidden` leak), the H3 screenshot cliff, and the H4/H5 session truths. No
leak-class issue (D1–D4). The instruments are calibrated, not blind. Anti-hardcoding
lint passes. Secret + abspath scan is clean (the pack already ships a `.gitignore`
and a `_redact` `$HOME→~` fold). The scorecard arithmetic is self-consistent
(weights = 100, scores = 84) and the 84/100 is *not* contradicted by its own
evidence.

The open items are **novelty-precision / cosmetic** and **none touches a measured
number**: (1) a directly-relevant upstream issue (**#1479**) was missed in the
issue-tracker search and should anchor the *general* "snapshot surfaces
non-visible content" theme as KNOWN-ISSUE while the *specific* aria-hidden/role-less
per-mechanism map stays EXCLUSIVE; (2) the H2 mechanism label "filters by visual
rendering" is an inference from the boundary pattern and should be framed as such
(upstream #39955 shows the criterion is really broader — layout inclusion, not
viewport visibility); (3) one self-praise word ("strongest") the pack already
self-flagged. I did not edit the novelty table or any score — these are flagged for
the worker/writer.

---

## Required fixes before publishing (all headline-safe)

1. **Novelty completeness — cite issue #1479 (missed in the tracker search).**
   The pretest's issue search cites `#1216/#915` (token cost) and `#1177` (portals)
   / `playwright#39955` (off-screen), and the novelty table asserts "adjacent open
   issues on snapshot scope … but none states the aria-hidden/role-less leak." That
   assertion is still **true** after my search — but it **omits the most on-point
   issue, [#1479](https://github.com/microsoft/playwright-mcp/issues/1479)**
   ("Indirect Prompt Injection via accessibility snapshots"), which establishes as a
   *known concern* that content hidden from the user (there: `position:absolute;
   left:-9999px` with an `aria-label`) is faithfully included in the snapshot. This
   does **not** invalidate the finding — #1479 uses CSS-off-screen, **not**
   `aria-hidden="true"`, so the pack's specific per-mechanism result (aria-hidden=true
   text and role-less `<div>` text surfaced) genuinely remains unrecorded. Fix: cite
   #1479 (and #39955) as the KNOWN-ISSUE anchor for the *general* theme, and narrow
   the **EXCLUSIVE** claim to the *specific per-mechanism enumeration + the aria-hidden
   leak*. Novelty-scope correction, not a number change.

2. **H2 mechanism framing — label "visual rendering" as inferred, not instrumented.**
   The measured *phenomenon* is exact and reproduced (aria-hidden + role-less
   surfaced; display:none / visibility:hidden / canvas dropped). The *mechanism*
   "the inclusion criterion tracks visual rendering (layout visibility)" is a
   parsimonious inference from those 5 data points — but upstream #39955 shows
   **below-the-fold** elements (in layout, *not* visible in the viewport) also appear,
   so the true criterion is closer to **"present in the rendered DOM / layout box
   (excludes display:none & visibility:hidden), regardless of viewport-visibility or
   aria-hidden"** — broader than "visually rendered." Per methodology Part 4 (现象与机制分离),
   present the mechanism as *inferred from the boundary pattern*, and note the pack did
   **not** test off-screen/below-fold content (a gap upstream already covers). The
   measured facts stand either way.

3. **Self-praise lint (Part 4 / D12).** `research-materials.md:318` — "the
   **strongest** information-gain items" — the pack's own Part-6 self-check
   (lines 347–348) already flags this; neutralize to "best-supported" in the final
   draft. Other grep hits are false positives ("tokenizer-**independent**",
   "**independent** of the tool's reporting", "recorded **honestly**" describing
   disclosure discipline, README "**Independent**, reproducible tests" describing the
   test design) — evidence-phase, not blockers.

Non-fix caveat for the writer (leave as-is): the H3 ratio (23–47×) is **PNG bytes ÷
a11y-snapshot text bytes** — a wire-size comparison. The pack correctly refuses to
convert the image side into a token number ("image-token cost is model-specific …
not fabricated"). Keep it framed as a **byte** ratio; do not let a final draft
silently upgrade "47× the bytes" into "47× the tokens."

---

## Independent reproduction (my re-runs, pack's own `.venv`)

I ran all four runners fresh and diffed the emitted JSON against the committed
artifacts (normalizing the random fixture port + timestamps). **Result: every
headline number is identical.** The only diffs were (a) `navigate_response` token
counts ±1 — a pure artifact of the random port digits tokenizing differently (the
`navigate_response` **bytes** are identical), and (b) per-call latency ±1–4 ms
(noise the pack explicitly excludes from the cost story). I then restored the
worker's committed artifacts so the pack's of-record numbers match its prose tables.

### H1 — snapshot cost vs complexity (`run_snapshot_cost.py`) — **reproduced exactly**

| n | snapshot bytes | tok o200k | > doc 400? | (my re-run) |
|---:|---:|---:|:--:|:--:|
| 0 | 190 | 73 | no | ✓ |
| 1 | 261 | 101 | no | ✓ |
| 10 | 763 | 263 | no | ✓ |
| **50** | **3,043** | **983** | **yes** | ✓ |
| 100 | 5,900 | 1,883 | yes | ✓ |
| 250 | 14,750 | 4,583 | yes | ✓ |
| 500 | 29,500 | 9,083 | yes | ✓ |
| 1000 | 59,007 | **18,090** | yes | ✓ |

`bytes_per_element_estimate = 58.8`, `first_n_exceeding_doc_claim = 50`,
`navigate_inlines_full_snapshot = false` for all 8 pages — all reproduced. Cost
cliff reproduced: `/classes` **47.05×** (33,923 PNG B ÷ 721 a11y B),
`/gradient?n=100` **22.86×** (134,847 ÷ 5,900). The "~200-400 token" doc figure
is genuinely broken: first exceed at **n=50 (983 tok, ~2.5×)**; n=1000 is a single
**~18k-token** snapshot (~45× the 400 upper bound). Snapshot bytes were stable
across 3 calls/page (determinism assert held on my run too).
**Independent reproduction: CONSISTENT.**

### H2 — per-content-class visibility (`run_visibility.py`) — **reproduced exactly**

My fresh `snapshot_text` (byte-identical to committed, modulo port) directly shows
the load-bearing nodes:

```
- generic [ref=e8]: NONSEMANTIC_DIV_TEXT_ZZ      # role-less <div> text — SURFACED
- generic [ref=e9]: ARIA_HIDDEN_SECRET_QQ        # aria-hidden="true" text — SURFACED
- img "chart" [ref=e10]                          # canvas: only its role, NOT its text
- link "Runtime Injected Link 77" [ref=e11]      # class B runtime-injected — SURFACED
```

Substring truth on my run: `ARIA_HIDDEN_SECRET_QQ` **present**,
`NONSEMANTIC_DIV_TEXT_ZZ` **present**, `Runtime Injected Link 77` **present**;
`DISPLAY_NONE_SECRET_DD`, `VISIBILITY_HIDDEN_SECRET_VV`, `CANVAS_ONLY_STRING_XY`
all **absent**. `boundary_map.aria_hidden_surfaced_contradicts_consensus = true`,
`nonsemantic_div_surfaced_contradicts_only_semantic = true`,
`canvas_text_invisible / display_none_dropped / visibility_hidden_dropped = true`.
**The most bold anti-consensus claim — that a snapshot the docs call "the
accessibility tree" surfaces `aria-hidden="true"` content a screen reader would
omit — is measured, artifact-backed, and I reproduced it. Not brainstormed.**
**Independent reproduction: CONSISTENT.**

### H4/H5 — sessions, refs, tabs (`run_session.py`) — **reproduced exactly**

`isolation`: `within_same_session_cookie_present=true`,
`server_cookie_hits_session1=1`, `new_isolated_session_cookie_present=false`,
**`server_cookie_hits_new_session=0`**, `isolation_holds=true`.
`persistence`: `persistent_profile_cookie_present_after_restart=true`,
`server_cookie_hits_after_restart=1`, `graceful_close_used=true`.
`refs`: 11→12 on mutation, `noop_resnapshot_refs_identical=true`. `tabs`: 2 lines,
both URLs listed. **CONSISTENT.**

### Tools + robustness (`run_tools_and_robustness.py`) — **reproduced exactly**

`default_tool_count=24`, `vision_tool_count=30`, and the 6 added are exactly the
`*_xy`/mouse coordinate tools. `http_500`/`http_404` both return a non-empty
snapshot (196/195 B), no crash. **CONSISTENT.**

---

## Leak-class findings (Part 6)

**D1 — self-contradicting winner sentence: PASS.**
No "cheap-and-complete" winner sentence. The README headline is explicitly hedged
("token-frugal **only for simple pages**"), and the scorecard *marks down* exactly
the dimensions the evidence limits: token-cost 8/14, visibility-honesty 7/12,
setup 7/10, persistence 7/8, screenshot 7/8. The only bolded comparatives (screenshot
23–47× snapshot bytes; n=50 exceeds the 400-tok claim) are measured, non-close
ratios. Full marks (12/12 semantic, 10/10 live-DOM, 10/10 isolation) are each
server-truth/ground-truth backed. Weights sum to 100; scores sum to 84.

**D2 — blind instrument: PASS (calibrated with a positive control).**
Isolation/persistence truth is the fixture's **server-side cookie counter**, not the
tool's stdout. The instrument is proven to *work*: in session 1 the counter reads
**1** (it can detect the cookie) — so the session-2 reading of **0** is a real
"cookie not re-sent," not a dead sensor. Recall/visibility is measured against
pre-registered `GT` marker strings; snapshot size is exact UTF-8 bytes
(tokenizer-independent) plus two named tokenizers; determinism verified (bytes
identical across 3 calls). Not blind. I independently re-ran it and the counter
truths reproduce.

**D3 — mis-attribution: PASS (the buried mine is defused correctly).**
The persistence test's first failure was root-caused to an **abrupt-kill
cookie-flush** harness artifact and fixed with a graceful `browser_close` — the
failure is attributed to the harness, not the tool. Critically, the **isolation
headline does not ride on the graceful-close dance**: `test_isolation` uses plain
`--isolated` (in-memory) sessions with no close ritual, and still reads counter 0.
So "isolation holds" is **not** the "closing the browser dropped the cookie"
confound mislabeled as isolation — I verified this by reproducing the isolated-session
counter 0 directly. The graceful-close requirement is disclosed as an operational
caveat on *persistence* only.

**D4 — claim-without-artifact: PASS.**
Spot-checked 6 headline numbers, all resolve to a JSON field:
`58.8 B/elem` → `snapshot-cost-summary.json.bytes_per_element_estimate`;
`n=50 → 983 tok > 400` → `gradient[3].snapshot_cost.tokens_o200k` +
`first_n_exceeding_doc_claim`; `aria-hidden surfaced` →
`visibility-summary.json.snapshot_text` (`generic [ref=e9]`) +
`boundary_map.aria_hidden_surfaced_contradicts_consensus`; `47×` →
`screenshot_cost_cliff.classes.a11y_bytes_vs_screenshot_png_bytes_ratio`;
`isolation counter 0` → `session-summary.json.isolation.server_cookie_hits_new_session`;
`24→30 tools` → `tools-robustness-summary.json.tool_surface`. The one quantity that
**cannot** be backed by a real number — vision-model **image-token** cost — is
explicitly left as **bytes only**, labelled model-specific, in H3, FINDING-03, and
Gaps. No unbacked "cross-verified" prose.

---

## Novelty classification (three-gate) + evidence

Verified against the live official Snapshots doc, the Playwright aria-snapshots doc,
and the issue tracker (`microsoft/playwright-mcp` + `microsoft/playwright`).

- **H1 cost linearity / "~200-400" broken / ~18 tok-per-element — KNOWN-ISSUE
  (theme) + EXCLUSIVE (quantification).** The blow-up itself is documented as prose
  and filed ([#1216](https://github.com/microsoft/playwright-mcp/issues/1216),
  [#915](https://github.com/microsoft/playwright-mcp/issues/915)) plus SERP anecdotes
  (Provar "114K", Medium "232K", "10k–50k per Lightning page"). **None plots
  bytes/tokens against a controlled element gradient** — the per-element rate + the
  first-exceed-at-n=50 + the n=1000→18k point are unrecorded. The pack's
  EXCLUSIVE(quantification) tag is **accurate**.
- **H2 visual-rendering-not-a11y-tree / aria-hidden surfaced — DOWNGRADE-CHECK
  PASSED; stays a real finding, but split the tag.** *The official docs call it the
  accessibility tree* — Snapshots doc: "structured tree of accessible elements";
  aria-snapshots doc: "a YAML representation of the **accessibility tree**." So the
  measured aria-hidden/role-less leak genuinely **deviates from the documented
  framing** — it is **not** a case of docs already saying "visual snapshot" (which
  would force DOWNGRADED). The *general* "snapshot surfaces content the user/screen-
  reader wouldn't" theme is **KNOWN-ISSUE** ([#1479](https://github.com/microsoft/playwright-mcp/issues/1479),
  [playwright#39955](https://github.com/microsoft/playwright/issues/39955),
  [#1177](https://github.com/microsoft/playwright-mcp/issues/1177)); the *specific*
  aria-hidden=true + role-less per-mechanism map is **EXCLUSIVE (measurement)** — I
  confirmed #1479 uses CSS-off-screen (not aria-hidden) and #39955 is below-the-fold
  (explicitly not aria-hidden/display/visibility). **Fix #1 above** just adds the
  #1479 citation and narrows the EXCLUSIVE scope to the specific mechanisms.
- **H3 screenshot ≈ 23–47× snapshot bytes (same page) — EXCLUSIVE (quantification).**
  "3–5× more expensive" is quoted generically; no source diffs the same page's
  snapshot vs screenshot payload. Accurate — with the bytes-not-tokens hedge intact.
- **H5 `--caps=vision` adds exactly 6 coordinate tools (24→30) / refs ephemeral /
  session modes / tabs — DOCUMENTED.** Vision mode adding coordinate tools, ephemeral
  refs, and the isolated/persistent modes are all in the docs; the pack labels these
  DOCUMENTED and claims only the *measured demonstration/count* as its own. Accurate.
  (Note: one SERP source says "23 core tools" for a different build; the pack's **24**
  is the v0.0.78 measured `tools/list` truth — version-specific, fine.)
- **`browser_navigate` references snapshot as a file, never inlines (v0.0.78) —
  EXCLUSIVE (candidate, version-specific).** Properly hedged as `v0.0.78`-specific and
  host-dependent, in FINDING-05, the novelty table, and Gaps. Accurate.

---

## Hardcoding lint: PASS

Every conclusion field is computed from this run's output:
- bytes = `len(text.encode("utf-8"))`; tokens from `tiktoken` encoders.
- `bytes_per_element_estimate = (b_hi − b_lo) / (n_hi − n_lo)`;
  `first_n_exceeding_doc_claim = min(over)`;
  `exceeds_doc_400_token_claim = tokens_o200k > DOC_CLAIM_TOKENS`.
- cliff `ratio = img_bytes / a11y_bytes`.
- visibility `present = marker in snap`; boundary map derived from the checks list.
- isolation/persistence verdicts computed from server cookie counters; refs from a
  regex over snapshot text; tool deltas from `set(vision) − set(default)`.

The only literals in the harness are legitimately **pre-registered inputs**, not
stored results: `DOC_CLAIM_TOKENS = 400` (the doc claim under test),
`GRADIENT_NS = [0,1,10,50,100,250,500,1000]` (element-count grid — Part 3 endorses
pre-registering the test matrix), `SNAPSHOTS_PER_PAGE = 3`, and the fixture's `GT`
markers + the `70 + 7` computed number (deliberately not a literal `"77"`). No
result constant (`58.8`, `983`, `18090`, `47.05`, `24`, `30`) is written into any
script. Lint clean.

---

## Secret / cleanliness scan

- **Credentials: CLEAN.** No `sk-or-`/`sk-ant-`/`OPENROUTER`/`OPENAI`/`API_KEY`/
  `ghp_`/`xox*`/AWS keys/`Bearer`/private-key blocks in any publish-bound file
  (`*.md`, `tests/*.py`, `artifacts/raw/*.json`), excluding `.venv`/`__pycache__`.
  The `SECRET`/`TOKEN` grep hits are all **fixture ground-truth markers**
  (`COOKIE_VALUE="SECRET_ISOLATION_TOKEN_5F"`, `ARIA_HIDDEN_SECRET_QQ`,
  `DISPLAY_NONE_SECRET_DD`, …) — self-evident test strings, not credentials.
- **Absolute home paths: CLEAN.** Full-tree `/Users/richardli` sweep (incl. the
  gitignored logs) returns nothing. `mcp_client.py._redact` folds `$HOME→~` on every
  written artifact, and the runners point Playwright's `--output-dir` at a throwaway
  temp dir. **No durable-leak debt** (unlike katana, whose harness re-emitted the
  abspath).
- **Hygiene: `.gitignore` already present** (`.venv/`, `__pycache__/`, `*.log`,
  `artifacts/logs/`, `.playwright-mcp/`). `.venv` is small (harness is stdlib +
  tiktoken). Temp `--output-dir`/`--user-data-dir` dirs are `rmtree`'d by the runners;
  I confirmed no `pwmcp-*` temp dirs and no stray `@playwright/mcp`/headless-shell
  processes lingered after my runs.

---

## Residual gaps the writer must not overclaim

1. **Image-token cost is bytes-only.** The 23–47× is a **byte** ratio; a final draft
   quoting "vision tokens" must name a specific model's image-token rule. The pack
   says so — keep it.
2. **Mechanism is inferred, and off-screen/below-fold was not tested.** "Filters by
   visual rendering" is an inference from 5 in-fixture data points; upstream #39955
   shows the criterion also admits below-the-fold (layout-present, viewport-invisible)
   elements the pack never tested. Frame the mechanism as inferred; list off-screen
   as an untested case.
3. **Everything is single-machine, local fixture, Chromium/Chrome-for-Testing,
   headless, v0.0.78.** No real SPA (the "50K-token" anecdotes), no Firefox/WebKit, no
   headed mode, no `--mobile`/`--snapshot-mode none` token-saver benchmark. The pack
   lists these as Gaps — keep them out of any generalized claim.
4. **`navigate` file-reference is v0.0.78-specific and host-dependent** — a host that
   auto-expands the referenced `.yml` still pays the tokens. Keep the version caveat.

---

_Audit re-ran `run_snapshot_cost.py`, `run_visibility.py`, `run_session.py`, and
`run_tools_and_robustness.py` on 2026-07-23 in the pack's own `.venv/bin/python`
(`@playwright/mcp@0.0.78` via `npx`, Chromium 1232). All headline numbers reproduced
byte-for-byte; the committed artifacts were restored after the reproduction diff so
the pack's of-record numbers match its tables. Auditor temp dirs and MCP subprocesses
were cleaned; no lingering state._

**Net status: PASS WITH FIXES.** Every headline reproduced independently (including
the H2 aria-hidden leak and the H1 n=50 break of the 200–400 figure); the open items
are one missed upstream citation (#1479), one mechanism-framing hedge, and one
self-flagged self-praise word — **none alters a measured value or a score.**
