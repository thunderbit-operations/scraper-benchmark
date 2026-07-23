import os

import scrapy


class NativeDynamicSpider(scrapy.Spider):
    """Baseline: fetch the dynamic catalog WITHOUT Playwright.

    Ground truth = 8 cards, rendered by JS. Native Scrapy sees the empty shell,
    so product_cards_found is expected to be 0. This reproduces the exact gap the
    Playwright handler is supposed to close, inside the SAME fixture and pack.
    """

    name = "native_dynamic"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/dynamic/catalog", callback=self.parse)

    def parse(self, response):
        cards = response.css(".product-card")
        yield {
            "source": "native_dynamic_without_rendering",
            "url": response.url,
            "status": response.status,
            "product_cards_found": len(cards),
            "status_text": response.css("#status::text").get(),
            "script_count": len(response.css("script")),
        }
