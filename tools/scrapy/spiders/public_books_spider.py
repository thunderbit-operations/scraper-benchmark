import scrapy


class PublicBooksSpider(scrapy.Spider):
    name = "public_books"
    start_urls = ["https://books.toscrape.com/"]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.25,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response):
        for book in response.css("article.product_pod"):
            yield {
                "source": "books_toscrape_home",
                "title": book.css("h3 a::attr(title)").get(),
                "price": book.css(".price_color::text").get(),
                "availability": " ".join(book.css(".availability::text").getall()).strip(),
                "rating_class": book.css("p.star-rating::attr(class)").get(),
                "detail_url": response.urljoin(book.css("h3 a::attr(href)").get()),
                "page_url": response.url,
            }
