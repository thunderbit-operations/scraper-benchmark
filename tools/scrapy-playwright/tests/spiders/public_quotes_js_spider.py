import os

import scrapy
from scrapy_playwright.page import PageMethod


PW_SETTINGS = {
    "ROBOTSTXT_OBEY": True,
    "LOG_LEVEL": "INFO",
    "USER_AGENT": "Mozilla/5.0 (compatible; ThunderbitBenchmark/1.0; +https://thunderbit.com)",
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
}


class PublicQuotesJsSpider(scrapy.Spider):
    """Public JS-rendered practice page: quotes.toscrape.com/js/ WITH Playwright.

    The native Scrapy pack recorded 0 quote nodes on this same URL. With the
    browser handler and a selector wait, the JS-populated quotes should appear.
    Uses async start() (the code path that reliably wires up the Playwright
    handler in this Scrapy version) and an errback so a render failure is data.
    """

    name = "public_quotes_js"
    custom_settings = PW_SETTINGS

    async def start(self):
        yield scrapy.Request(
            "https://quotes.toscrape.com/js/",
            callback=self.parse,
            errback=self.errback,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "div.quote", timeout=15000)
                ],
            },
        )

    def parse(self, response):
        quotes = response.css("div.quote")
        yield {
            "source": "public_quotes_js_rendered",
            "url": response.url,
            "outcome": "rendered",
            "quote_nodes_found": len(quotes),
            "authors": sorted({q.css("small.author::text").get() for q in quotes if q.css("small.author::text").get()}),
        }

    def errback(self, failure):
        yield {
            "source": "public_quotes_js_rendered",
            "url": failure.request.url,
            "outcome": "errback",
            "quote_nodes_found": 0,
            "error_type": failure.type.__name__,
            "error_message": str(failure.value)[:300],
        }
