# scrapy-playwright — evidence pack

Independent, reproducible tests for **scrapy-playwright** (the Scrapy download
handler that renders selected requests with Playwright). Part of the Thunderbit
open-source scraping-tool benchmark. Every number in `research-materials.md`
traces to a script here and a JSON artifact under `artifacts/raw/`.

Tested versions (as-of 2026-07-23): Scrapy 2.17.0, scrapy-playwright 0.0.48,
playwright 1.61.0, Chromium 149.0.7827.55, Python 3.12, macOS arm64.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install scrapy scrapy-playwright playwright
python -m playwright install chromium

# 1) correctness + behavior matrix (15 runs, ~30s; hits public quotes.toscrape.com twice)
python tests/run_correctness.py

# 2) resource: elapsed + browser-inclusive RSS + memory-visibility (12 runs, ~2-3 min)
#    run this ALONE — it is timing-sensitive
python tests/run_resource.py

# 3) scheduler / lifecycle / backpressure (~40s; includes a bounded ~22s wedge test)
python tests/run_lifecycle.py
```

Outputs land in `artifacts/raw/*.json` (+ a rendered screenshot in
`artifacts/screenshots/`). The shared local fixture (`tests/fixture_server.py`)
mirrors the standalone Scrapy pack's fixture, so the two packs are comparable on
identical ground truth.

## What the pack establishes

- Native Scrapy sees 0 cards on a JS catalog; Playwright + `wait_for_selector`
  returns 8/8 (and 10 on public `quotes.toscrape.com/js/`).
- Render success is governed by the readiness condition, not "does JS appear":
  no-wait 0 / fixed-100ms 0 / fixed-1200ms 8 / selector 8.
- Scrapy's default memory stat under-reports the browser-inclusive footprint ~11×;
  the documented `ScrapyPlaywrightMemoryUsageExtension` recovers most of it.
- Selective vs full rendering (same extraction) is a wall-time tie but ~29% lower
  peak RSS for the selective path.
- Page/context caps bound concurrency but still complete; unclosed pages under a
  cap wedge the crawl and require an external kill.

See `research-materials.md` for the full evidence, `scorecard.md` for the
provisional scores, and `validation.md` for the independent reproduction audit.
