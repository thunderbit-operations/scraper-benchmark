import os

import scrapy


class NativeFailureSpider(scrapy.Spider):
    """HTTP 500 handling without a browser. Records the status rather than
    crashing, so the error path is captured as data."""

    name = "native_failure"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
        "HTTPERROR_ALLOW_ALL": True,
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/failure/500", callback=self.parse, errback=self.errback)

    def parse(self, response):
        yield {
            "source": "native_failure_500",
            "url": response.url,
            "status": response.status,
            "outcome": "response_received",
        }

    def errback(self, failure):
        yield {
            "source": "native_failure_500",
            "url": failure.request.url,
            "outcome": "errback",
            "error_type": failure.type.__name__,
        }
