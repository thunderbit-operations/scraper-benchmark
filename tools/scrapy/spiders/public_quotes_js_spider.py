import scrapy


class PublicQuotesJsSpider(scrapy.Spider):
    name = "public_quotes_js"
    start_urls = ["https://quotes.toscrape.com/js/"]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.25,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response):
        quotes = response.css("div.quote")
        yield {
            "source": "quotes_toscrape_js_without_js_rendering",
            "url": response.url,
            "status": response.status,
            "quote_nodes_found": len(quotes),
            "script_count": len(response.css("script")),
            "body_chars": len(response.text),
            "note": "Scrapy did not execute client-side JavaScript; CSS selectors for rendered quote nodes found no quote cards.",
        }
