# playwright-mcp — evidence pack

Independent, reproducible tests for **Playwright MCP** (`microsoft/playwright-mcp`,
npm `@playwright/mcp`), the MCP server that hands browser automation to an LLM agent —
whose defining choice is returning a **structured accessibility-tree snapshot (text)**
instead of a pixel screenshot. Part of the Thunderbit open-source scraping-tool
benchmark. Every number in `research-materials.md` traces to a script here and a JSON
artifact under `artifacts/raw/`. This pack scores the **agent-facing snapshot surface**,
not the Playwright library (that is `tools/playwright/`).

Tested version (as-of 2026-07-23): **@playwright/mcp v0.0.78** (bundled Playwright
server 1.62.0-alpha), Chrome for Testing 151 / Chromium 1232, Node 22, Python 3.14,
macOS arm64.

## Headline

On controlled ground truth, Playwright MCP's accessibility snapshot is **token-frugal
only for simple pages**: it costs ~58.8 bytes / ~18 tokens **per interactive element**
and grows linearly, so the official **"~200-400 tokens" figure is already exceeded at
~50 elements** (983 tokens) and a 1,000-element page is a single **~18k-token**
snapshot. And the snapshot **filters by visual rendering, not the accessibility tree**:
`aria-hidden` and role-less `<div>` text — which a screen reader would omit — leak in,
while `display:none` / `visibility:hidden` / canvas-drawn text are dropped. On the same
page, a screenshot costs **~23-47× the snapshot's bytes**.

Secondary, all measured: `--isolated` isolation and `--user-data-dir` persistence both
hold under server-side cookie truth (persistence needs a graceful `browser_close`);
`browser_navigate` references its snapshot as a file rather than inlining it (v0.0.78);
refs are stable on a no-op and renumber on DOM change; `--caps=vision` adds exactly 6
coordinate mouse tools (24→30).

## Reproduce

```bash
# one-time: install the browser the bundled Playwright wants (~273 MB)
npx -y @playwright/mcp@latest install-browser chromium

uv venv .venv --python 3.14
uv pip install --python .venv/bin/python tiktoken   # token counts; bytes are ground truth

# 1) snapshot cost vs page complexity + a11y-vs-screenshot cliff, ~1 min
.venv/bin/python tests/run_snapshot_cost.py

# 2) per-content-class snapshot visibility on ground truth, ~15s
.venv/bin/python tests/run_visibility.py

# 3) session isolation/persistence (server-side cookie truth) + refs + tabs, ~40s
.venv/bin/python tests/run_session.py

# 4) tool surface (default vs --caps=vision) + 500/404 robustness, ~15s
.venv/bin/python tests/run_tools_and_robustness.py
```

Requires Node 22 (for `npx @playwright/mcp`) and the installed browser. The local
fixture (`tests/fixture_server.py`) binds `127.0.0.1` on a random port and defines
every ground-truth marker, so visibility is measured against a known set — never
guessed. Outputs land in `artifacts/raw/*.json`.

## What the pack establishes

- **Cost scaling (headline):** ~18 tokens/element, linear; first exceed of the
  400-token doc claim at n=50; ~18k tokens at n=1000. Snapshot bytes deterministic
  across calls; wall-time 1-13 ms (the cost is tokens, not latency).
- **Visibility boundary:** semantic + runtime-injected content surfaced; `aria-hidden`
  and role-less text also surfaced (not a strict a11y tree); `display:none` /
  `visibility:hidden` / canvas text dropped.
- **Cost cliff:** screenshot 33.9 KB (simple) / 134.8 KB (n=100) vs 721 B / 5.9 KB for
  the snapshot on the same pages (47× / 23×).
- **Sessions:** `--isolated` never re-sends a prior cookie (server counter 0);
  `--user-data-dir` persists it across restart after a graceful close (counter 1).
- **Surface:** 24 tools default, 30 with `--caps=vision` (the 6 `*_xy` mouse tools).

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP consensus, hypotheses, matrix,
  PROCEED decision).
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check.
- `scorecard.md` — provisional dimension scores (84/100), evidence-anchored.
- `metadata-snapshot.md` — versions, exact commands, reproducibility caveats.
- `tests/` — `mcp_client.py` (MCP stdio client) + `fixture_server.py` + four runners.
- `artifacts/raw/` — result JSON; `artifacts/logs/` — per-run stdout (gitignored).

Evidence phase only: no article, no publishing. Any independent audit (`validation.md`)
is produced separately and is not part of this worker's deliverable.
