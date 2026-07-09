import os

import scrapy


class LocalCrawlGraphSpider(scrapy.Spider):
    name = "local_crawl_graph"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DEPTH_LIMIT": 2,
        "DOWNLOAD_DELAY": 0.02,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(base_url, callback=self.parse)

    def parse(self, response):
        yield {
            "source": "local_crawl_graph",
            "url": response.url,
            "status": response.status,
            "depth": response.meta.get("depth", 0),
            "title": response.css("title::text").get(),
            "links_found": len(response.css("a::attr(href)").getall()),
        }

        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)
            if url.startswith(os.environ["FIXTURE_BASE_URL"]):
                yield scrapy.Request(url, callback=self.parse)
