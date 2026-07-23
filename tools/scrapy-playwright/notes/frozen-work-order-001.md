# Work Order 001 — Scrapy-Playwright

## Scope

- Candidate: `scrapy-plugins/scrapy-playwright`
- Broad search target: `Scrapy Playwright web scraping`
- Article boundary: whether a Scrapy project should render selected routes with Playwright, rather than a generic "Scrapy versus Playwright" comparison.
- Status: pre-test gate approved; evidence pack may begin only after the frozen plan below is copied into `tools/scrapy-playwright/`.

## SERP information-gain scan — 2026-07-23

### What the current results repeat

- Tutorials and commercial comparison pages repeat the same division: Scrapy is suitable for HTTP/static pages, while Playwright renders JavaScript.
- Tutorials demonstrate an install, one dynamic page, and sometimes scrolling, but do not quantify scheduler behavior, browser-process memory visibility, or the cost of rendering only selected routes.
- The official project documents important operational boundaries—separate browser-process memory, context/page limits, page-close discipline, no per-request proxy support, and restart behavior—but these are rarely the center of a review.

### Source evidence

- Official project README: https://github.com/scrapy-plugins/scrapy-playwright
- Official package documentation sections: memory extension, maximum contexts/pages, context closing, restart behavior, and known issues in the same README.
- Current comparison/tutorial examples found in the first search-result scan: https://scrappey.com/qa/python-web-scraping/scrapy-vs-playwright · https://brightdata.com/blog/web-data/scrapy-vs-playwright · https://www.browserstack.com/guide/scrapy-playwright

### Testable information-gain hypotheses

1. **Selective rendering is the actual decision point.** A mixed spider should retain HTTP handling for static routes while enabling browser rendering only for dynamic routes; the useful question is not whether JavaScript appears, but what throughput and resource cost the selective path adds.
2. **The integration's operational risk is invisible in normal Scrapy stats unless its replacement memory extension is enabled.** Measure the gap between process-level browser-inclusive RSS and default Scrapy reporting, then test whether the documented extension closes that visibility gap.
3. **Page and context limits create a real backpressure boundary.** Under controlled local concurrency, an intentionally unclosed page should stall/fail in a reproducible, bounded way; the error/recovery path must be captured, never described from documentation alone.
4. **"Works on a JS page" is insufficient.** Rendering success depends on a correct readiness condition. Compare no explicit wait, fixed wait, and selector wait against a controlled delayed-DOM fixture with ground truth.
5. **The browser is not a replacement for crawl design.** On a small crawl graph, test whether Scrapy's depth/scope/export behavior remains usable when only some requests invoke Playwright.

## Frozen test surface

### Allowed targets

- Shared local fixtures: static catalog, delayed JavaScript catalog, article page, JSON API, HTTP 500 route, and crawl graph.
- Public practice targets only: Books to Scrape and Quotes to Scrape.
- No logins, protected targets, CAPTCHA/anti-bot tests, proxy testing, or load testing of third-party sites.

### Required checks (24)

| Group | Checks |
|---|---|
| Install and baseline | exact versions; clean-venv install; browser download size/time; official quickstart; fresh `scrapy runspider`; documentation mismatch log if any |
| Static and dynamic correctness | local static catalog recall; native-Scrapy dynamic baseline; rendered dynamic recall; no-wait result; fixed-wait result; selector-wait result; public Quotes JS result; screenshot evidence |
| Crawl and outputs | mixed static/dynamic crawl graph; depth/scope assertion; duplicate filtering; JSON/CSV export; HTTP 500 behavior; delayed-page timeout behavior |
| Scheduler and lifecycle | page limit at concurrency 1/4/8; context limit; correctly closed pages; deliberately unclosed-page bounded reproduction; errback cleanup; browser-disconnect/restart behavior if safely reproducible |
| Resource and reliability | three isolated runs per concurrency; elapsed-time distribution; browser-inclusive RSS versus default Scrapy memory statistic; replacement memory-extension statistic; per-route rendering cost; repeated batch stability |
| Adversarial and documentation checks | late DOM update; selector never appears; malformed/empty body; documented no-per-request-proxy boundary recorded as untested behavior, not bypassed; official limitation cross-check |

## Measurement protocol

- Freeze package versions and machine/runtime facts before execution.
- Assert parity against ground truth before timing any comparable route.
- Use three isolated process runs for performance statements; report p50 and spread. Differences below 5% or with overlapping run ranges are a tie.
- Measure RSS in a separate process from Python allocation instrumentation. Never infer browser memory from the default Scrapy memory statistic alone.
- Store JSON/raw HTML/CSV/logs/screenshots even for failures. Every conclusion field must be calculated from run output, not written as a constant.

## Required outputs

```text
tools/scrapy-playwright/
├── notes/source-notes.md
├── tests/
├── artifacts/logs/
├── artifacts/raw/
├── artifacts/screenshots/
├── scorecard.md
├── research-materials.md
└── validation.md
```

`research-materials.md` must classify every finding as `EXCLUSIVE`, `KNOWN_ISSUE`, or `DOCUMENTED`; preserve the exact evidence and state all gaps. It is not an article draft.

## Completion gates

1. Pre-test scan and this work order are present.
2. All 24 checks are either completed with artifacts or explicitly blocked with preserved evidence.
3. At least one headline finding is decision-relevant, measured, and not merely the common "Scrapy static / Playwright dynamic" claim.
4. An independent clean-context audit reproduces every headline claim and passes the no-hardcoded-conclusions lint.
5. Only then may the pack enter the future writing queue.
