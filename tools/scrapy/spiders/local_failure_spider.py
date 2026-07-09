import os

import scrapy


class LocalFailureSpider(scrapy.Spider):
    name = "local_failure"
    handle_httpstatus_list = [500]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/failure/500", callback=self.parse)

    def parse(self, response):
        yield {
            "source": "local_failure_500",
            "url": response.url,
            "status": response.status,
            "body_text": response.text,
            "handled": response.status == 500,
        }
