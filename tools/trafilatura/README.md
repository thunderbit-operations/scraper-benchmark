# trafilatura pack

Tested version: **2.1.0** (Apache-2.0). [Project on GitHub](https://github.com/adbar/trafilatura).

trafilatura is a lightweight, pure-Python **main-content / article extractor**: HTML in, clean text / Markdown / JSON (with metadata) out, boilerplate (nav / aside / footer) stripped. It is a content extractor, **not** a structured-catalog scraper, and it does **not** render JavaScript.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_tests.py
```

`run_tests.py` starts a local fixture server, then exercises an article page (text / Markdown / JSON extraction), a static catalog (the structured-scraping boundary), an intentional HTTP 500, plus one public practice page, and writes JSON / Markdown / text to `results/`.

## What's in `results/`

- `local_article.{txt,md,json}` — article extraction: title + **3/3** body paragraphs, author + date metadata, boilerplate (Login / Subscribe / Copyright) fully removed
- `local_catalog_extraction.txt` — the catalog: **12/12** product names appear as text but **0 structured rows** (id/name/price), the real content-extractor-vs-scraper boundary
- `local_failure_500.json` — the intentional 500: `fetch_url` returns `None` (fails gracefully, no raise)
- `local_fixture_ground_truth.json` — the ground truth the run is checked against
- `public_books_product.{txt,md}` — a Books to Scrape product page, used as the allowed demo-site content target
- `trafilatura-test-summary.json` — machine-readable summary of every check above
- `metadata/` — GitHub / PyPI snapshots (2026-07-07 / 2026-07-09)

## Honest caveats (also in the root METHODOLOGY)

- **Content extractor, not a structured scraper.** On the catalog it returned all 12 product names as a text blob but **0 structured rows** — for id/name/price rows you still need a parser/selector tool. This is a boundary, not a failure.
- **No JavaScript rendering.** trafilatura works on the HTML it fetches; JS-injected content is out of reach.
- Clean side: the article fixture came back with the title, 3/3 paragraphs, and author + date, with every boilerplate marker stripped.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
