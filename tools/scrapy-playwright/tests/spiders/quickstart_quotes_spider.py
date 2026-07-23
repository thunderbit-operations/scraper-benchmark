import scrapy


class QuickstartQuotesSpider(scrapy.Spider):
    """Official Scrapy quickstart shape: a static quotes page, no Playwright."""

    name = "quickstart_quotes"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
        "USER_AGENT": "Mozilla/5.0 (compatible; ThunderbitBenchmark/1.0; +https://thunderbit.com)",
    }

    async def start(self):
        yield scrapy.Request("https://quotes.toscrape.com/tag/humor/", callback=self.parse)

    def parse(self, response):
        for quote in response.css("div.quote"):
            yield {
                "source": "quickstart_quotes",
                "text": quote.css("span.text::text").get(),
                "author": quote.css("small.author::text").get(),
            }
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
