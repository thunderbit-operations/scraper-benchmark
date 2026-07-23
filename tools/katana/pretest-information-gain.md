# Katana — pre-test information-gain brief

Date: 2026-07-23. Gate document (TESTING-STANDARD). Design only.

Broad keyword: **`Katana web crawler`** (ProjectDiscovery `projectdiscovery/katana`).
Article boundary: Katana is an **endpoint-discovery crawler for recon/pipelines**
(what URLs/endpoints exist on a target), not a structured-data extractor like
Scrapy or a content converter like Jina/trafilatura. This pack judges **discovery
coverage and crawl discipline**, not field extraction.

## SERP scan (first ~20 results, official docs, README)

### What the results repeat (consensus, mostly unmeasured)

- Katana has two modes: **standard** (Go HTTP library — fast, no browser, misses
  post-rendered/dynamic endpoints) and **headless** (`-headless`, real browser
  context — legit fingerprint, "better coverage" of JS-rendered endpoints).
- It can **parse JavaScript for endpoints** even in requests mode (`-jc` /
  jsluice), pulling URLs out of `.js` files without a browser.
- Positioned for **automation pipelines / offensive-security recon**; scope
  controls (field scope `-fs`, in/out-scope regex), depth, known-files
  (robots/sitemap), and a **`-resume`** file are advertised.

### What is NOT measured anywhere (the gap)

1. **The standard-vs-headless discovery delta is asserted, never quantified.**
   Every source says headless "finds more" — none measures *how many more*, or
   *which kinds* of endpoints, against a page with known ground-truth endpoints.
2. **Where JS parsing (`-jc`) closes the gap vs where only a browser can.** If
   `-jc` recovers endpoints referenced in linked `.js` files, then headless's
   marginal value narrows to endpoints injected into the DOM **at runtime**.
   Nobody separates "endpoint is a string in a JS file" (parseable without a
   browser) from "endpoint only appears after JS executes" (needs headless).
3. **Scope discipline under a mixed graph** (in-scope + external links) is not
   demonstrated on ground truth.
4. **Resume correctness** is advertised but rarely shown actually recovering an
   interrupted crawl's state.

### Source evidence

- Official: [projectdiscovery/katana README](https://github.com/projectdiscovery/katana/blob/main/README.md), [Running Katana docs](https://docs.projectdiscovery.io/opensource/katana/running), [intro blog](https://projectdiscovery.io/blog/introducing-katana-the-best-cli-web-crawler).
- Upstream issues to scan at execution: `github.com/projectdiscovery/katana/issues`.
- Representative SERP: [Trickster Dev walkthrough](https://www.trickster.dev/post/katana-web-crawler-for-offensive-security-and-web-exploration/), [codeline repo-review](https://www.codeline.co/thoughts/repo-review/2024/katana-next-gen-web-crawler-for-automation-pipelines).

## Testable information-gain hypotheses

- **H1 (core, quantify the delta):** On a controlled local fixture with a known
  set of endpoints, headless mode discovers strictly more endpoints than standard
  mode — measure the exact count and *which* endpoints only headless finds.
- **H2 (adversarial, the real boundary):** `-jc` JS-parsing in **standard** mode
  recovers endpoints that live as strings in a linked `.js` file, closing most of
  the gap; headless's unique contribution is limited to endpoints injected into the
  DOM **at runtime** (not present as a literal anywhere in the fetched bytes).
  I.e. "use headless" is over-prescribed; `-jc` is enough unless endpoints are
  runtime-DOM-only.
- **H3 (scope):** Field/scope controls keep the crawl within the target host on a
  graph seeded with external links; out-of-scope hosts are not fetched.
- **H4 (resume):** An interrupted crawl resumed from the resume file does not
  re-crawl completed URLs and reaches the same final endpoint set.
- **H5 (cost):** Headless mode's wall-time / process cost vs standard on the same
  fixture (distribution over ≥3 runs), so the coverage gain has a price tag.

## Test matrix (tied to hypotheses)

| # | Test | Fixture route | Measures | H |
|---|---|---|---|---|
| 1 | standard crawl, endpoint recall | full local fixture | endpoints found vs ground truth | H1 |
| 2 | headless crawl, endpoint recall | same fixture | endpoints found vs ground truth; delta over #1 | H1 |
| 3 | standard + `-jc` (JS parsing) | page linking a `.js` with endpoint literals | JS-file endpoints recovered without a browser | H2 |
| 4 | runtime-DOM-only endpoint | page that injects a link via JS at runtime (no literal in bytes) | found only by headless? | H2 |
| 5 | scope discipline | graph with external-host links | out-of-scope hosts fetched = 0 | H3 |
| 6 | depth limit | crawl graph | endpoints/pages per depth honored | H3 |
| 7 | resume | interrupt mid-crawl, `-resume` | no re-crawl of done URLs; same final set | H4 |
| 8 | mode cost | full fixture, ≥3 isolated runs each | standard vs headless elapsed distribution | H5 |
| 9 | known-files | robots.txt / sitemap.xml routes | endpoints from known files surfaced | H1 |
| 10 | malformed/500 routes | 500 + broken-link routes | crawler continues, records status | robustness |

Fixture (local, Katana can hit 127.0.0.1 — unlike Jina): reuse the same-fixture
philosophy. Distinct endpoint classes are the key design: (a) endpoints as `<a
href>` in HTML, (b) endpoints as string literals inside a linked `.js` file, (c)
endpoints injected into the DOM only after JS runs. This triad is exactly what
separates standard / `-jc` / headless coverage. Public corroboration only if
needed and allowed; no anti-bot, no unauthorized targets.

## Boundary / compliance notes

- Evidence phase only; no article, no publish.
- Katana is an offensive-security recon tool by positioning. Keep all tests on the
  **local fixture** (and, if any public target, only the allowed to-scrape practice
  sites) — no scanning of third-party/production hosts, no auth bypass, no rate
  abuse. The article framing is "discovery coverage on controlled ground truth,"
  not "how to recon someone's site."
- Headless requires a Chromium; record install/runtime cost honestly.
- Report mode-cost as distributions; scope claims limited to the tested fixture.
