# Firecrawl pack

Tested version: **self-hosted, official prebuilt `latest` images** (pulled 2026-07-09). [Project on GitHub](https://github.com/firecrawl/firecrawl).

Firecrawl turns web pages into **LLM-ready markdown / structured data**, offered as a hosted cloud API and as a self-hostable stack. This pack tests the **self-hosted** service (no cloud key) via its local HTTP `/v1/scrape` API.

> ⚠️ **License: AGPL-3.0.** Firecrawl is strong copyleft with network-use provisions — modifications served over a network may need to be released. **If you are evaluating Firecrawl for commercial use, check the AGPL-3.0 implications first.** This is a decision-relevant caveat, not a footnote.
>
> This pack does **not** redistribute any Firecrawl source code. Only our own runner and raw results live here. To run the service, clone it yourself from the [official repo](https://github.com/firecrawl/firecrawl).

## Run it

Firecrawl self-hosts as a **6-container stack** (`api`, `playwright-service`, `redis`, `rabbitmq`, `nuq-postgres`, `foundationdb`) via Docker Compose — it is not a pip package.

1. **Bring up the service** by following the official self-host guide:
   <https://github.com/firecrawl/firecrawl> (see its `SELF_HOST.md` + `docker-compose.yaml`). Once up, the API listens on `http://localhost:3002`.

2. **Point the runner at your instance** and run it (the runner is pure stdlib):

   ```bash
   pip install -r requirements.txt          # no-op: stdlib only
   export FIRECRAWL_API_URL=http://localhost:3002
   export FIRECRAWL_API_KEY=<YOUR_FIRECRAWL_API_KEY>   # any value; self-host bypasses auth
   python run_tests.py
   ```

`run_tests.py` scrapes a static public page and a JS-rendered public page (both purpose-built scraping-practice sites) to markdown, plus an invalid-host error case, and writes JSON + Markdown to `results/`.

## What's in `results/`

- `public_books_scrape.md` / `public_books_scrape_response.json` — static page → 9,222 chars of clean LLM-ready markdown
- `public_quotes_js_scrape.md` — JS-rendered page, rendered via the bundled `playwright-service` (post-JS content present)
- `firecrawl-test-summary.json` — machine-readable run summary (status, char counts, error case)
- `metadata/` — GitHub / PyPI / npm snapshots (2026-07-07 frozen + 2026-07-09 refresh)

## Honest caveats (also in the root METHODOLOGY)

- **AGPL-3.0 — verify commercial-use licensing implications** (repeated here on purpose; see the banner above).
- The full 6-service stack **did come up** and `/v1/scrape` returned real markdown, including a JS page rendered through `playwright-service`. Two workarounds were needed, and both are **colima-environment artifacts, not Firecrawl faults**:
  1. The from-source build hit a **colima containerd snapshotter flake** → we used the official **prebuilt images** instead.
  2. colima's DNS maps public hostnames to `198.18.x.x`, which Firecrawl's **SSRF/private-IP guard correctly blocked** → we set `ALLOW_LOCAL_WEBHOOKS=true` so the local NAT could reach the demo sites. **Do not disable SSRF protection in a real deployment** — this was purely to work around colima networking.
- **Self-hosted lacks Fire-engine** — the cloud product's advanced anti-block / bot-detection layer. The free self-host is the "fetch + Playwright + markdown" core.
- **Cloud API was not tested** (no key). `/v1/crawl`, `/extract`, and `json` format were also out of scope for this pack.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
