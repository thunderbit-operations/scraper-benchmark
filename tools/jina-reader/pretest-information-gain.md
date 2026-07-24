# Jina Reader — pre-test information-gain brief

Date: 2026-07-23 (design); **calibrated to measured results 2026-07-24** — see the
"Post-run calibration" section at the end for each hypothesis's verdict. Gate
document (TESTING-STANDARD). Design only — **no API key appears here or in any test
file/log/commit; the key is supplied at run time via `$JINA_KEY` from the
environment.**

Broad keyword: **`Jina Reader` / `URL to Markdown`**.
Article boundary vs Wave B **Mozilla Readability**: Jina Reader is the **hosted
URL→Markdown service** (server-side fetch, engine choice, access friction, and the
end-to-end markdown you actually get back). Mozilla Readability is the
**extraction library/algorithm** run locally on ground-truth HTML. Jina *uses*
Readability internally, so the two must not cannibalize: this pack judges the
**service** (access + engine + fidelity of the returned markdown), not the
algorithm in isolation.

## SERP scan (first ~20 results, official docs, README)

### What the results repeat (consensus, mostly unmeasured)

- Prepend `https://r.jina.ai/` to any URL → clean, LLM-friendly Markdown; no signup
  for basic use. Companion `s.jina.ai` does search→Markdown.
- Pipeline is described as headless Chrome → Mozilla Readability (boilerplate
  strip) → Turndown (HTML→Markdown).
- Free tier is rate-limited; an API key raises quota (sources conflict: "1M" vs
  "10M free tokens"). Rate limits cited: anonymous is "most aggressively
  rate-limited"; keyed free ~100 RPM / 100K TPM, paid higher; IP cap ~10k/60s.
- Documented failure modes: datacenter-IP fetches are blocked by Reddit/X/LinkedIn;
  client-side React/Shadow DOM pages return an almost-empty shell; paywalled/login
  content needs an authenticated session.

### What is NOT measured anywhere (the gap)

1. **Does the API key change OUTPUT FIDELITY, or only access/rate?** Every source
   treats the key as a quota lever. None diffs the *markdown* of the same page
   fetched anonymously vs keyed. The Reader API exposes fidelity headers
   (`X-Engine`, `X-Target-Selector`, `X-Wait-For-Selector`, `X-Respond-With`,
   `X-Retain-Links/Images`, `X-Respond-Timing`) — whether these work anonymously
   or require a key, and whether they change what content survives, is untested.
2. **Engine choice on a controlled JS page.** `X-Engine` = `auto` (default) /
   `browser` / `curl`. Nobody measures whether `curl` silently drops JS-rendered
   content that `browser`/`auto` recovers, on the same URL with known ground truth.
3. **Fidelity against ground truth.** No source measures paragraph/entity recall or
   boilerplate-stripping precision (does it also strip *real* content?) of the
   returned markdown against a known page. It's all "looks clean."
4. **Access-friction is asserted, not quantified.** The prior `tools/jina-reader/`
   material only shows anonymous cloud access is rejected. The exact status/error,
   on which targets, and whether the key + engine headers fix it, is unquantified.

### Source evidence (Tier 1 first)

- Official: [jina-ai/reader README](https://github.com/jina-ai/reader), [Reader API page](https://jina.ai/reader/), [Reader-LM note](https://jina.ai/news/reader-lm-small-language-models-for-cleaning-and-converting-html-to-markdown/)
- Upstream issue tracker to scan at execution: `github.com/jina-ai/reader/issues`
  (confirm engine/fidelity issues before tagging anything EXCLUSIVE).
- Representative SERP: [Web2MD "how it works and when it fails"](https://web2md.org/blog/jina-reader-url-prefix-guide), [Elastic Search Labs tutorial](https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader), rate/pricing roundups ([linkstartai](https://www.linkstartai.com/en/agents/jina), [coldiq](https://coldiq.com/tools/jina-ai)).

## Testable information-gain hypotheses

- **H1 (core, separates the two axes):** The key buys **access/rate**, not
  **fidelity**. On a page both can fetch, keyed vs anonymous markdown is identical
  (byte- or normalized-diff). → measures fidelity independent of access.
- **H2 (adversarial):** `X-Engine=curl` drops JS-rendered content that
  `browser`/`auto` recover on the *same* URL with known ground truth — i.e. the
  default `auto` already renders JS and `curl` is a silent-loss trap.
- **H3 (fidelity vs ground truth):** On a controlled public page, measure returned
  markdown recall of known content and precision of boilerplate stripping (flag any
  real content wrongly dropped — the Readability inheritance risk).
- **H4 (access friction, quantified):** Characterize the exact anonymous-vs-keyed
  access outcome (status/error/rate) on allowed public targets; separate "cannot
  fetch" from "fetched but low fidelity."
- **H5 (fidelity headers gating):** Which of `X-Target-Selector` /
  `X-Respond-With` / `X-Retain-Links` actually take effect anonymously vs keyed.

## Test matrix (tied to hypotheses)

| # | Test | Target | Measures | H |
|---|---|---|---|---|
| 1 | anonymous vs keyed, default engine, same URL | quotes.toscrape.com (static) | normalized markdown diff = fidelity delta | H1 |
| 2 | `X-Engine` direct(curl) vs browser vs auto | quotes.toscrape.com/js (JS) | author recall (ground truth = **8 distinct authors**, page 1) per engine | H2 |
| 3 | markdown recall + boilerplate precision | books.toscrape.com + a stable Wikipedia article | known-entity recall; real-content-dropped count | H3 |
| 4 | access outcome matrix | allowed public targets | status/error/latency anonymous vs keyed | H4 |
| 5 | `X-Respond-With` formats | one static target | markdown/html/text/screenshot returned as specified | H5 |
| 6 | `X-Target-Selector` scoping | one static target | does selector scoping take effect keyed vs anon | H5 |
| 7 | repeated calls (cache/rate) | one target | `X-No-Cache` behavior; rate-limit onset | H4 |

Ground truth is defined from the public target's known structure — the **8 distinct
authors** on `quotes.toscrape.com/js` page 1 (10 quotes; Einstein appears 3×), which
ties this pack to the same public JS target used by the Scrapy / scrapy-playwright
packs — a same-target thread across the series. The `/js/page/N/` deeper pages are
**not** scored (their proxied fetch proved unreliable at execution and was dropped).
Allowed targets: quotes/books to-scrape, a stable Wikipedia article.
**Forbidden:** logins, paywalls, Reddit/X/LinkedIn, anti-bot targets, proxy abuse.

## Boundary / compliance notes

- Not an article yet. Evidence phase only.
- The key is used only at runtime from the keychain; it is never written to a file,
  log, JSON artifact, or commit. Test scripts read it from an env var populated by
  the operator at run time.
- Fidelity claims must be scoped to the tested public targets and the fetch date
  (Jina's server behavior can change); report as-of.
- If H1 turns out true (key = access not fidelity), that IS the article's
  information gain — say it plainly rather than implying the key improves quality.

## Post-run calibration (2026-07-24)

The gate PROCEEDED; results are in `research-materials.md`. Each hypothesis's
verdict against what was actually measured:

- **H1 (key = access, not fidelity) — SUPPORTED by decomposition.** Anonymous
  datacenter access is a hard 401 (access denied); with the key held constant,
  fidelity varies only by `X-Engine` + cache. So the key isolates to access. Honest
  limit: the cleanest test (keyed-vs-anonymous byte-diff on a page *both* can fetch)
  was **impossible** — anonymous is 401 from this egress — so H1 rests on the
  decomposition, not a direct A/B. Residential-IP retest → Gap. **This is the pack's
  core headline.**
- **H2 (`X-Engine: direct`/`curl` drops JS content) — SUPPORTED.** `direct` = 0/8 on
  the JS page (348 B, nav only); `browser`/`auto` = 8/8 (1193 B). But the default is
  `auto`, which renders JS, so the loss is a **silent trap only if `direct` is
  explicitly chosen**, not a default-path failure.
- **H3 (fidelity vs ground truth) — SUPPORTED for recall + isolation.** `direct`
  returns **8/8 on the server-rendered twin**, byte-identical to `auto` — proving
  `direct` is a pure HTTP fetch, blind only to client-side JS (by design), not a
  lossy engine. Full boilerplate-**precision** scoring deferred → Gap.
- **H4 (access friction quantified) — SUPPORTED.** Binary 401→200; anonymous 401
  `AuthenticationRequiredError` reproduced on all 4 shipped anonymous GET probes
  (single datacenter egress). The error's ASN (AS7922 vs real AS25820) is a caveat, not a bug.
- **H5 (header gating anon vs keyed) — DOWNGRADED to a Gap.** Anonymous is 401, so
  "does header X work anonymously" is unanswerable from this egress. Keyed, three
  headers were confirmed to take effect (`X-No-Cache`, `X-Engine`,
  `X-Wait-For-Selector`); the anon-vs-keyed gating question is deferred.
- **New (unplanned) finding — timing reversal.** Default `auto` is the **slowest**
  engine (4.81s cold) while producing output identical to `browser` (1.94s); `direct`
  fastest (0.99s). Counterintuitive; EXCLUSIVE quantification. In-pack single-run
  (medium confidence) with operator-observed 3-rep ranges.
- **Cache — demoted from a candidate headline to an observation.** A cold stale 0/8
  snapshot was seen once but could **not** be reproduced after warming (shipped
  `cached_js` is warm 8/8). No cache-trap claim is made; only `X-No-Cache` →
  fresh and warm-vs-cold latency are asserted.
