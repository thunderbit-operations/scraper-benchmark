# scrapy-playwright — provisional scorecard

**Provisional.** Based only on the completed material tests (see
`research-materials.md`). Not a final benchmark and not a cross-tool ranking.
Same weight template as the Scrapy single-tool pack where dimensions overlap.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 10 | 7 | clean venv install; extra cost = chromium download (~94 MiB) |
| Static extraction (inherited) | 10 | 10 | HTTP path unchanged: 12/12 static, 8/8 JSON API |
| Dynamic rendering | 14 | 12 | 8/8 local + 10 public with correct readiness; 0 with wrong/no wait |
| Readiness ergonomics | 10 | 7 | success hinges on the wait condition; silent 0 if wrong |
| Selective-render efficiency | 10 | 8 | same result, 29% lower peak RSS; wall-time tie |
| Memory observability | 10 | 6 | default stat 11× blind; documented extension still ~13% short |
| Lifecycle / backpressure | 12 | 8 | caps behave; unclosed pages wedge the crawl |
| Crawl control (inherited) | 8 | 8 | depth/scope/dedupe/export intact under selective rendering |
| Adversarial robustness | 8 | 7 | bounded timeout errback; late-DOM readiness nuance |
| License/compliance fit | 8 | 7 | BSD-3-Clause; proxy launch-level (documented), no anti-bot framing |
| **Total** | **100** | **80** | provisional research-material score only |

Scoring notes:
- Scores are evidence-anchored, not vibes; each cites a run in `research-materials.md`.
- Memory observability is marked down because the default `memusage/max` under-reports
  the true footprint ~11× and even the documented extension trails external RSS ~13%.
- Readiness ergonomics is marked down because a wrong/absent wait yields 0 cards with
  no error — a quiet failure mode.
