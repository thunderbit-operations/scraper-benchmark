import os

import scrapy


class LocalDynamicPageSpider(scrapy.Spider):
    name = "local_dynamic_page"

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
            "source": "local_dynamic_page_without_js_rendering",
            "url": response.url,
            "status": response.status,
            "product_cards_found": len(cards),
            "status_text": response.css("#status::text").get(),
            "script_count": len(response.css("script")),
            "note": "Scrapy downloaded source HTML but did not execute the JavaScript that populates product cards.",
        }
