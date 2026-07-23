import os

import scrapy
from scrapy_playwright.page import PageMethod


PW_SETTINGS = {
    "ROBOTSTXT_OBEY": True,
    "LOG_LEVEL": "INFO",
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
}


class PwPagesSpider(scrapy.Spider):
    """Fan out N Playwright renders to probe page/context limits and lifecycle.

    Env knobs (set per run by run_lifecycle.py):
      PW_N              number of distinct dynamic pages to render (default 8)
      PW_INCLUDE_PAGE   'true' to hold the Playwright page object in meta
      PW_CLOSE_PAGE     'true' to close the held page in the callback

    The page cap (PLAYWRIGHT_MAX_PAGES_PER_CONTEXT), context cap, and concurrency
    are passed as -s settings so the same spider produces the whole matrix.
    Holding pages open without closing them (PW_INCLUDE_PAGE=true,
    PW_CLOSE_PAGE=false) is the deliberate leak that exercises backpressure.
    """

    name = "pw_pages"
    custom_settings = PW_SETTINGS

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        n = int(os.environ.get("PW_N", "8"))
        include_page = os.environ.get("PW_INCLUDE_PAGE", "false").lower() == "true"
        for i in range(n):
            meta = {
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".product-card", timeout=5000)
                ],
                "k": i,
            }
            if include_page:
                meta["playwright_include_page"] = True
            yield scrapy.Request(
                f"{base_url}/dynamic/catalog?delay_ms=300&k={i}",
                callback=self.parse,
                errback=self.errback,
                meta=meta,
                dont_filter=True,
            )

    async def parse(self, response):
        close_page = os.environ.get("PW_CLOSE_PAGE", "false").lower() == "true"
        page = response.meta.get("playwright_page")
        cards = len(response.css(".product-card"))
        # Side-channel progress marker: survives an external kill, so we can tell
        # how many pages actually rendered before a wedge, independent of whether
        # the feed was ever finalized.
        progress_file = os.environ.get("PW_PROGRESS_FILE")
        if progress_file:
            with open(progress_file, "a", encoding="utf-8") as fh:
                fh.write(f"{response.meta.get('k')}\n")
        if page is not None and close_page:
            await page.close()
        yield {
            "source": "pw_pages",
            "k": response.meta.get("k"),
            "product_cards_found": cards,
            "held_page": page is not None,
            "closed_page": bool(page is not None and close_page),
            "outcome": "rendered",
        }

    def errback(self, failure):
        yield {
            "source": "pw_pages",
            "k": failure.request.meta.get("k"),
            "product_cards_found": 0,
            "outcome": "errback",
            "error_type": failure.type.__name__,
            "error_message": str(failure.value)[:200],
        }
