import os

import scrapy


class NativeStaticCatalogSpider(scrapy.Spider):
    """HTTP-only static catalog recall. Same fixture as the Scrapy pack."""

    name = "native_static_catalog"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.02,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/static/catalog?page=1", callback=self.parse)

    def parse(self, response):
        for product in response.css(".product-card"):
            yield {
                "source": "native_static_catalog",
                "product_id": product.attrib.get("data-product-id"),
                "name": product.css(".product-name::text").get(),
                "category": product.css(".category::text").get(),
                "price": product.css(".price::text").get(),
                "rating": product.css(".rating::text").get(),
                "page_url": response.url,
            }
        next_page = response.css(".next-page::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
