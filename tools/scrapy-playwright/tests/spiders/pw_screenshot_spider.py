import os

import scrapy
from scrapy_playwright.page import PageMethod


PW_SETTINGS = {
    "ROBOTSTXT_OBEY": True,
    "LOG_LEVEL": "INFO",
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
}


class PwScreenshotSpider(scrapy.Spider):
    """Render the dynamic catalog and capture a full-page screenshot as visual
    evidence that the browser path actually painted the JS-populated cards."""

    name = "pw_screenshot"
    custom_settings = PW_SETTINGS

    async def start(self):
        base_url = os.environ["FIXTURE_BASE_URL"]
        shot_path = os.environ["PW_SCREENSHOT_PATH"]
        yield scrapy.Request(
            f"{base_url}/dynamic/catalog?delay_ms=450",
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".product-card", timeout=5000),
                    PageMethod("screenshot", path=shot_path, full_page=True),
                ],
            },
        )

    def parse(self, response):
        cards = response.css(".product-card")
        yield {
            "source": "pw_screenshot",
            "url": response.url,
            "product_cards_found": len(cards),
            # Record a repo-relative path so no absolute home path leaks into the
            # published artifact; the write above still uses the absolute path.
            "screenshot_path": os.environ.get("PW_SCREENSHOT_REL", "artifacts/screenshots/dynamic_catalog_rendered.png"),
        }
