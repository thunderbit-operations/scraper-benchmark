# scraper-benchmark

Reproducible, hands-on test material for a batch of open-source web scraping tools — the actual scripts, fixtures, and raw results behind a set of independent single-tool reviews.

Most "best scraper" comparisons online are written by companies selling scraping services, rarely run the tools on the same pages, and almost never publish anything you can re-run. This repo is the opposite: every number in the write-ups traces back to a script and a raw JSON result you can execute yourself.

## What's inside

```
tools/<tool>/        one runner per tool + its fixtures + raw results/
fixtures-reference/   the shared ground-truth page structure all packs mirror
METHODOLOGY.md        environment, versions, and the comparability boundary (read this)
```

Tools covered: Crawl4AI · Crawlee · Playwright · Puppeteer · trafilatura · Scrapy · Colly · Scrapling · Firecrawl · selectolax.

## How to reproduce

Each tool directory has its own README with exact steps (they span Python, Node, and Go). In general:

- **Python tools** (crawl4ai, trafilatura, scrapy, scrapling, firecrawl, selectolax): create a venv, `pip install -r requirements.txt`, run the pack's runner (`run_*_material_tests.py`, or `run_tests.py` for selectolax).
- **Node tools** (crawlee, playwright, puppeteer): `npm install`, then `node run_*_material_tests.mjs`. Browser engines need `npx playwright install` / `npx puppeteer browsers install`.
- **Go tool** (colly): `go run main.go`.

**selectolax is a parsing library, not a crawler**, so its pack does not use the shared catalog fixtures. It reproduces a *parser* benchmark — performance distributions vs lxml / BeautifulSoup / parsel across page sizes (3 independent runs + cross-run variance), a CSS-selector coverage matrix (including a fault-finding pass and soupsieve), an adversarial-input sweep, a real dirty-HTML accuracy check, memory/import profiling, and production-dimension probes (thread scaling / memory growth / node lifecycle). See `tools/selectolax/README.md`.

Each runner starts a local fixture server, runs the tests against known ground truth, and writes JSON to `results/`.

## The comparability boundary (please read)

These packs share the **same fixture structure** — a 12-item static catalog, an 8-item JavaScript-rendered catalog, an article page with boilerplate, an intentional HTTP 500, and a small internal-link graph. That makes **structural and recall metrics directly comparable across tools** (e.g. "recovered 8/8 dynamic products", "12/12 static products").

What is **not** strictly comparable across tools is **absolute character counts** of extracted markdown. Each pack uses its own mirrored copy of the fixtures, so product names, prices, and article wording differ slightly between packs. Treat a raw char count as a within-tool signal, not a cross-tool ranking. See [METHODOLOGY.md](METHODOLOGY.md) for the full boundary.

We'd rather state this limit plainly than imply a precision the setup doesn't have.

## Who maintains this

Built and maintained by the Thunderbit team. We make an AI web-scraping API/MCP/CLI, so we have a commercial interest in this space — which is exactly why we're publishing the scripts instead of asking you to take our word for it. The tests aim to be fair to each tool; where a tool stumbled, the raw result says so. Maintenance is best-effort, with metadata (stars/releases) refreshed roughly quarterly.

## License

[MIT](LICENSE). Use it, fork it, re-run it, disagree with it.
