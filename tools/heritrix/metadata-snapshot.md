# Heritrix — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [internetarchive/heritrix3](https://github.com/internetarchive/heritrix3) |
| Stars | **3,282** |
| Open issues | **36** |
| License | **Apache-2.0** (per `LICENSE` / README; GitHub API reports `NOASSERTION` because some bundled files carry other licenses) |
| Default branch | **master** |
| Last push | **2026-07-15T05:07:03Z** |
| Latest GitHub release | **3.16.0**, published **2026-07-03T01:40:18Z** |
| Version tested | **3.16.0** (== latest release on snapshot day; no drift) |

Environment actually used:

| Item | Value |
|---|---|
| Heritrix | **3.16.0** (`heritrix-3.16.0-dist.tar.gz`), engine reports `heritrixVersion: 3.16.0` |
| JDK | **OpenJDK 26.0.1** (Homebrew `openjdk@26`, 2026-04-21 build) |
| JDK sufficiency | **Yes — 26 satisfies the documented "Java 17 or later"; the engine booted, served the REST API, and completed every crawl on 26.0.1** (no `--add-opens` / `--enable-preview` / Security-Manager flags needed) |
| Python (harness) | stdlib only + system `curl` for REST (digest auth over self-signed TLS) |
| Platform | macOS 26.x arm64 |
| Test date | **2026-07-24** |

## Deployment cost (recorded honestly)

- **Download**: `heritrix-3.16.0-dist.tar.gz` ≈ **41 MB**; unpacks to a tree with
  **142 jars** in `lib/`. (Kept in a git-ignored `vendor/`; never committed.)
- **Start**: `bin/heritrix -a admin:admin -b 127.0.0.1` launches the engine + Jetty
  Web UI + REST on `https://localhost:8443` with a self-signed cert; engine reached
  REST-ready in ~10 s.
- **No browser required**: the whole job lifecycle is REST. Headless automation used
  `curl -k -u admin:admin --anyauth`:
  `POST action=create` → `PUT crawler-beans.cxml` → `POST action=build` →
  `POST action=launch` → `POST action=unpause` → poll `GET job` for
  `crawlControllerState=FINISHED` → `POST action=terminate` → `POST action=teardown`.
- **Config surface**: a job is a ~750-line Spring `crawler-beans.cxml`. A minimal run
  requires setting `metadata.operatorContactUrl` (stock value is a placeholder that
  must be replaced) and the seed; everything else (scope, WARC writer, politeness)
  is bean-configured. This is materially heavier than a single-binary CLI crawler.

### Host artifact (reproducibility note, not Heritrix behavior)

The test host runs a **system HTTP proxy** (macOS `scutil --proxy` →
`HTTPProxy 127.0.0.1:6152`, a Surge instance). Heritrix's Java HTTP client routed
even loopback fixture fetches **through** that proxy — which returned `503` — despite
the OS proxy-exceptions list and `NO_PROXY` both listing `127.0.0.1`. Only launching
the JVM with **`-Djava.net.useSystemProxies=false`** (and stripping `*_PROXY` env)
made fetches reach the fixture directly (verified: same crawl went from `2×503` to
`18×200`). This is a host/proxy interaction, recorded so the run reproduces; it is
**not** scored against Heritrix. The engine is launched with that flag by
`tests/heritrix_driver.py`.

## Exact commands run

Fixture: `tests/fixture_server.py` (Katana pack fixture + additive `/dup/*` identical
-content and `/robots-denied/*` Disallowed routes; binds `127.0.0.1`, random free
port; server-side hit counter). Ground truth: `artifacts/raw/ground_truth.json`.

```bash
# JDK on PATH
export JAVA_HOME=/opt/homebrew/opt/openjdk && export PATH="$JAVA_HOME/bin:$PATH"

# One-time: download the release into the git-ignored vendor/ dir
mkdir -p tools/heritrix/vendor && cd tools/heritrix/vendor
curl -sL -o heritrix-3.16.0-dist.tar.gz \
  https://github.com/internetarchive/heritrix3/releases/download/3.16.0/heritrix-3.16.0-dist.tar.gz
tar xzf heritrix-3.16.0-dist.tar.gz    # -> vendor/heritrix-3.16.0/

# Run the whole evidence harness (starts fixture(s) + a managed engine, runs the
# five concerns, tears everything down). ~5-7 min incl. 3x default-politeness runs.
cd tools/heritrix
python3 tests/run_all.py
#   writes artifacts/raw/{warc-fidelity,dedup,scope,politeness,robots,summary}.json
```

## Reproducibility notes (honest)

- The engine is launched by `heritrix_driver.start_engine()` with
  `JAVA_OPTS="-Xmx256m -Djava.net.useSystemProxies=false ..."` and `*_PROXY` stripped
  (see host-artifact note above). Removing that flag on a host with no system proxy
  is harmless; on this host it is required.
- The stock default-profile `crawler-beans.cxml` is obtained at runtime from a
  throwaway job (`get_baseline_cxml`) and then string-templated per test, so **no
  Heritrix-authored config file is committed** to the pack.
- Politeness is timing-sensitive; default-politeness wall time is dominated by
  `minDelayMs` (3000) per same-host request. Reported as min/median/max over 3 runs.
- Cleanup: the harness tears down every job (`terminate`+`teardown`) and stops the
  engine JVM it launched; `vendor/` (release + all `jobs/` WARC output) is
  git-ignored. The two Python fixture servers are stopped in a `finally` block.
