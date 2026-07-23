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
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 15000,
}


class PwDynamicSpider(scrapy.Spider):
    """Render the dynamic catalog with Playwright under a controlled readiness policy.

    Env knobs (set per run by the harness so behavior is data, never hardcoded):
      PW_TARGET      catalog | never | late   (default catalog)
      PW_WAIT_MODE   none | fixed | selector  (default selector)
      PW_DELAY_MS    server-side render delay  (default 450)
      PW_FIXED_MS    wait_for_timeout value for fixed mode (default 100)
      PW_TIMEOUT_MS  wait_for_selector timeout (default 5000)
    """

    name = "pw_dynamic"
    custom_settings = PW_SETTINGS

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        target = os.environ.get("PW_TARGET", "catalog")
        wait_mode = os.environ.get("PW_WAIT_MODE", "selector")
        delay_ms = os.environ.get("PW_DELAY_MS", "450")
        fixed_ms = int(os.environ.get("PW_FIXED_MS", "100"))
        timeout_ms = int(os.environ.get("PW_TIMEOUT_MS", "5000"))

        path = {"catalog": "/dynamic/catalog", "never": "/dynamic/never", "late": "/dynamic/late"}[target]
        url = f"{base_url}{path}?delay_ms={delay_ms}"

        page_methods = []
        if wait_mode == "fixed":
            page_methods = [PageMethod("wait_for_timeout", fixed_ms)]
        elif wait_mode == "selector":
            page_methods = [PageMethod("wait_for_selector", ".product-card", timeout=timeout_ms)]
        # wait_mode == "none": no page methods, read immediately after load

        yield scrapy.Request(
            url,
            callback=self.parse,
            errback=self.errback,
            meta={
                "playwright": True,
                "playwright_page_methods": page_methods,
                "run_config": {
                    "target": target,
                    "wait_mode": wait_mode,
                    "delay_ms": int(delay_ms),
                    "fixed_ms": fixed_ms,
                    "timeout_ms": timeout_ms,
                },
            },
        )

    def parse(self, response):
        cfg = response.meta["run_config"]
        cards = response.css(".product-card")
        names = [c.css(".product-name::text").get() for c in cards]
        yield {
            "source": "pw_dynamic_rendered",
            "url": response.url,
            "status": response.status,
            "run_config": cfg,
            "product_cards_found": len(cards),
            "product_names": names,
            "status_text": response.css("#status::text").get(),
            "outcome": "rendered",
        }

    def errback(self, failure):
        cfg = failure.request.meta.get("run_config", {})
        yield {
            "source": "pw_dynamic_rendered",
            "url": failure.request.url,
            "run_config": cfg,
            "product_cards_found": 0,
            "outcome": "errback",
            "error_type": failure.type.__name__,
            "error_message": str(failure.value)[:300],
        }
