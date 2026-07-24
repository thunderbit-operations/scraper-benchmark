# ArchiveBox — evidence pack

Independent, reproducible tests for **ArchiveBox** (self-hosted web archiving),
part of the Thunderbit open-source scraping-tool benchmark. Focus (verbatim from the
queue): *"Measure which redundant preservation outputs are useful and where they
fail."* Every number in `research-materials.md` traces to a script here and a JSON
artifact under `artifacts/raw/`.

Tested (as-of 2026-07-24): ArchiveBox **v0.7.4** (`archivebox/archivebox:latest`,
`sha256:1a5a3733…`), Chromium 147 / single-file 2.0.83 / readability 0.0.11 /
mercury 1.0.0 — **all dependencies valid** in the stock image. Docker 29.2.1 on
Colima, macOS arm64.

## Headline

ArchiveBox's "multiple redundant copies" are **not** interchangeable. On a fixture
page whose article content is injected by JavaScript at runtime (a token present in
zero served bytes), of the eight content outputs: `singlefile`, `dom`, `pdf`,
`readability`, `htmltotext` preserve the runtime content; **`wget` and `mercury` do
not** — and `wget` is the *only* output that preserves a string living solely in
`app.js`. The two "article text" extractors disagree: `readability` reads
ArchiveBox's rendered capture and keeps the runtime content, while `mercury`
re-fetches the raw URL itself (server-side hit count proves it) and misses it.
Worse, the text extractors' dynamic-content coverage is **inherited**: disable the
chrome extractors and `readability`/`htmltotext` silently fall back to the static
wget HTML and lose the runtime content too — so one chrome failure strips dynamic
content from four outputs at once. Redundancy is a dependency tree, not N
independent copies.

Secondary, evidence-anchored: archiving one page fetches the origin **~8×** (one per
fetching extractor); on an HTTP 500 the run exits cleanly but chrome extractors
report `succeeded` by capturing the *error page* (status ≠ content); PDF carries an
extractable text layer while the screenshot is visual-only; `htmltotext` produces
output but is absent from the snapshot `history` ledger; in v0.7.4 **all** content
extractors (incl. pdf/screenshot) are on by default.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install pypdf   # pypdf = PDF text layer only

# Requires Docker + the archivebox image; the fixture is served in-process and the
# container reaches it via host.docker.internal (colima/Docker Desktop).
docker pull archivebox/archivebox:latest

# defaults dump + FULL(static+dynamic) + NOCHROME + mercury-isolation +
# robustness(500), with 2 stability re-runs of /dynamic (~9 min; per-key
# `config --set` container spawns dominate the wall time, not archiving)
.venv/bin/python tests/run_matrix.py --repeat 2
```

Outputs land in `artifacts/raw/*.json` (host paths redacted). The data dir
(`tests/data/`, gitignored) must live under `$HOME` — colima does not share
`/private/tmp` into the VM.

## What the pack establishes

- **Capture matrix (main):** per-output × per-token (STATIC / RUNTIME / JSLIT /
  BOILER) on `/static` and `/dynamic` — the redundant outputs have distinct
  preservation profiles (`full-matrix.json`).
- **mercury ≠ readability:** source-cited (mercury passes `link.url`; readability
  reads `get_html()` local capture) + server-side fetch attribution
  (`mercury-isolation.json`).
- **Inherited coverage:** chrome-off collapses runtime capture from four outputs
  (`nochrome.json`).
- **Costs & honesty:** ~8× origin fetch per page; 500 clean-exit with
  status≠content (`robustness.json`); htmltotext journaling gap.

## Pack contents

- `pretest-information-gain.md` — SERP/docs/issue gap analysis + hypotheses.
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check, gaps.
- `scorecard.md` — provisional dimension scores (76/100), evidence-anchored.
- `metadata-snapshot.md` — versions, image digest, exact commands, reproducibility
  caveats.
- `tests/` — `fixture_server.py` + `run_matrix.py`.
- `artifacts/raw/` — result JSON (paths redacted).

Evidence phase only: no article, no publishing. `validation.md` (independent audit)
is produced separately and is not part of this worker's deliverable.
