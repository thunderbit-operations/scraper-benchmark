# Playwright MCP — pre-test information-gain brief

Date: 2026-07-23. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable gap exists; see "Information-gain verdict").

Broad keyword: **`Playwright MCP`** (Microsoft `microsoft/playwright-mcp`,
npm `@playwright/mcp`).
Article boundary: Playwright MCP is the **MCP server that exposes browser
automation to an LLM agent as tools**, whose defining design choice is returning a
**structured accessibility-tree snapshot** (text) rather than a pixel screenshot.
This pack judges **what that snapshot sees/omits and what it costs** on controlled
ground truth — *not* the Playwright library itself (that is the separate
`tools/playwright/` pack: native rendering, one API, no crawl queue). No overlap:
this pack never scores rendering or the JS API; it scores the *agent-facing snapshot
surface* (visibility per content class + byte/token cost + session/tab lifecycle).

## SERP scan (first ~20 results, official docs, README, issue tracker)

### What the results repeat (consensus, mostly unmeasured)

- **Default mode = accessibility snapshot, not screenshots.** The server reads the
  browser accessibility tree ("the same semantic structure screen readers use");
  every interactive element gets a `role`, `name`, `state`, and an ephemeral `ref`
  (e.g. `ref=e5`) used to target actions.
- **Token frugality is the headline selling point.** Official Snapshots doc: snapshot
  ≈ **"~200-400 tokens"** vs a screenshot's **"~3000-5000 tokens (vision model)"**.
  Blogs repeat "a few KB vs a few MB," "vision tokens are 3-5× more expensive."
- **Vision mode (`--caps=vision`) adds coordinate/screenshot tools** for content the
  a11y tree can't represent (canvas, WebGL, charts, custom-drawn UI). Docs: "the
  default snapshot-based approach is more reliable and token-efficient… use vision
  mode only when the accessibility tree doesn't cover your use case."
- **Refs are ephemeral** — "valid only until the page changes"; re-snapshot after any
  navigation/DOM change. Framed as a determinism feature.
- **Session modes**: persistent profile (default), `--isolated` (in-memory), plus
  extension/CDP attach. Tabs are `Page` objects managed via `browser_tabs`.
- **Known pitfalls in prose**: token blow-up on large pages; hidden / `aria-hidden`
  content omitted from the default ("interestingOnly") snapshot.

### What is NOT measured anywhere (the gap)

1. **The "~200-400 tokens" claim is never measured against page complexity.** Every
   source quotes the marketing number; several *contradict* it in prose ("a single
   snapshot can hit 50K tokens," "50KB-500KB," "context limit after 2-3 navigations")
   — but **no source plots snapshot bytes/tokens against a controlled element-count
   gradient**. The claim and its refutation both float as anecdote.
2. **Exactly which content classes the a11y snapshot surfaces vs drops is asserted,
   never enumerated on ground truth.** "Canvas is empty," "aria-hidden omitted" are
   repeated as prose. Nobody builds a fixture with distinct content classes and
   measures per-class visibility — in particular the boundary between *runtime-injected
   accessible content* (should appear, because the tree is live) and *non-semantic /
   canvas content* (should not).
3. **The vision fallback's cost cliff is asserted, not priced on the same page.** "3-5×
   more expensive" is quoted generically; no source reports the a11y-snapshot bytes/
   tokens vs the screenshot bytes/tokens **for the identical page**.
4. **Session isolation is described, not proven with fetch-truth.** `--isolated` vs
   persistent is documented; nobody demonstrates, via server-side cookie truth, that
   an isolated session actually starts clean while a persistent one carries state.

### Source evidence

- Official: [microsoft/playwright-mcp README](https://github.com/microsoft/playwright-mcp),
  [Snapshots doc](https://playwright.dev/mcp/snapshots),
  [Vision Mode doc](https://playwright.dev/mcp/vision-mode),
  [Playwright MCP intro](https://playwright.dev/mcp/introduction).
- Upstream issues to cite at execution (token/visibility already reported):
  [#1216 omit page snapshot to cut tokens](https://github.com/microsoft/playwright-mcp/issues/1216),
  [#915 optimize browser_snapshot](https://github.com/microsoft/playwright-mcp/issues/915),
  [#1193 more detailed a11y snapshot](https://github.com/microsoft/playwright-mcp/issues/1193),
  [#1177 overlay/portal dropdowns not captured](https://github.com/microsoft/playwright-mcp/issues/1177),
  [playwright#39955 snapshot includes off-screen elements](https://github.com/microsoft/playwright/issues/39955).
- Representative SERP: [Provar "114K token problem"](https://provar.com/blog/thought-leadership/the-114k-token-problem-why-playwright-mcp-burns-your-ai-coding-agents-control-on-salesforce/),
  [Medium "one screenshot, 232,000 tokens"](https://medium.com/@7003425114klp/one-screenshot-232-000-tokens-0b37783438c7),
  [QASkills a11y snapshots reference](https://qaskills.sh/blog/playwright-mcp-accessibility-snapshots-reference).

## Testable information-gain hypotheses

- **H1 (core, quantify the delta):** On controlled fixtures, a11y-snapshot size grows
  roughly linearly with interactive-element count; the "~200-400 tokens" figure holds
  only for trivially small pages and is exceeded by an order of magnitude on a modest
  (few-hundred-element) page. Measure exact bytes + tokens across a 1→1000-element
  gradient.
- **H2 (adversarial, the real boundary):** The a11y snapshot is a **live** view, so it
  surfaces a link *injected by JavaScript at runtime* (the class that a static crawler
  like katana's standard mode misses) — **but** it silently drops content with **no
  accessible semantics**: a bare non-semantic `<div>`'s text, `aria-hidden` content,
  and anything drawn on `<canvas>`. I.e. "the snapshot sees the page" is over-claimed:
  it sees the *accessible* page. Measure per-content-class recall against ground truth.
- **H3 (cost cliff, same page):** On one identical page, the vision-mode screenshot
  response costs far more (bytes/tokens) than the a11y snapshot — quantify the exact
  multiple, not a generic "3-5×."
- **H4 (session isolation, fetch-truth):** An `--isolated` session started after a
  cookie/localStorage was set does **not** carry that state (server-side cookie truth
  = cookie not re-sent), while a persistent `--user-data-dir` session does.
- **H5 (ref determinism):** Repeated snapshots of an unchanged page yield a stable
  structure; a DOM mutation invalidates prior refs and a fresh snapshot renumbers —
  confirm the documented ephemerality behaves as stated (not a silent stale-ref trap).

## Test matrix (tied to hypotheses)

| # | Test | Fixture route / mode | Measures | H |
|---|---|---|---|---|
| 1-5 | complexity gradient | `/gradient?n=1,10,100,500,1000` interactive elems | snapshot bytes + tokens vs n | H1 |
| 6 | class A semantic | `<a>/<button>/<input>/headings` | present in snapshot w/ role+ref | H2 |
| 7 | class B runtime-injected | `<a>` created by JS at load (no literal in bytes) | surfaced by live snapshot? | H2 |
| 8 | class C non-semantic/hidden | bare `<div>` text, `aria-hidden` block | omitted from default snapshot? | H2 |
| 9 | class D canvas text | known string drawn via canvas `fillText` | a11y-invisible; vision-recoverable? | H2/H3 |
| 10 | cost cliff, same page | a11y snapshot vs `browser_take_screenshot` | bytes/tokens ratio on identical page | H3 |
| 11-13 | snapshot latency | small/medium/large, ≥3 isolated runs each | per-call wall-time distribution | H1 |
| 14 | ref ephemerality | snapshot → mutate DOM → re-snapshot | refs renumber; structure stable on no-op | H5 |
| 15 | isolation | `--isolated`, cookie set then new session | server-side: cookie NOT re-sent | H4 |
| 16 | persistence | `--user-data-dir`, cookie set then reconnect | server-side: cookie re-sent | H4 |
| 17 | tabs | open 2 tabs | `browser_tabs` lists both; snapshot = active tab | lifecycle |
| 18 | tool enumeration | `tools/list` default vs `--caps=vision` | tool count delta, which vision tools appear | doc-confirm |
| 19 | robustness | navigate to 500 / 404 route | snapshot still returns, no crash | robustness |
| 20 | mitigation flags | `--snapshot-mode none`, `--mobile` | do documented token-savers actually shrink output | H1 |

Fixture (local, `127.0.0.1`, Playwright's Chromium hits loopback): reuse the
katana "same-fixture / server-side hit-counter" philosophy. The three content
classes (semantic / runtime-injected / non-semantic+canvas) are the discriminator,
and a **server-side cookie hit-counter** provides isolation fetch-truth independent
of the tool's own reporting. Recall is computed against a pre-registered
ground-truth set — never guessed. Token counts use a real tokenizer (tiktoken
`o200k_base` + `cl100k_base`), with **exact byte counts as the tokenizer-independent
ground truth** so no "token" claim is a guess.

## Harness design (MCP stdio client)

Minimal Python JSON-RPC 2.0 stdio client drives `npx @playwright/mcp@latest`
(v0.0.78): spawn with flags → `initialize` → `notifications/initialized` →
`tools/list` → `tools/call` (`browser_navigate`, `browser_snapshot`,
`browser_take_screenshot`, `browser_tabs`, `browser_evaluate`). Tool names are read
from `tools/list`, never hardcoded. The returned snapshot **text** is measured
byte-exact; screenshot response bytes measured from the returned image payload.
All server-side truth comes from the fixture's hit/cookie counters.

## Information-gain verdict: PROCEED

Not parked. The consensus is dense (snapshot-not-screenshot, ~200-400 tokens, vision
fallback, ephemeral refs) but **entirely qualitative on the four questions that
decide whether the design pays off**: (1) how snapshot cost actually scales with page
complexity vs the marketing number, (2) exactly which content classes the snapshot
surfaces vs drops on ground truth, (3) the same-page a11y-vs-screenshot cost multiple,
(4) isolation proven by fetch-truth. Each is measurable on a local fixture with no
credentials and yields numbers no current SERP source provides. Cross-series bonus:
the class-B runtime-injected endpoint is the *same* content class katana's static
crawl misses — a live a11y snapshot catching it is a concrete, same-fixture contrast
across the benchmark.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on the **local fixture** (`127.0.0.1`) + Playwright's bundled Chromium.
  No third-party/production host, no anti-bot, no auth bypass, no rate abuse.
- No credentials anywhere. Artifacts redact `$HOME`→`~` (katana `_redact` habit).
- Token counts are tokenizer-specific (report the tokenizer + exact bytes); snapshot
  cost claims scoped to the tested fixtures, tool version v0.0.78, and fetch date.
- Novelty honesty: mode existence, ~200-400-token figure, vision fallback, ref
  ephemerality, session modes are all **DOCUMENTED** — this pack's value is the
  *quantification*, not the existence. Token blow-up on large pages is a **KNOWN-ISSUE**
  (#1216/#915). Only genuinely un-recorded measurements get an EXCLUSIVE tag.
