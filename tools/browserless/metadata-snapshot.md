# browserless — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [browserless/browserless](https://github.com/browserless/browserless) |
| Stars | **13,508** |
| License | **NOASSERTION** (GitHub "Other"; browserless ships a custom license — see repo `LICENSE`) |
| Default branch | **main** |
| Last push | **2026-07-24T05:53:14Z** |
| Docker image | **`ghcr.io/browserless/chromium:latest`** |
| Image digest | **`sha256:9e48bf8df71ba285f974dd9bd9effb59ce8a1e767cfe734b36a24b065ab033f4`** |
| Image created | **2026-07-14T14:30:08Z** |
| Image size | **4.34 GB** |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| Browserless | **v2.55.0** (from `/usr/src/app/package.json` inside the container) |
| Browser | **Chrome/149.0.7827.0** (headless; from `/json/version`) |
| Node (in image) | **v24.18.0** |
| Image base label | **ubuntu 24.04** (`org.opencontainers.image.version`) |
| Container arch | **aarch64** (native; `/json/version` UA cosmetically reports `x86_64` — this is Chrome's UA string, **not** emulation — `docker exec … uname -m` = `aarch64`) |
| Container runtime | **colima 0.10.3** (macOS Virtualization.Framework, 6 CPU / 11.6 GiB) + **Docker 29.2.1** |
| Harness | **Python 3 stdlib only** (no venv, no third-party deps) |
| Host | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-24** |
| Service defaults observed | `CONCURRENT=10`, `QUEUED=10`, `TIMEOUT=30000` (from `/config`) |

## Container token (local, non-secret)

The container is authenticated with a **local, self-assigned `TOKEN`** set at
`docker run` time (`-e TOKEN=…`). It is a container password we chose for this local
run, **not an external credential**. It is **redacted to `<TOKEN>`** in every artifact
and every doc (`bl_common.redact()` also maps `$HOME`→`~`,
`$TMPDIR`/`/var/folders`→`<TMP>`). `/config` echoes the token back, so the harness
redacts `/config` output before writing; no artifact contains a token-shaped literal
(verified: `grep -c` = 0 across all four artifacts).

## Exact commands run

Harness = pure Python 3 stdlib. `tests/bl_common.py` manages the container lifecycle
and drives the REST endpoints; `tests/fixture_server.py` binds **`0.0.0.0`** on a
random free port so the container reaches it via `host.docker.internal`. Ground-truth
markers live in the fixture's `GT` dict; recall is computed against that set, never
guessed.

```bash
# 0) one-time: pull the image (4.3 GB). Recorded by tag + digest; never copied into the pack.
docker pull ghcr.io/browserless/chromium:latest

# The container is launched by the runners themselves, e.g. (token redacted here):
#   docker run -d --name <n> --shm-size=2g \
#     --add-host host.docker.internal:host-gateway \
#     -p 3000:3000 -e TOKEN=<TOKEN> [-e CONCURRENT=N -e QUEUED=M -e TIMEOUT=ms] \
#     ghcr.io/browserless/chromium:latest

# 1) H1 startup: docker-run->ready, cold render, warm; PREBOOT arm; 3 fresh boots each. ~90s
python3 tests/run_startup.py

# 2) H2 concurrency ceiling (RUN ALONE — saturates the container by design). ~90s
python3 tests/run_concurrency.py
#    configs (2,2)/(3,5)/(5,5); fire C+Q+4 concurrent /slow?ms=5000; client + /pressure truth

# 3) H3 REST endpoint fidelity: /content /scrape /screenshot /pdf + token gate. ~20s
python3 tests/run_endpoints.py

# 4) H4 resource/leak (30 sequential sessions, calibrated proc/zombie scan) + H5 TIMEOUT kill. ~90s
python3 tests/run_lifecycle.py

# Each runner starts its OWN container on port 3000 and removes it at the end; run one at
# a time (they share port 3000). All artifacts land in artifacts/raw/*.json (redacted).
```

## Reproducibility notes (honest)

- **Image is single-arch-per-selection.** The manifest lists `linux/arm64` and
  `linux/amd64`; on this arm64 host Docker pulled the **native arm64** variant (4.3 GB).
  Chrome's UA string still reads `X11; Linux x86_64` — that is Chrome's cosmetic UA on
  Linux, **not** emulation (`uname -m` inside the container = `aarch64`). All latency /
  memory numbers are native-arm64, comparable in kind to the sibling arm64 packs.
- **`--shm-size=2g` is set on every launch** (Docker's 64 MB `/dev/shm` default crashes
  Chrome under load — the universally documented caveat). Numbers assume this.
- **`host.docker.internal` networking** is provided by
  `--add-host host.docker.internal:host-gateway` (colima maps host-gateway to the host);
  verified reachable from inside the container (raw `curl` = 200) before any measurement.
- **Container memory** is the operator-visible `docker stats` "MemUsage" used-side
  (cgroup accounting minus inactive file cache on cgroup v2), parsed to bytes — an
  operator's number, not a `tracemalloc`/RSS-of-a-single-process number.
- **Process / zombie truth** comes from `/proc/[0-9]*/comm` + `/proc/*/stat` state field
  inside the container (state `Z` = zombie), enumerated via `docker exec`. The detector
  is **calibrated** (confirmed to read 11 chrome procs mid-session) before its post-run
  zero is trusted.
- **PREBOOT arm caveat:** `-e PREBOOT=true` is inert on v2 (removed in 2.0.0); the arm is
  effectively a second cold-boot sample. This is a finding (FINDING-02), not a harness
  bug — verified by the absence of an idle browser and of a `preboot` key in `/config`.
- **Cleanup:** every runner removes its container (`docker rm -f`) in a `finally`; the
  fixture server is stopped; no `bl_*` container or host fixture process survives a run
  (verified 0 remaining). The 4.3 GB image is left in the local Docker cache (gitignored,
  never copied into the pack).
- **n counts:** startup n=3 boots/arm (median+range only; n<1000 → no percentile);
  concurrency n=3 configs with dual truth; endpoint/lifecycle/timeout are deterministic
  ground-truth checks (single observation each, stated as such).
