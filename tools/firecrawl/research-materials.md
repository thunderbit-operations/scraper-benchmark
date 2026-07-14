# Firecrawl Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Firecrawl (`firecrawl/firecrawl`), **self-hosted** via official prebuilt images (`ghcr.io/firecrawl/firecrawl:latest`, pulled 2026-07-09). SDK snapshot: firecrawl-py 4.32.0 / @mendable/firecrawl-js 4.30.0. License: **AGPL-3.0**. Date: 2026-07-09, Docker via colima, macOS arm64.
Positioning (official): "The API to search, scrape, and interact with the web at scale" — pages → LLM-ready markdown / structured data.

## What This Pack Covers

A real self-hosted Firecrawl instance (no cloud key) and its `/v1/scrape` API on public scraping-friendly demo sites, including a JS-rendered page routed through the bundled playwright-service. Runner: `tests/run_firecrawl_material_tests.py`.

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Scrape → markdown (static) | books.toscrape.com | success, **9,222 chars** LLM-ready markdown, title "All products \| Books to Scrape" | `artifacts/raw/public_books_scrape.md`, `public_books_scrape_response.json` |
| Scrape → markdown (JS page) | quotes.toscrape.com/js/ | success, 1,574 chars, **rendered Einstein quote present** (playwright-service worked) | `artifacts/raw/public_quotes_js_scrape.md` |
| Error handling | invalid host | structured HTTP 500, no crash | `artifacts/raw/firecrawl-test-summary.json` |

Full details: `artifacts/raw/firecrawl-test-summary.json`.

## The Core Story

Firecrawl's value is page → clean LLM-ready markdown, and the self-hosted stack delivered it: 9k+ chars of structured markdown (headings, links, image refs) from a static catalog, and a JS-rendered quotes page correctly rendered through the bundled playwright-service (the Einstein quote only exists after JS runs). This is a genuinely different product shape from the libraries in this research base — it is a *service* (6 containers) that hands you markdown, not a library you code against.

## Setup And Dependency Friction (Substantial — Key Finding)

Firecrawl self-host is the heaviest setup in this research base:

- **6-service Docker stack**: api, playwright-service, redis, rabbitmq, nuq-postgres, foundationdb. Not a single binary.
- **From-source build failed** on a containerd snapshotter error inside colima (infra flake). Workaround: use the official prebuilt `ghcr.io/firecrawl/*` images (documented option in the compose file), which came up cleanly.
- **SSRF/private-IP guard** blocked public targets because colima's DNS maps public hostnames to `198.18.x.x`. Workaround: `ALLOW_LOCAL_WEBHOOKS=true` (a colima-networking artifact, not a real-deployment recommendation).
- **AGPL-3.0 license**: strong copyleft with network-use terms — a real compliance consideration for any commercial recommendation.
- Self-hosted instances **lack Fire-engine** (the cloud product's advanced anti-block layer), per official `SELF_HOST.md`. AI features (`json` format, `/extract`) need an OpenAI key or Ollama.

## Successes

- Real LLM-ready markdown from a static page (9,222 chars, structured).
- JS rendering via the bundled playwright-service (Einstein quote proves post-JS content).
- Structured error handling (HTTP 500 on a bad target, no crash).
- The full 6-service stack ran on prebuilt images.

## Failures And Limitations (On Purpose)

- Very heavy setup vs every library in this base; not for a quick local script.
- From-source build was not achievable in this environment (containerd snapshotter flake); only the prebuilt-image path succeeded here.
- SSRF guard + colima NAT required a workaround to reach public sites.
- Not tested: `/v1/crawl` (multi-page), `/extract` (needs LLM key), the cloud API + Fire-engine, structured `json` format output.

## Writer Notes

Good blog material (verified): the "page → LLM-ready markdown" core with a real 9k-char sample; JS rendering proof; the honest "it's a 6-service platform, not a library" framing; the AGPL-3.0 compliance flag.

Caveat-only: star count (~148k — very high, note it is metadata); the two environment workarounds (containerd flake, colima DNS) are *this environment*, not Firecrawl faults, and should be described precisely; self-host lacks Fire-engine.

Exclusions: framing the cloud anti-block/Fire-engine capabilities as tested (they were not); any stealth/anti-bot selling point; "best/easiest" superlatives (setup is objectively the heaviest here).

## Gaps Before Final Draft

- Test `/v1/crawl` (multi-page crawl) and `/extract` (with an LLM key).
- Try the from-source build on a clean Docker daemon (non-colima) to validate the contributor path.
- Compare Firecrawl markdown quality vs Crawl4AI and trafilatura for the LLM-ready angle.
- Document AGPL-3.0 implications for commercial use prominently.
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources: the upstream repo/issue tracker (`firecrawl/firecrawl`), the official docs (incl. `SELF_HOST.md`), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.** LLM-dependent features (`json` format, `/extract`) are **out of scope** (need an LLM key) and are not classified from memory.

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Page → LLM-ready Markdown** via a self-hosted `/v1/scrape` (verified 9,222-char structured Markdown; JS page rendered via bundled playwright-service) | **DOCUMENTED** | The core "scrape → clean Markdown" product is the advertised positioning ("The API to search, scrape, and interact with the web at scale"). Verified working self-hosted, but an advertised capability, not a discovery. |
| **Self-host is a 6-service platform, not a library** (api, playwright-service, redis, rabbitmq, nuq-postgres, foundationdb) | **DOCUMENTED — architecture fact** | The service topology is defined in the project's own `docker-compose` / self-host docs. An accurate, decision-relevant framing ("service, not a library") — verifiable, not novel. |
| **Self-hosted instances lack Fire-engine** (the cloud product's proprietary anti-block layer) | **DOCUMENTED — the pack cites `SELF_HOST.md`** | Confirmed vendor-documented and widely corroborated: Fire-engine is closed-source and cloud-only; self-host users get no built-in anti-bot/proxy layer — [WebScraping.AI: is Firecrawl self-hostable](https://webscraping.ai/faq/firecrawl/is-firecrawl-open-source-and-can-i-self-host-it), and multiple 2026 writeups ([TinyFish alternatives](https://www.tinyfish.ai/blog/firecrawl-alternatives)). The pack already cites official `SELF_HOST.md`. **Not EXCLUSIVE** — this is a documented product boundary, correctly reported. |
| **AGPL-3.0 license** (strong copyleft + network-use terms) as a commercial-compliance consideration | **DOCUMENTED** | License is stated on the repo and in the snapshot (AGPL-3.0). The compliance implication for commercial use is a documented, decision-relevant flag — accurate framing, not a finding. |
| **From-source build failed (containerd snapshotter error in colima); SSRF/private-IP guard blocked public targets under colima NAT** | **DOCUMENTED — environment artifacts, correctly disclaimed** | Both are explicitly labeled in the RM as *this environment* (colima), **not** Firecrawl faults — the containerd flake and the `198.18.x.x` DNS mapping are colima behaviors; the SSRF guard itself is an intended, documented security feature. Per v3 §Part 6 point 4 (rule out harness/environment before attributing to the tool), the attribution is already honest: these are not Firecrawl defects. No `[KNOWN-ISSUE]` tag against Firecrawl. |

**Consequence for the writer:** nothing is `EXCLUSIVE`. The most valuable true statements are the honest "6-service platform, not a library" framing, the verified self-hosted Markdown sample, and the **documented** "self-host lacks Fire-engine + AGPL-3.0" compliance flags. The two environment workarounds must stay labeled as colima artifacts, not Firecrawl faults.

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool ranking; the RM explicitly excludes "best/easiest" superlatives and even states setup is "objectively the heaviest here" (a limitation, not a win). No winner sentence to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* The scrape results cite artifacts (`public_books_scrape.md`, `public_quotes_js_scrape.md`, `firecrawl-test-summary.json`). The Fire-engine and AGPL claims are backed by the cited `SELF_HOST.md` / license, now with external corroboration links added above. No un-backed "cross-verified" sentence.
3. **Blind instrument (D2)** — *Pass (N/A).* No timing/memory/leak instrument is used at all; this pack makes no speed claim. No blind-instrument exposure and no zero-benchmark "fast" adjective.
4. **Mis-attribution (D3)** — *Pass (this is the pack's strong point).* The two failures (containerd build flake, SSRF/DNS block) are explicitly attributed to the colima environment, not to Firecrawl — exactly the "rule out harness/environment first" discipline v3 Part 6 point 4 demands. The prebuilt-image workaround path is disclosed. Attribution is honest.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → "the **honest** '6-service platform, not a library' framing" (Writer Notes) — modifies the *framing's candor*, borderline-acceptable; neutralize to "the accurate '…' framing" in the final draft if strict. Flagged, not rewritten (additive pass).

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the LLM-dependent features are explicitly excluded as out-of-scope rather than classified; every verdict cites a doc or external link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks:** RM Writer Notes flags "~148k — very high, note it is metadata"; the snapshot records 146,948 → 147,906 stars (2026-07-07 → 2026-07-09). **Writer note:** the RM's "~148k" rounds slightly above the 2026-07-09 figure (147,906) — render as **"~148k stars as of 2026-07-09 (firecrawl/firecrawl)"** at point of use, and the writer may prefer "~147.9k" for precision.
- **SDK / image versions:** RM cites firecrawl-py 4.32.0 / firecrawl-js 4.30.0 and the `ghcr.io/firecrawl/firecrawl:latest` image "pulled 2026-07-09"; the snapshot's 2026-07-09 refresh confirms firecrawl-py 4.32.0 / firecrawl-js 4.30.0. Traceable; the `:latest` image tag is inherently mutable and is correctly dated to the 2026-07-09 pull.
- **License:** AGPL-3.0 in both RM and snapshot. Stable.
- **Instruction (do not fetch live):** not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.
