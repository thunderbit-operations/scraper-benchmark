# browsertrix-crawler — evidence pack

Independent, reproducible tests for **Browsertrix Crawler** (Webrecorder), a
real-browser web archiver (Chromium via Puppeteer → WARC/WACZ). Part of the
Thunderbit open-source scraping-tool benchmark. Every number in
`research-materials.md` traces to a script here and a JSON artifact under
`artifacts/raw/`.

Tested (as-of 2026-07-24): image `webrecorder/browsertrix-crawler:latest`
@ `sha256:9d6800a8c50723dde1ad768ede91bf5d9704e848d70524c6b71e8492e006ddd4`,
crawler **v1.14.0**, on Docker/colima, macOS arm64, Python 3.14 (stdlib-only
harness).

## Headline

On controlled ground truth with four dynamic-behaviour classes, a real-browser
**archiver captures what the browser executed, not what code references** — the
inverse of a static JS parser. Browsertrix captures a **runtime-injected DOM
`<a href>`** (class C) and a **runtime `fetch()`** (class D) — both present as WARC
response records and confirmed by server-side fetch — the same runtime-injected
class a static crawl (katana) misses and the CDP-family siblings catch. But it does
**not** capture URL literals sitting in an *uncalled* JS function (class B, 0/2),
**even though the `app.js` that contains them is archived** and both literals are in
its archived bytes. A static parser (katana `-jc`) recovers exactly that class.

Archival cost (measured, 3-run stable): the WACZ is **~10× the captured response
payload** and the WARC.gz **~4.5×**; on this 11-page fixture **request records
(40.6%) + per-page `urn:pageinfo:` records (26.6%) exceed the actual response
payload (31.4%)**, and ~30% of the WACZ is the crawl log. Small-fixture regime —
does not extrapolate to large pages.

## Reproduce

```bash
# harnesses are stdlib-only (no pip). Requires Docker (colima) + the image.
docker pull webrecorder/browsertrix-crawler:latest

python3 tests/run_capture.py   # capture matrix + class-B boundary + replay + cost (~30s)
python3 tests/run_scope.py     # scope: prefix vs any, out-of-scope host proof (~60s)
python3 tests/run_cost.py      # archival-cost + wall-time distribution, 3 runs (~90s)
```

Container→host networking: the fixture (`tests/fixture_server.py`) binds `0.0.0.0`
on a random port; the container reaches it via `host.docker.internal`
(`--add-host=host.docker.internal:host-gateway`, honoured by colima). The
"out-of-scope host" is a second `--add-host` alias to the **same** fixture, so scope
is proven by Host header with no real-internet traffic. Outputs land under
`artifacts/crawls/collections/<name>/` (gitignored) and are parsed into
`artifacts/raw/*.json`.

## What the pack establishes

- **Capture split (headline):** class A (HTML) captured; class C (runtime DOM link)
  captured; class D (runtime fetch) captured; class B (uncalled JS literal) **not**
  captured — though `app.js` is archived with both literals. Two instruments (WARC
  response records + server-side hits) agree in every cell.
- **Replay bodies:** class C (206 B) and D (201 B) response bodies are in the WARC
  (replayable content); full pywb replay render PARKED.
- **Archival cost:** WARC.gz 24.2 KB / WACZ 53.5 KB for 5.3 KB of captured response
  payload → 4.5× / 10.0×; record-type composition request 40.6% > response 31.4% >
  pageinfo 26.6%.
- **Scope:** out-of-scope host fetched 0× under `--scopeType prefix`, 2× under
  `any` (server-side Host-header truth).

## Pack contents

- `pretest-information-gain.md` — the pre-test gate (SERP consensus, gap,
  hypotheses, matrix).
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check.
- `scorecard.md` — provisional dimension scores (86/100), evidence-anchored.
- `metadata-snapshot.md` — image tag+digest, versions, container-network method,
  exact commands, reproducibility caveats.
- `tests/` — `fixture_server.py`, `warc_utils.py` (stdlib WARC/WACZ parser),
  `run_capture.py`, `run_scope.py`, `run_cost.py`.
- `artifacts/raw/` — result JSON (WARC/WACZ binaries + `artifacts/crawls/` and
  `artifacts/logs/` are gitignored).

Evidence phase only: no article, no publishing. `validation.md` (independent audit)
is produced separately and is not part of this worker's deliverable.
