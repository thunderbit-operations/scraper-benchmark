import os

import scrapy
from scrapy_playwright.page import PageMethod


PW_SETTINGS = {
    "ROBOTSTXT_OBEY": True,
    "DEPTH_LIMIT": 2,
    "DOWNLOAD_DELAY": 0.02,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    "LOG_LEVEL": "INFO",
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
}


class MixedCrawlGraphSpider(scrapy.Spider):
    """Selective rendering inside one Scrapy crawl.

    Static routes are fetched over plain HTTP (no browser). Only the /dynamic/
    route opts into Playwright via meta. Scrapy's own scheduler, depth limit,
    dedupe, and export stay in charge; the browser is invoked per-request, not
    globally. This is the actual decision point the review targets.
    """

    name = "mixed_crawl_graph"
    custom_settings = PW_SETTINGS

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield self._request(base_url)

    def _needs_browser(self, url: str) -> bool:
        if os.environ.get("PW_RENDER_MODE", "selective") == "all":
            return True
        return "/dynamic/" in url

    def _page_methods(self, url: str) -> list:
        # The dynamic route needs its delayed cards; everything else only needs a
        # loaded body. Using a card-wait on card-less pages would time out and drop
        # them, so the readiness condition is chosen per URL — identical in both modes.
        if "/dynamic/" in url:
            return [PageMethod("wait_for_selector", ".product-card", timeout=5000)]
        return [PageMethod("wait_for_selector", "body", timeout=5000)]

    def _request(self, url: str) -> scrapy.Request:
        if self._needs_browser(url):
            return scrapy.Request(url, callback=self.parse, meta={
                "playwright": True,
                "playwright_page_methods": self._page_methods(url),
            })
        return scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        rendered = bool(response.meta.get("playwright"))
        cards = response.css(".product-card")
        yield {
            "source": "mixed_crawl_graph",
            "url": response.url,
            "status": response.status,
            "depth": response.meta.get("depth", 0),
            "rendered_with_playwright": rendered,
            "title": response.css("title::text").get(),
            "product_cards_found": len(cards),
            "links_found": len(response.css("a::attr(href)").getall()),
        }

        base_url = os.environ["FIXTURE_BASE_URL"]
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)
            if url.startswith(base_url):
                yield self._request(url)
