# ArchiveBox — metadata snapshot

Fetched / tested: **2026-07-24** (as-of). Refresh metadata within 48h before any
final draft.

| Field | Value |
|---|---|
| Repo | [ArchiveBox/ArchiveBox](https://github.com/ArchiveBox/ArchiveBox) |
| License | **MIT** |
| Version tested | **v0.7.4** (`COMMIT_HASH=3830544`, `BUILD_TIME=2026-05-18`) |
| Image | `archivebox/archivebox:latest` |
| Image digest | `sha256:1a5a37331091d9df865ead2b9c231aa5a892fc26fe0422ce6140d9e2d9532327` |
| Image size | 3.24 GB (785 MB compressed) |

Metadata that drifts (stars / open issues / latest release) was **not** re-fetched
for this evidence pack and carries no as-of number here — re-check before any draft.

## Environment actually used

| Item | Value |
|---|---|
| Container runtime | **Docker 29.2.1** on **Colima** (macOS Virtualization.Framework, aarch64), 6 CPU / 11.6 GiB |
| Container→host fixture | fixture binds host `0.0.0.0`; container reaches it via **`host.docker.internal`** (colima maps to 192.168.5.2). `/private/tmp` is NOT shared into the colima VM, so the data dir must live under `$HOME` (verified round-trip). |
| ArchiveBox | **v0.7.4** (in image) |
| Python (in image) | 3.11.15 |
| Chromium (in image) | **147.0.7727.0** (`/usr/bin/chromium-browser`) |
| Node (in image) | 24.15.0 |
| single-file-cli | **2.0.83** |
| readability-extractor | **0.0.11** |
| @postlight/parser (mercury) | **1.0.0** |
| wget | 1.21.3 |
| Harness Python (host) | 3.14 (`.venv`), only third-party dep **pypdf 6.14.2** (PDF text-layer verification) |
| Platform | macOS 26.5.2 arm64 |
| Test date | **2026-07-24** |

### Dependency status (important boundary)

The stock official image reports **every** extractor dependency `valid` via
`archivebox version` (Chrome 147, single-file 2.0.83, readability 0.0.11, mercury
1.0.0, node, wget, git, ripgrep). The large public issue cluster about extractors
failing (#1689/#1278/#763/#1386/#774/#847) is about **missing/mis-detected deps** —
that failure mode does **not** apply to this image. All findings below are behaviour
**with every dependency present**, which is the untested regime.

## Exact commands run

Fixture: `tests/fixture_server.py` (binds `0.0.0.0`, random free port; routes
`/static`, `/dynamic`, `/static/app.js`, `/favicon.ico`, `/failure/500`; four
planted tokens). Harness: `tests/run_matrix.py`.

```bash
python3 -m venv .venv && .venv/bin/pip install pypdf   # pypdf = PDF text-layer only

# Full matrix: defaults dump + FULL(static+dynamic) + NOCHROME + mercury-isolation
# + robustness(500), with 2 stability re-runs of /dynamic. ~9 min (config --set
# spawns one container per key; that dominates wall time, not archiving).
.venv/bin/python tests/run_matrix.py --repeat 2
```

Per config the harness: `docker run --rm -v <DATA>:/data archivebox init --setup`,
then `archivebox config --set SAVE_*=...` (one container per key — **env-var
`-e SAVE_*` is NOT honoured by `add`; only `config --set` persists**), then
`archivebox add <url>`. Extractor status is read from each snapshot's
`index.json["history"]`; token capture is measured by grepping the actual output
files (PDF via pypdf; screenshot is pixels = not text-greppable).

## Reproducibility notes (honest)

- **Container networking**: the fixture must bind `0.0.0.0` (not `127.0.0.1`) and
  live under `$HOME`; colima shares `$HOME` but not `/private/tmp`. Both verified by
  round-trip probe before any measurement.
- **`config --set`, not env vars**: `-e SAVE_MEDIA=False` etc. were silently ignored
  by `archivebox add` (media/archive_org still ran); `archivebox config --set` does
  persist. All disabling in this pack uses `config --set` and is disclosed.
- **`SAVE_ARCHIVE_DOTORG` disabled**: it would submit `localhost` to archive.org
  (offsite + guaranteed-fail); `SAVE_MEDIA`/`SAVE_GIT` disabled (no media/git on the
  fixture). Disclosed, not hidden.
- **Timing is observational single-run only** (`elapsed_s_observational`) and is NOT
  used to support any headline; the headlines are deterministic token-capture facts,
  shown stable across 3 runs (`token_matrix_identical_across_runs: true`).
- **Cleanup**: containers use `--rm`; local scratch (`tests/data/`, `.venv/`, the
  scratch pdf venv) is gitignored and was removed after the run. No image or archive
  product is committed.
