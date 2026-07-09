# Crawl4AI pack

Tested version: **0.9.0** (Apache-2.0). [Project on GitHub](https://github.com/unclecode/crawl4ai).

Crawl4AI is a browser-backed, LLM-oriented crawler: it drives a real headless browser and converts pages to Markdown, with optional CSS-schema structured extraction.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
crawl4ai-setup            # downloads browser assets (Playwright + Patchright) — sizeable
python run_tests.py
```

`run_tests.py` starts a local fixture server, exercises static/dynamic extraction, an article page, a deep crawl, an intentional 500, plus two public practice sites, and writes JSON + Markdown to `results/`.

## What's in `results/`

- `local_static_*` / `local_dynamic_*` — static and JS-rendered catalog extraction (Markdown + CSS schema)
- `local_article_markdown.*` — article extraction (note the retained boilerplate)
- `local_bfs_deep_crawl.json` — BFS deep crawl (mixed success — see caveat)
- `local_failure_500.json` — the intentional 500 (mislabeled "anti-bot" by a minimal-text heuristic)
- `local_arun_many_product_details.json` — concurrent batch crawl
- `public_books_to_scrape.*`, `public_quotes_js.*` — public practice sites
- `screenshots/` — rendered-page proof; `metadata/` — GitHub/PyPI snapshots (2026-07-07)

## Honest caveats (also in the root METHODOLOGY)

- The intentional 500 was labeled "anti-bot protection" by a minimal-text heuristic — not a real anti-bot wall.
- Raw Markdown includes nav/footer boilerplate unless a content filter is configured.
- Deep crawls do not auto-wait for dynamic pages; direct dynamic crawls with `wait_for` do.
- First-time setup downloads two browser stacks — budget disk/bandwidth.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
