import scrapy


class QuickstartQuotesSpider(scrapy.Spider):
    name = "quickstart_quotes"
    start_urls = ["https://quotes.toscrape.com/tag/humor/"]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.25,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response):
        for quote in response.css("div.quote"):
            yield {
                "source": "quotes_toscrape_humor",
                "author": quote.css("span small::text").get(),
                "text": quote.css("span.text::text").get(),
                "tags": quote.css("div.tags a.tag::text").getall(),
                "page_url": response.url,
            }

        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)
