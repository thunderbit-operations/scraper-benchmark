# scrapy-playwright — official source notes

Primary source (Tier 1): the official README, which is also the package's
reference documentation. Repo: https://github.com/scrapy-plugins/scrapy-playwright

## What the integration is

- A Scrapy **download handler** that routes selected requests through Playwright,
  so a request opts into browser rendering with `meta={"playwright": True}` while
  everything else stays on Scrapy's normal HTTP path. Requires the asyncio
  Twisted reactor (`TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"`).
- Page interaction is scripted with `PageMethod` objects passed in
  `meta["playwright_page_methods"]` (e.g. `wait_for_selector`, `wait_for_timeout`,
  `screenshot`). The rendered DOM becomes the Scrapy `response`.
- The live Playwright `Page` can be handed to the callback with
  `meta["playwright_include_page"] = True`; the README states the page must then
  be **closed by the caller** to avoid leaks.

## Documented operational boundaries (the review's center of gravity)

These are documented but rarely quantified in tutorials; the pack tests them:

1. **Browser memory is invisible to Scrapy's default stats.** The browser runs in
   separate OS processes, so Scrapy's built-in `MemoryUsage` extension (Python
   process only) does not see it. The package ships a **replacement memory
   extension** `scrapy_playwright.memusage.ScrapyPlaywrightMemoryUsageExtension`
   that includes the browser processes.
2. **Page / context caps.** `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` and
   `PLAYWRIGHT_MAX_CONTEXTS` bound concurrent pages/contexts; hitting the cap is
   the documented backpressure mechanism.
3. **Page-close discipline.** With `playwright_include_page`, the README warns to
   close pages or exhaust the pool; the pack reproduces the exact failure.
4. **No per-request proxy.** Proxy is a browser-launch/context option, not a
   per-request setting — recorded here as an untested documented boundary, not
   bypassed.
5. **Restart / disconnect behavior** and known issues are listed in the README.

## Official capability claims to verify

- Selective rendering via per-request `meta` (verified: mixed crawl renders only
  the `/dynamic/` route).
- `wait_for_selector` / readiness policies determine rendering success (verified:
  no-wait and too-short fixed wait miss the delayed DOM; selector-wait recovers it).
- Screenshot capture via `PageMethod` (verified: full-page PNG artifact).
- Page/context caps and the browser-inclusive memory extension (verified with
  numbers).

## Allowed public targets

- `https://quotes.toscrape.com/js/` (JS-rendered practice page) and
  `https://quotes.toscrape.com/tag/humor/` (static). No logins, no anti-bot, no
  proxy tests, no third-party load testing.
