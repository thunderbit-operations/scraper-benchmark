import os

import scrapy


class LocalArticleSpider(scrapy.Spider):
    name = "local_article"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        yield scrapy.Request(f"{base_url}/article/1", callback=self.parse)

    def parse(self, response):
        yield {
            "source": "local_article",
            "title": response.css("article h1::text").get(),
            "author": response.css(".author::text").get(),
            "date": response.css("time::text").get(),
            "body_paragraphs": [text.strip() for text in response.css("article p:not(.byline)::text").getall()],
            "nav_text": " ".join(text.strip() for text in response.css("nav::text").getall() if text.strip()),
            "footer_text": " ".join(text.strip() for text in response.css("footer::text").getall() if text.strip()),
            "url": response.url,
        }
