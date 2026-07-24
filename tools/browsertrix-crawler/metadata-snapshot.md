# browsertrix-crawler — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [webrecorder/browsertrix-crawler](https://github.com/webrecorder/browsertrix-crawler) |
| Stars | **1,092** |
| Open issues | **139** |
| License | **AGPL-3.0** |
| Default branch | **main** |
| Last push | **2026-07-23T18:49:02Z** |
| Latest GitHub release | **v1.14.0**, published **2026-07-23T18:49:02Z** |
| Version tested | **v1.14.0** (`crawl --version` inside the image == latest release; no drift) |

Image actually used (record for reproduction):

| Item | Value |
|---|---|
| Image | **`webrecorder/browsertrix-crawler:latest`** |
| Digest | **`sha256:9d6800a8c50723dde1ad768ede91bf5d9704e848d70524c6b71e8492e006ddd4`** |
| Crawler version | **1.14.0** (`docker run --rm …:latest crawl --version`) |
| Image size on disk | **3.51 GB** (bundles a Brave/Chromium browser) |
| Container runtime | **Docker 29.4.3 client / 29.2.1 engine on colima** (macOS Virtualization.Framework VM, 6 CPU / 11.6 GiB, Ubuntu 24.04 aarch64) |
| Python (harness) | **3.14.2** (stdlib only — no third-party WARC libs; no venv required) |
| Host platform | **macOS 26.5.2 arm64** |
| Test date | **2026-07-24** |

## Container → host fixture networking (how it was solved)

The fixture HTTP server runs on the **host** (`fixture_server.py`) and the crawl
runs **inside a Docker container**, so the container must reach back to the host:

- Fixture **binds `0.0.0.0`** (not loopback) — the container's connection arrives
  from the VM gateway, which a loopback-only bind would refuse.
- Container reaches the host via **`host.docker.internal`**, injected with
  **`--add-host=host.docker.internal:host-gateway`** (colima honours the
  `host-gateway` special value). Verified with a one-off `node -e "fetch(...)"`
  in the image before the crawl: the fixture logged a hit with Host header
  `host.docker.internal` (see the network smoke test in the run notes).
- The scope test's "out-of-scope host" is a **second hostname alias**,
  `--add-host=outofscope.test:host-gateway`, pointing at the **same** fixture, so
  a Host-header hit proves an out-of-scope fetch **without any real-internet
  traffic**.

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `0.0.0.0`, random free port; four
endpoint classes A/B/C/D + scope/depth/known-files/robustness routes). Server-side
hit truth is `(host_header, path)`. Ground truth: `artifacts/raw/ground_truth.json`.

```bash
# harnesses are stdlib-only; a venv is optional
python3 tests/run_capture.py   # 1) capture matrix + class-B boundary + replay + archival cost (~30s)
python3 tests/run_scope.py     # 2) scope: prefix vs any, out-of-scope host proof (2 crawls, ~60s)
python3 tests/run_cost.py      # 3) archival-cost + wall-time distribution, 3 isolated crawls (~90s)
```

Each crawl is:

```bash
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  --add-host outofscope.test:host-gateway \
  --shm-size 1g \
  -v <pack>/artifacts/crawls:/crawls \
  webrecorder/browsertrix-crawler:latest crawl \
  --url http://host.docker.internal:<port>/ \
  --scopeType prefix --depth 4 --workers 1 \
  --generateWACZ --collection <name> --logging stats
```

Output lands in `/crawls/collections/<name>/` (WARC in `archive/*.warc.gz`, WACZ
`<name>.wacz`, `pages/pages.jsonl` + `extraPages.jsonl`, `indexes/index.cdxj`).

## Behaviors actually used

Default browsertrix behaviors (`autoplay, autofetch, autoscroll, siteSpecific`);
the crawl log shows `Autoscroll` skipped ("page seems to not be responsive to
scrolling events") and `siteSpecific` present. **`autofetch` did not recover the
class-B endpoints** (still 0/2) — autofetch fetches `img` srcset / stylesheets /
`data-*` URLs, not URL literals inside JS function bodies.

## Reproducibility / honesty notes

- **Container writes are host-readable.** The bind-mounted `artifacts/crawls/`
  tree is owned by the invoking host user (colima virtiofs); the harness parses
  the WARC/WACZ directly, no `docker cp` or chown needed.
- **Archive sizes are near-deterministic.** Over 3 isolated runs, response payload
  was identical (5,339 B every run) and WARC.gz / WACZ varied <0.4% (WARC.gz
  24,174–24,262 B; WACZ 53,446–53,533 B). Elapsed 28.22–30.27 s.
- **Redaction (durable).** All committed JSON is folded `$HOME`→`~` and
  `$TMPDIR` / `/var/folders` / `/private/var/folders`→`<TMP>` by
  `warc_utils.redact`; a scan of `artifacts/raw/` finds no absolute host path.
  Seeds use `host.docker.internal:<port>` (no user path).
- **Cleanup.** Every container ran with `--rm` (self-removing); after the runs
  `docker ps -a --filter ancestor=webrecorder/browsertrix-crawler` is empty. The
  large `artifacts/crawls/` tree (WARC/WACZ/browser profile) is gitignored and was
  removed after the numbers were captured into `artifacts/raw/*.json`.
- **WACZ pages count** comes from `pages/*.jsonl` inside the WACZ (11 pages);
  raw-WARC inventory has no page index (`pages_count: null`), by design.
