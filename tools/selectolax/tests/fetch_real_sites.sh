#!/usr/bin/env bash
# Fetch real-world HTML from a diverse set of sites into artifacts/fixtures/real/
# Rate-limited (sleep between requests), realistic UA, follows redirects.
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)/artifacts/fixtures/real"
mkdir -p "$DIR"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

fetch () {
  local name="$1" url="$2"
  echo "=== $name  <-  $url"
  curl -sL --max-time 40 --compressed \
    -A "$UA" \
    -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
    -H 'Accept-Language: en-US,en;q=0.9' \
    -o "$DIR/$name.html" -w "  http=%{http_code} size=%{size_download} time=%{time_total}s type=%{content_type}\n" \
    "$url"
  sleep 2
}

# category : name : url
fetch "news_bbc"          "https://www.bbc.com/news"
fetch "news_hackernews"   "https://news.ycombinator.com/"
fetch "ecommerce_books"   "https://books.toscrape.com/"
fetch "docs_python"       "https://docs.python.org/3/library/index.html"
fetch "docs_mdn_array"    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array"
fetch "forum_reddit"      "https://old.reddit.com/r/programming/"
fetch "wiki_scraping"     "https://en.wikipedia.org/wiki/Web_scraping"
fetch "gov_whitehouse"    "https://www.whitehouse.gov/"
fetch "spa_quotes_js"     "https://quotes.toscrape.com/js/"
# NOTE: eBay category pages return a "Pardon Our Interruption" anti-bot challenge
# page (2 links / 1 heading / 0 imgs) to datacenter/curl clients. It was dropped
# from the fixture set and replaced with a real, scrapeable e-commerce fixture.
# The fixture admission gate in real_world.py also rejects any block page by
# title/body signature, so a re-fetched challenge page can never re-enter the tally.
fetch "ecommerce_webscraper_allinone" "https://webscraper.io/test-sites/e-commerce/allinone"
fetch "oldstyle_craigslist" "https://sfbay.craigslist.org/search/sss"
fetch "misc_httpbinhtml"  "https://httpbin.org/html"

echo "=== sizes ==="
ls -la "$DIR"
