# playwright-mcp — metadata snapshot

Fetched: **2026-07-23** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) |
| Stars | **35,435** |
| License | **Apache-2.0** |
| Default branch | **main** |
| Last push | **2026-07-15T01:32:35Z** |
| npm package | **@playwright/mcp** |
| Version tested | **v0.0.78** (== `npx @playwright/mcp@latest` on snapshot day) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| @playwright/mcp | **v0.0.78** (`npx -y @playwright/mcp@latest`) |
| Bundled Playwright server | **1.62.0-alpha-1783623505000** (from MCP `serverInfo`) |
| Browser | Chromium build **1232** = Chrome for Testing **151.0.7922.10** (via `@playwright/mcp install-browser chromium`) |
| Node | **v22.22.3** |
| Python (harness) | **3.14.2** (clean `uv` venv) |
| Token counting | **tiktoken 0.13.0** (`o200k_base` + `cl100k_base`) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-23** |
| Default tool count | **24** (30 with `--caps=vision`) |

## Exact commands run

Harness: a minimal JSON-RPC 2.0 stdio client (`tests/mcp_client.py`) spawns
`npx -y @playwright/mcp@latest <flags>`, does `initialize` →
`notifications/initialized` → `tools/list` → `tools/call`. Tool names are read from
`tools/list`, never hardcoded. Local fixture (`tests/fixture_server.py`) binds
`127.0.0.1` on a random free port; ground-truth markers defined in its `GT` dict.

```bash
# 0) one-time: install the browser the bundled Playwright wants (~273 MB)
npx -y @playwright/mcp@latest install-browser chromium

# 1) venv with tiktoken for token counts (bytes are the ground truth)
uv venv .venv --python 3.14
uv pip install --python .venv/bin/python tiktoken

# 2) snapshot cost vs complexity + a11y-vs-screenshot cliff; ~1 min
.venv/bin/python tests/run_snapshot_cost.py
#    gradient n in {0,1,10,50,100,250,500,1000}; 3 snapshots/page (determinism + latency)
#    screenshot cost on /classes and /gradient?n=100

# 3) per-content-class visibility on ground truth; ~15s
.venv/bin/python tests/run_visibility.py
#    classes A(semantic) B(runtime-injected) C(4 hiding mechanisms) D(canvas)

# 4) session isolation/persistence (server-side cookie truth) + refs + tabs; ~40s
.venv/bin/python tests/run_session.py
#    --isolated leak test; --user-data-dir persistence (graceful browser_close); ref renumbering

# 5) tool surface (default vs --caps=vision) + 500/404 robustness; ~15s
.venv/bin/python tests/run_tools_and_robustness.py

# All flags used per run: --headless --isolated --browser chromium --output-dir <tempdir>
# (persistence run swaps --isolated for --user-data-dir <tempdir>)
```

## Reproducibility notes (honest)

- **Browser install is a required first step.** The bundled Playwright (1.62.0-alpha)
  requested Chrome-for-Testing build 1232; a pre-existing chromium-1228 in the
  ms-playwright cache was not accepted. `install-browser chromium` downloaded Chrome
  for Testing + a headless shell (~273 MB total).
- **Temp output dir.** Every runner passes `--output-dir <tempdir>` (deleted after the
  run) so Playwright MCP's per-action snapshot/console/screenshot files never land in
  the pack. `.playwright-mcp/` is also gitignored.
- **Bytes vs tokens.** Exact UTF-8 bytes of the returned tool text are the
  tokenizer-independent ground truth; `o200k_base`/`cl100k_base` counts are reported
  alongside. No token number is guessed. Snapshot bytes were identical across the 3
  calls per gradient page (determinism verified).
- **Persistence needs a graceful close.** `run_session.py`'s persistence test calls
  `browser_close` before restarting the server so Chromium flushes cookies to the
  `--user-data-dir` profile; an abrupt process kill loses the flush (harness artifact,
  not tool behavior). This is why the first persistence attempt read "not persisted"
  and the corrected one reads "persisted."
- **`navigate` file reference.** In v0.0.78, `browser_navigate` returns a ~321-330 B
  response that references the post-action snapshot as a `.yml` file rather than
  inlining it — observed under `--output-mode stdout`, `file`, and default alike. The
  inline snapshot cost is paid on an explicit `browser_snapshot`.
- **Cleanup.** All temp `--output-dir` and `--user-data-dir` directories are removed by
  the runners; no state is left on the host.
