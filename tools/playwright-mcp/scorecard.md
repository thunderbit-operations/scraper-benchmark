# playwright-mcp — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking. Weights
are pack-local and pre-registered here; scores are evidence-anchored, each citing a
run. Scope: the **agent-facing accessibility-snapshot surface** of Playwright MCP
v0.0.78 — not the Playwright library.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 7 | one `npx @playwright/mcp` command, but a required ~273 MB `install-browser` step |
| Semantic snapshot fidelity (class A) | 12 | 12 | heading/link/button/textbox all surfaced with roles+refs (`visibility-summary.json`) |
| Live-DOM visibility (class B) | 10 | 10 | runtime-injected link (no literal in bytes) surfaced by the live snapshot |
| Visibility-boundary honesty | 12 | 7 | aria-hidden + role-less `<div>` text leak in (not a real a11y tree); canvas correctly excluded |
| Token-cost scaling | 14 | 8 | ~18 tok/element linear; `~200-400` doc claim broken at n=50 (983 tok); n=1000 → ~18k tok |
| Screenshot / vision cost transparency | 8 | 7 | screenshot 23-47× a11y-snapshot bytes on the same page; vision fallback documented |
| Session isolation | 10 | 10 | fresh `--isolated` session never re-sends the cookie — server counter 0 |
| Session persistence | 8 | 7 | `--user-data-dir` persists across restart, but only with a graceful `browser_close` |
| Ref determinism | 6 | 6 | refs identical on no-op re-snapshot; renumber on DOM mutation (matches contract) |
| Tab lifecycle | 4 | 4 | `browser_tabs` list/new/select work; snapshot reflects active tab |
| Robustness (500 / 404) | 6 | 6 | snapshot still returns non-empty, no crash |
| **Total** | **100** | **84** | provisional research-material score only |

Scoring notes:

- **Token-cost scaling** is marked down (8/14): the headline "~200-400 tokens" is a
  small-page property only. Measured ~58.8 bytes / ~18 tokens per interactive element,
  linear; the first gradient step past the 400-token upper claim is n=50 (983 tokens),
  and a 1,000-element page is a single ~18k-token snapshot. The design is token-frugal
  for simple pages and expensive for complex ones — a real, unadvertised trade.
- **Visibility-boundary honesty** is marked down (7/12): the snapshot filters by
  *visual rendering*, not the ARIA accessibility tree. `aria-hidden="true"` content and
  role-less `<div>` text — which a screen reader would omit — are surfaced as `generic`
  nodes, while `display:none`/`visibility:hidden`/canvas text are correctly dropped.
  Useful to know an agent can read text no screen reader announces; the common
  "same structure screen readers use" framing overstates it.
- **Setup** (7/10): genuinely one command, but the bundled Playwright wants a specific
  Chrome-for-Testing build and a pre-existing chromium was not accepted — a ~273 MB
  first-run download.
- **Session persistence** (7/8): works, but the graceful-`browser_close`-before-restart
  requirement is a real operational caveat (an abrupt kill loses the cookie flush).
- **Isolation** (10/10) and **semantic fidelity / live-DOM visibility** (12, 10) are
  full marks: isolation is proven by server-side fetch-truth, and the snapshot surfaces
  every semantic and runtime-injected element on the fixture.
- Scores reflect the **snapshot surface + session/tab lifecycle** only; Playwright's
  rendering engine, JS API, and crawl behavior are out of scope (see `tools/playwright/`).
