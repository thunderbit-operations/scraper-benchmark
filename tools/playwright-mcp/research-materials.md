# playwright-mcp — Review Research Materials

Date: 2026-07-23

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **Playwright MCP**
(`microsoft/playwright-mcp`, npm `@playwright/mcp`), the MCP server that exposes
browser automation to an LLM agent as tools. Its defining design choice is returning
a **structured accessibility-tree snapshot (text)** instead of a pixel screenshot.
This pack judges the **agent-facing snapshot surface** — what the snapshot sees vs
drops on controlled ground truth, what it costs in bytes/tokens as page complexity
grows, the a11y-vs-screenshot cost gap, and session/tab lifecycle proven by
server-side truth. It does **not** re-score the Playwright *library* (native
rendering, JS API, crawl) — that is the separate `tools/playwright/` pack; there is no
overlap.

All tests run against a **local fixture on `127.0.0.1`** (Playwright's bundled
Chromium hits loopback). No third-party or production host is used; no anti-bot, no
auth bypass, no credentials anywhere. Framing is "what the accessibility snapshot
surfaces and costs on controlled ground truth," not "how to automate someone's site."

Central question (from the pre-test gate): the SERP consensus says "snapshot, not
screenshot; ~200-400 tokens; the tree is the semantic structure screen readers use;
use vision mode for canvas." Nobody measures *how snapshot cost scales with page
complexity* against that 200-400 figure, *which content classes the snapshot actually
surfaces vs drops* on ground truth, the *same-page a11y-vs-screenshot cost gap*, or
*isolation proven by fetch-truth*. This pack measures all four.

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-23** (see `metadata-snapshot.md`):

| Field | Value |
|---|---|
| Repo | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) |
| Stars | **35,435** |
| License | **Apache-2.0** |
| Default branch | **main** |
| Last push | **2026-07-15** |
| npm package | **@playwright/mcp** |
| Version tested | **v0.0.78** (bundled Playwright server `1.62.0-alpha-1783623505000`) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (build 25F84) arm64 |
| @playwright/mcp | **v0.0.78** (`npx -y @playwright/mcp@latest`) |
| Bundled Playwright server | **1.62.0-alpha-1783623505000** (from `serverInfo`) |
| Browser | Chromium build **1232** = Chrome for Testing **151.0.7922.10** (installed via `@playwright/mcp install-browser chromium`) |
| Node | **v22.22.3** |
| Python (harness) | **3.14.2** (clean `uv` venv) |
| Token counts | **tiktoken 0.13.0** (`o200k_base` + `cl100k_base`) |
| MCP client | [tests/mcp_client.py](tests/mcp_client.py) — minimal JSON-RPC 2.0 stdio client |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) — 4 content classes + complexity gradient + server-side cookie counter |
| Cost runner | [tests/run_snapshot_cost.py](tests/run_snapshot_cost.py) → [snapshot-cost-summary.json](artifacts/raw/snapshot-cost-summary.json) |
| Visibility runner | [tests/run_visibility.py](tests/run_visibility.py) → [visibility-summary.json](artifacts/raw/visibility-summary.json) |
| Session runner | [tests/run_session.py](tests/run_session.py) → [session-summary.json](artifacts/raw/session-summary.json) |
| Tools/robustness | [tests/run_tools_and_robustness.py](tests/run_tools_and_robustness.py) → [tools-robustness-summary.json](artifacts/raw/tools-robustness-summary.json) |

Setup / reliability notes (recorded honestly; they affect reproduction):

- **Browser install is a required first step.** The bundled Playwright (1.62.0-alpha)
  wants Chrome-for-Testing build 1232; a pre-existing chromium-1228 was not accepted.
  `install-browser chromium` downloaded ~273 MB (Chrome for Testing + headless shell).
- **Runtime output dir.** Playwright MCP writes per-action snapshots/console/
  screenshots to an `--output-dir`; every runner points it at a throwaway temp dir
  that is deleted after the run, so nothing pollutes the pack (`.playwright-mcp/` is
  also gitignored).
- **Token counts are tokenizer-specific.** Exact UTF-8 **bytes** of the returned tool
  text are the tokenizer-independent ground truth; `o200k_base`/`cl100k_base` token
  counts are reported alongside and labelled as such. No token number is guessed.
- **Persistence requires a graceful close.** The `--user-data-dir` persistence test
  calls `browser_close` before restarting so Chromium flushes cookies to the profile;
  an abrupt process kill loses the flush (a harness artifact, not tool behavior — see
  FINDING-04 and the Part-6 self-check).

## Test Coverage Completed

Fixture ground truth: four content classes, each carrying a **unique marker string**
so presence/absence is measured against a known set, never guessed
([fixture_server.py](tests/fixture_server.py) `GT`):

- **Class A — semantic accessible elements:** heading, two links, a button, a labelled
  textbox. Any snapshot should surface these with roles + refs.
- **Class B — runtime-injected accessible element:** an `<a>` created by JavaScript at
  load time whose href/text are assembled from fragments (`70+7` → 77), so no literal
  `"/runtime/injected-77"` or `"Runtime Injected Link 77"` exists in any served byte.
  This is the class a **static** crawl (katana standard mode) misses.
- **Class C — hidden content, four mechanisms:** bare `<div>` (no role, visible),
  `aria-hidden="true"`, `display:none`, `visibility:hidden`.
- **Class D — canvas-drawn text:** a known string painted via `fillText`; it lives only
  in pixels.

Plus a `/gradient?n=N` route (N interactive `<button>`s) for cost-vs-complexity, a
`/set-cookie` + `/check-cookie` pair with a server-side cookie counter for isolation
fetch-truth, and `500`/`404` routes for robustness.

### H1 — snapshot cost vs page complexity (`snapshot-cost-summary.json`)

`browser_snapshot` inline text size per gradient page (bytes = ground truth; tokens =
tiktoken). Snapshot bytes were **identical across 3 calls per page** (deterministic):

| n interactive elements | snapshot bytes | tokens (o200k) | tokens (cl100k) | > doc 400-tok claim? |
|---:|---:|---:|---:|:--:|
| 0 | 190 | 73 | 74 | no |
| 1 | 261 | 101 | 102 | no |
| 10 | 763 | 263 | 264 | no |
| 50 | 3,043 | **983** | 984 | **yes** |
| 100 | 5,900 | 1,883 | 1,884 | yes |
| 250 | 14,750 | 4,583 | 4,584 | yes |
| 500 | 29,500 | 9,083 | 9,084 | yes |
| 1000 | 59,007 | **18,090** | 18,091 | yes |

Computed: **~58.8 bytes / interactive element**, ~18 tokens/element — snapshot size
grows **linearly** with element count. The official doc's **"~200-400 tokens"** figure
holds only for trivially small pages; the **first gradient step to exceed the 400-token
upper claim is n = 50** (983 tokens, ~2.5×), and a 1,000-element page is **~18k tokens
in a single snapshot** (~45× the claim). Snapshot wall-time is 1-13 ms — the cost is
**tokens, not latency**.

A separate measured behavior: **`browser_navigate` never inlines the snapshot.** Its
response is ~321-330 bytes and references the post-action snapshot as a `.yml` file
(`navigate_inlines_full_snapshot: false` for all 8 pages, across `--output-mode
stdout|file|default`). The full snapshot token cost is paid only when the agent calls
`browser_snapshot` (which inlines). Version-specific (v0.0.78).

### H2 — per-content-class snapshot visibility (`visibility-summary.json`)

Presence of each ground-truth marker in the `/classes` `browser_snapshot`, computed
this run:

| Marker | Class / mechanism | In snapshot? |
|---|---|:--:|
| heading / links / button / textbox | A — semantic roles | **present** |
| Runtime Injected Link 77 | B — JS-injected at runtime, no literal in bytes | **present** |
| NONSEMANTIC_DIV_TEXT_ZZ | C — bare `<div>`, no role, visible | **present** |
| ARIA_HIDDEN_SECRET_QQ | C — `aria-hidden="true"` | **present** |
| DISPLAY_NONE_SECRET_DD | C — `display:none` | **dropped** |
| VISIBILITY_HIDDEN_SECRET_VV | C — `visibility:hidden` | **dropped** |
| CANVAS_ONLY_STRING_XY | D — canvas `fillText`, pixels only | **dropped** |

Reading (the boundary map): the **measured** boundary is exact and reproduced —
elements removed from *layout* (`display:none`, `visibility:hidden`) and content that
exists only as *pixels* (canvas text) are dropped, while **`aria-hidden="true"` content
and role-less `<div>` text — which a real accessibility tree / screen reader would omit
— are surfaced as `generic` nodes.** From those five points the most parsimonious
*inferred* inclusion criterion is roughly **"present in the rendered DOM / layout box,
labelled with ARIA roles where they exist"**, not the browser's ARIA accessibility tree
— but this is an inference, not an instrumented mechanism. We did **not** test
off-screen or below-the-fold content; upstream
[playwright#39955](https://github.com/microsoft/playwright/issues/39955) reports that
below-the-fold (in-layout, not in-viewport) elements also appear, so the true criterion
is layout inclusion, *not* viewport visibility — "visual rendering" is a loose label for
it, not the tested variable. What stands unconditionally is the SERP contradiction: the
snapshot is **not** "the same semantic structure screen readers use" — both role-less
text and aria-hidden text leak in.

Cross-series contrast: class B (runtime-injected, no literal in bytes) **is** surfaced
here by the live snapshot — the same content class that katana's *static* standard-mode
crawl misses (katana pack class C). Live-DOM read vs static parse, on comparable
fixtures.

### H3 — a11y snapshot vs screenshot cost, same page (`snapshot-cost-summary.json`)

On one identical page, `browser_snapshot` text vs `browser_take_screenshot` image:

| Page | a11y snapshot | screenshot (PNG) | screenshot base64 len | PNG-bytes ÷ a11y-bytes |
|---|---|---|---|---:|
| `/classes` (simple) | 260 tok / 721 B | **33,923 B** | 45,232 | **47.0×** |
| `/gradient?n=100` | 1,883 tok / 5,900 B | **134,847 B** | 179,796 | **22.9×** |

The screenshot is returned as an **inline image** payload (a real base64 blob of
45k-180k chars). On a *simple* page the a11y snapshot is dramatically cheaper (721 B
vs a 34 KB PNG). But note the two axes interact: on complex pages the a11y snapshot
itself is expensive (n=1000 → 18k tokens), so "snapshot is cheap" is a **simple-page**
property, not a universal one. Image-token cost is model-specific and is **not**
fabricated here; PNG bytes and base64 length are reported as the ground truth.

### H4 — session isolation vs persistence (`session-summary.json`)

Proven by the fixture's **server-side cookie counter** (did the browser actually re-send
the session cookie), not the tool's own reporting:

| Scenario | Cookie present (page marker) | Server cookie hits | Verdict |
|---|:--:|:--:|---|
| within one `--isolated` session | yes | 1 | cookie works in-session |
| **new `--isolated` session** | **no** | **0** | **isolation holds** |
| `--user-data-dir`, after graceful close + restart | **yes** | **1** | **persistence holds** |

`--isolated` sessions do not leak state across server restarts (a fresh session never
re-sends the prior cookie; server counter 0). A persistent `--user-data-dir` profile
carries a persistent (Max-Age) cookie across a restart — **but only if the browser is
closed gracefully** (`browser_close`) so Chromium flushes cookies to disk first; an
abrupt kill loses it (see FINDING-04).

### H5 — ref determinism (`session-summary.json` → `refs`)

| Observation | Value |
|---|---|
| Two consecutive snapshots of an unchanged page | **refs identical** (`noop_resnapshot_refs_identical: true`) |
| Refs before a DOM mutation | 11 |
| Refs after prepending one element | 12 (`mutation_added_refs: true`) |
| Injected element surfaced in new snapshot | yes |
| Runtime link still present after mutation | yes |

Refs are stable across a no-op re-snapshot and are renumbered/extended after a DOM
change — matching the documented "valid until the page changes" contract. No silent
stale-ref surprise observed on this fixture.

### Tabs (`session-summary.json` → `tabs`)

`browser_tabs {action:new}` + `{action:list}` returns both tabs with the active one
marked `(current)`; `browser_snapshot` reflects the active tab. Tab management works as
documented.

### Tool surface + robustness (`tools-robustness-summary.json`)

- **24 tools by default**; **30 with `--caps=vision`** — the 6 added are exactly the
  coordinate tools `browser_mouse_click_xy`, `browser_mouse_move_xy`,
  `browser_mouse_drag_xy`, `browser_mouse_down`, `browser_mouse_up`,
  `browser_mouse_wheel`. Confirms the documented vision surface.
- **Robustness:** navigating to `/failure/500` and a `/404` both return a non-empty
  snapshot (196 / 195 bytes) with no crash.

## Key Findings for the Writer

1. **FINDING-01 — The "~200-400 token" snapshot is a small-page property; cost scales
   linearly and blows past the claim at ~50 elements (measured, deterministic).**
   Snapshot size is ~58.8 bytes / ~18 tokens per interactive element; n=50 → 983
   tokens (~2.5× the doc's 400 upper bound), n=1000 → ~18k tokens in one snapshot.
   Bytes were identical across 3 calls/page. Confidence: high (deterministic, exact
   bytes + two tokenizers).

2. **FINDING-02 — The snapshot surfaces content a real ARIA accessibility tree would
   omit: aria-hidden and role-less text leak in; display:none / visibility:hidden /
   canvas text are dropped (measured against ground truth).** The inclusion criterion
   is *inferred* to be layout / rendered-DOM inclusion rather than the accessibility
   tree — a parsimonious inference from the boundary points, not an instrumented
   mechanism (off-screen / below-the-fold content was not tested; see the boundary-map
   caveat). This contradicts the common "same structure screen readers use" framing.
   Practical impact: agents can read text a screen reader would never announce, and
   cannot read canvas-drawn text without vision mode. Confidence: high on the measured
   boundary; the mechanism label is inferred.

3. **FINDING-03 — On a simple page the screenshot costs ~23-47× the a11y snapshot's
   bytes; on a complex page the a11y snapshot itself is large (measured, same page).**
   `/classes`: 721 B snapshot vs 34 KB PNG (47×); `/gradient?n=100`: 5.9 KB vs 135 KB
   (23×). The "snapshot is cheap" advantage is real for simple pages and narrows as
   pages grow. Confidence: high on bytes (image-token cost left model-specific, not
   fabricated).

4. **FINDING-04 — `--isolated` isolation and `--user-data-dir` persistence both hold,
   proven by server-side cookie truth; persistence requires a graceful `browser_close`
   before restart.** A fresh isolated session never re-sends a prior cookie (server
   counter 0); a persistent profile does after a graceful close (counter 1). The
   graceful-close requirement is an operational caveat, not a defect. Confidence: high
   (server-side fetch truth).

5. **FINDING-05 — `browser_navigate` does not inline the post-action snapshot; it
   references a `.yml` file (~321-330 B response) across all `--output-mode` settings
   (measured, v0.0.78).** The full snapshot token cost is paid only on an explicit
   `browser_snapshot`. This nuances the "every navigation dumps a full snapshot into
   context" narrative for this version — though a host that auto-expands the referenced
   file would still pay it. Confidence: high on the raw behavior; version-specific.

6. **FINDING-06 — `--caps=vision` adds exactly 6 coordinate mouse tools (24→30);
   refs are stable on a no-op and renumber on DOM change; 500/404 don't crash the
   crawl (all measured).** Housekeeping confirmations of documented behavior.
   Confidence: high.

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark and not
a cross-tool ranking. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **7** | one `npx` command, but a ~273 MB browser install is a required first step |
| Semantic snapshot fidelity (class A) | 12 | **12** | all semantic roles surfaced with refs (`visibility-summary.json`) |
| Live-DOM visibility (class B) | 10 | **10** | runtime-injected link surfaced; static crawlers miss this class |
| Visibility-boundary honesty | 12 | **7** | aria-hidden + role-less text leak in (not a real a11y tree); canvas correctly out |
| Token-cost scaling | 14 | **8** | linear ~18 tok/elem; ~200-400 claim broken by n=50; large pages costly |
| Screenshot / vision cost transparency | 8 | **7** | screenshot 23-47× snapshot bytes on same page; vision fallback documented |
| Session isolation | 10 | **10** | fresh `--isolated` session never re-sends cookie (server truth) |
| Session persistence | 8 | **7** | `--user-data-dir` persists, but needs graceful `browser_close` |
| Ref determinism | 6 | **6** | stable on no-op, renumber on mutation, matches contract |
| Tab lifecycle | 4 | **4** | `browser_tabs` list/new/select work; snapshot = active tab |
| Robustness (500 / 404) | 6 | **6** | snapshot still returns, no crash |
| **Total** | **100** | **84** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **Image-token cost not measured, only image bytes.** Vision-model image tokenization
  is model-specific; PNG bytes / base64 length are the ground truth reported. A final
  draft quoting "vision tokens" must name a specific model's image-token rule.
- **Real-world SPA / heavy app not tested** — all pages are controlled fixtures.
  Enterprise-app snapshot sizes (the "50K token" anecdotes) are plausibly reproduced by
  the gradient but not measured on a real Salesforce/Figma-class page (out of scope).
- **`navigate` file-reference behavior is version-specific (v0.0.78)** and host-
  dependent (a host that auto-reads the referenced file still pays the tokens). Re-check
  on version bumps before generalizing.
- **`--mobile` / `--snapshot-mode none` token-savers not benchmarked** — the help text
  advertises them; their actual reduction is untested here.
- **Single machine, single browser** (Chromium/Chrome-for-Testing, macOS arm64,
  headless). Firefox/WebKit snapshot sizes and headed mode not measured.

## Novelty verification (pre-registration search)

Sources per finding: upstream issue tracker (`microsoft/playwright-mcp` + `playwright`),
official Snapshots/Vision docs, README, and top-~20 SERP. Verdict is
`[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| Snapshot-not-screenshot; ~200-400 tokens; vision adds coordinate tools; refs ephemeral; `--isolated`/`--user-data-dir` modes; tabs | **DOCUMENTED** | [Snapshots doc](https://playwright.dev/mcp/snapshots), [Vision doc](https://playwright.dev/mcp/vision-mode), [README](https://github.com/microsoft/playwright-mcp). Existence/figures are stated; this pack's value is the *quantification*. |
| Snapshot cost blows up on large pages / long navigation | **KNOWN-ISSUE** | [#1216 omit snapshot to cut tokens](https://github.com/microsoft/playwright-mcp/issues/1216), [#915 optimize browser_snapshot](https://github.com/microsoft/playwright-mcp/issues/915). Reported as prose; **not quantified vs an element gradient** anywhere. |
| **~58.8 B / ~18 tok per element; first exceed of the 400-tok claim at n=50; ~18k tok at n=1000 (deterministic)** | **EXCLUSIVE (quantification)** | No SERP/issue source measures snapshot size vs a controlled element-count gradient. Zero-hit for the per-element rate. |
| Snapshot surfaces content hidden from the user (general theme) | **KNOWN-ISSUE** | [#1479 indirect prompt-injection via accessibility snapshots](https://github.com/microsoft/playwright-mcp/issues/1479) (CSS off-screen content reaches the agent) and [playwright#39955 off-screen elements](https://github.com/microsoft/playwright/issues/39955) already establish that non-visible content can appear; [#1177 portals not captured](https://github.com/microsoft/playwright-mcp/issues/1177) is the adjacent scope issue. |
| **Specific per-mechanism enumeration: `aria-hidden="true"` text and role-less `<div>` text surfaced; `display:none`/`visibility:hidden`/canvas dropped** | **EXCLUSIVE (measurement)** | SERP repeats "screen-reader tree" and "aria-hidden omitted"; measured behavior contradicts both. #1479 uses CSS off-screen (`position:absolute`), **not** `aria-hidden`, so the per-mechanism boundary — especially the aria-hidden leak — remains unrecorded. Inferred mechanism ≈ rendered-DOM / layout inclusion (see boundary-map caveat). |
| **Screenshot ≈ 23-47× a11y snapshot bytes on the same page** | **EXCLUSIVE (quantification)** | "3-5× more expensive" quoted generically; no source diffs the same page's snapshot vs screenshot bytes. |
| **`browser_navigate` references snapshot as a file, never inlines (all `--output-mode`), v0.0.78** | **EXCLUSIVE (candidate, version-specific)** | The "every navigation dumps a full snapshot" narrative ([Provar 114K](https://provar.com/blog/thought-leadership/the-114k-token-problem-why-playwright-mcp-burns-your-ai-coding-agents-control-on-salesforce/)) does not note the file-reference response. Version-dependent; flagged as candidate. |
| **Isolation/persistence proven by server-side cookie truth; persistence needs graceful close** | **DOCUMENTED mechanism / EXCLUSIVE demonstration** | Modes are documented; the fetch-truth demonstration + graceful-close requirement is this pack's. |

**Consequence for the writer:** the best-supported information-gain items are all
*measurements behind documented flags* — the token-vs-complexity curve, the
visual-rendering-not-a11y-tree boundary, and the same-page screenshot cost gap.
Superlatives are avoided; every claim above points to a JSON field.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No "fastest/best" adjectives
   on tied numbers. The only bolded comparatives are cost figures with disjoint scales
   (screenshot 23-47× snapshot bytes; n=50 exceeds the 400-tok claim) — measured
   ratios, not close calls. Snapshot latency (1-13 ms) is explicitly *not* used to
   claim a speed win; the cost story is tokens.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`snapshot-cost-summary.json`, `visibility-summary.json`, `session-summary.json`,
   `tools-robustness-summary.json`). The one thing I could **not** back with a real
   number — vision-model image-token cost — is explicitly left as bytes only, labelled
   model-specific, not fabricated.
3. **Blind instrument (D2)** — *Pass.* Recall/visibility is measured against
   pre-registered ground-truth marker strings (`fixture_server.py` `GT`); isolation and
   persistence use the fixture's **server-side cookie counter** (fetch-truth), not the
   tool's stdout. Snapshot size is exact UTF-8 bytes (tokenizer-independent) plus two
   named tokenizers. Determinism verified: snapshot bytes identical across 3 calls/page.
4. **Mis-attribution (D3)** — *Pass.* The persistence test initially failed; before
   claiming "persistence broken" I root-caused it to an **abrupt-kill cookie-flush**
   artifact in the harness and fixed it with a graceful `browser_close` — persistence
   then held. The failure is attributed to the harness, not the tool, and the caveat is
   reported as an operational note.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a
   verdict per finding. The body's one self-praise phrase ("strongest information-gain
   items") has been neutralized to "best-supported"; a
   `grep -iE 'honest|independent|strongest|trustworthy'` now matches only the pattern
   names quoted in this lint line itself ("recorded honestly" is a factual method note).

## As-of provenance check

- **Snapshot date:** explicit **2026-07-23** in `metadata-snapshot.md`. Stars (35,435) /
  license (Apache-2.0) / last-push (2026-07-15) traceable to that GitHub fetch.
- **Versions:** @playwright/mcp v0.0.78; bundled Playwright server
  1.62.0-alpha-1783623505000 (from `serverInfo`); Chromium 1232 / Chrome for Testing
  151.0.7922.10; Node v22.22.3; Python 3.14.2; tiktoken 0.13.0 — read from the run
  summaries / environment.

## Raw Artifact Index

- Cost gradient + screenshot cliff: [snapshot-cost-summary.json](artifacts/raw/snapshot-cost-summary.json)
- Visibility boundary map: [visibility-summary.json](artifacts/raw/visibility-summary.json)
- Session isolation/persistence/refs/tabs: [session-summary.json](artifacts/raw/session-summary.json)
- Tool surface + robustness: [tools-robustness-summary.json](artifacts/raw/tools-robustness-summary.json)
- Per-run stdout under `artifacts/logs/` (gitignored; JSON summaries carry the numbers).
