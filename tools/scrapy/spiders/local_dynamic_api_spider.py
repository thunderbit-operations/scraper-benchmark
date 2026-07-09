import json
import os

import scrapy


class LocalDynamicApiSpider(scrapy.Spider):
    name = "local_dynamic_api"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/api/dynamic-products", callback=self.parse)

    def parse(self, response):
        for product in json.loads(response.text):
            yield {
                "source": "local_dynamic_api",
                "product_id": product["id"],
                "name": product["name"],
                "category": product["category"],
                "price": product["price"],
                "rating": product["rating"],
                "url": response.url,
            }
