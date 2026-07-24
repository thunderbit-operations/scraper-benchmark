# browsertrix-crawler — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing a run field.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 7 | single `docker run … crawl`; 3.51 GB image; container→host needs `--add-host=host.docker.internal:host-gateway` |
| Static/HTML capture | 12 | 12 | class A 4/4 + depth 3/3, archive == server (`capture_matrix`) |
| Runtime-DOM capture (class C) | 12 | 11 | injected `<a href>` captured (archive+server); bound: behavior-time injection is #723 gap |
| Runtime-fetch capture (class D) | 12 | 12 | issued `fetch()` captured as traffic (archive == server) |
| Static-reference boundary (class B) | 10 | 7 | B 0/2 though `app.js` archived w/ both literals — correct-by-design, real gap vs static parsers |
| Replay-body fidelity | 10 | 8 | C/D response bodies present in WARC (206/201 B); full pywb replay PARKED |
| Archival cost transparency | 10 | 7 | WACZ ~10× payload; request(40.6%)+pageinfo(26.6%) > response(31.4%); ~30% WACZ is logs |
| Scope discipline | 12 | 10 | prefix 0 out-of-scope hits, any 2 (`scope-summary.json`); #788 not reproduced |
| Robustness (500 / dead link) | 6 | 6 | crawl rc=0; dead link stored as `revisit` record |
| Cost measurement rigor | 6 | 6 | 3 isolated runs, <0.4% size spread, full record-type composition |
| **Total** | **100** | **86** | provisional research-material score only |

Scoring notes:

- **Setup (7/10):** one command, but a 3.51 GB image and a real container→host
  networking step (`--add-host=…:host-gateway`, fixture bound `0.0.0.0`) is more
  friction than a single Go binary. Docker required.
- **Runtime-DOM capture (11/12):** the runtime-injected `<a href>` (class C) was
  extracted by the default `a[href]` DOM link extraction and archived — the parity
  win vs a static crawl. Docked one point because it is bounded to
  **synchronous-load** injection; links injected **during behaviors** are a known
  gap ([#723](https://github.com/webrecorder/browsertrix-crawler/issues/723)),
  untested here.
- **Static-reference boundary (7/10):** class B (URL literals in an *uncalled*
  `app.js` function) is **not** captured (0/2) even though `app.js` is archived and
  both literals are in its bytes. This is *correct* for an archiver (it records
  executed traffic, not references) but is a genuine coverage gap relative to a
  static JS parser (katana `-jc`), so it is scored as a real limitation, not a bug.
- **Archival cost (7/10):** transparent and measurable, but heavy on small pages —
  on the 11-page fixture the WACZ is ~10× the captured response bytes, request +
  per-page `urn:pageinfo:` records together exceed the response payload ~2.1×, and
  ~30% of the WACZ is the crawl log. High fidelity has a real byte price; this
  measurement does **not** extrapolate to large-page archives where bodies dominate.
- **Scope discipline (10/12):** default `prefix` scope did not fetch the
  out-of-scope hostname alias (0 hits, server-side Host-header truth); `any` did
  (2 hits), proving the negative is discipline not a missed link. Adjacent leak
  issue [#788](https://github.com/webrecorder/browsertrix-crawler/issues/788) exists
  in other configs and was **not** reproduced under prefix here.
- Scores reflect **dynamic-capture fidelity + archival cost** only; browsertrix is
  not scored on structured-data extraction or known-files recall (out of this pack's
  focus).
