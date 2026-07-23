import json
import os

import scrapy


class NativeDynamicApiSpider(scrapy.Spider):
    """Replay the backing JSON API over plain HTTP (no browser). The dynamic
    catalog is populated from /api/dynamic-products; hitting the API directly
    recovers all 8 records without rendering. Same fixture as the Scrapy pack."""

    name = "native_dynamic_api"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/api/dynamic-products", callback=self.parse)

    def parse(self, response):
        products = json.loads(response.text)
        for product in products:
            yield {
                "source": "native_dynamic_api",
                "product_id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "category": product["category"],
            }
