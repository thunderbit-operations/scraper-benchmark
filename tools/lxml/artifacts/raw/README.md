# lxml pack — raw artifacts index

All JSON in this directory is **computed from a run** of the scripts in `../../tests/`, not hand-written
(methodology v3 gate 3). Every result field derives from measured output.

## This pack ran (capability / fidelity — NOT timing)

| File | Script | What it holds |
|---|---|---|
| `xpath_matrix.json` | `xpath_matrix.py` | 37-case XPath feature matrix (axes / predicates / functions / return types + 5 fault-finding XPath-2.0 cases). Expected sets pre-registered in source before running. |
| `two_api_behavior.json` | `two_api_behavior.py` | `lxml.etree` (strict) vs `lxml.html` (lenient) vs `recover=True` on 7 malformed inputs. Behavior labels computed from `error_log`. |
| `iterparse_streaming.json` | `iterparse_streaming.py` | `iterparse` bounded-memory (fast_iter) vs full load vs no-clear, 300k-record XML, peak-RSS instrument with a known-heavy calibration anchor. |
| `namespaces.json` | `namespaces.py` | 12 namespace cases on RSS / SVG / default-NS XML (prefix binding, `local-name()`, `xlink:`, QName, nsmap). |
| `xpath_vs_css.json` | `xpath_vs_css.py` | 10 cases quantifying what XPath expresses that cssselect cannot (text filter, parent/ancestor nav, attr/text-node extraction, count predicates). |
| `real_world_lxml.json` | `real_world_lxml.py` | `lxml.html` on the 11 reused real dirty-HTML fixtures; libxml2 recovery-error counts; strict-XML outcome; count crosscheck vs the reused selectolax-pack lxml counts. |
| `api_capabilities.json` | `api_capabilities.py` | read/write DOM, serialization (html/xml/c14n/pretty), thread-safety API surface, non-UTF-8 handling, node-lifecycle stale-handle (subprocess). |
| `depth_limit.json` | `depth_limit.py` | default ~256-level libxml2 depth cap vs `huge_tree=True` bypass, at depths 300 / 1000 / 5000. |
| `lxml-test-summary.json` | `build_summary.py` | summary rolled up from the above + the reused selectolax timing fields. Generated, not authored. |

## Metadata snapshots (fetched 2026-07-14)

- `github_repo_snapshot_2026-07-14.json` — GitHub API for `lxml/lxml`.
- `pypi_snapshot_2026-07-14.json` — PyPI JSON for `lxml`.
- `github_releases_snapshot_2026-07-14.json` — recent releases.

## Reused from the selectolax pack (read-only; NOT re-run here)

Timing / memory distributions for lxml are **not produced by this pack**. They are cited from the
selectolax pack's artifacts (same machine / same venv / same lxml 6.1.1 / libxml2 2.14.6, benchmarks
as-of 2026-07-13):

- `../../../selectolax/artifacts/raw/bench_isolate.json` — parse-only p50 + 100k-node throughput (lxml rows).
- `../../../selectolax/artifacts/raw/bench_parse.json` — full parse+extract p50 (lxml rows).
- `../../../selectolax/artifacts/raw/bench_memory_import.json` — lxml RSS / tracemalloc / import.
- `../../../selectolax/artifacts/raw/etree_crosscheck.json` — two lxml APIs (`lxml.html.fromstring` vs `lxml.etree.HTMLParser`) parse-only cross-check.
- `../../../selectolax/artifacts/raw/production_dims.json` — lxml thread-scaling / memory-growth / lifecycle.
- `../../../selectolax/artifacts/raw/real_world.json` — reused lxml per-page counts (crosscheck source).
- `../../../selectolax/artifacts/fixtures/real/*.html` — the 11 admitted real fixtures.
