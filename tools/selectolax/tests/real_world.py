#!/usr/bin/env python3
"""Real-world dirty HTML: accuracy parity + speed across parsers.

For each fetched real page we run the SAME extraction task on 6 parsers:
  - all <a href> (count + set of hrefs)
  - all headings h1..h6 (count + concatenated text length)
  - all <img src> (count)
We compare selectolax Lexbor against lxml as the reference and flag any
DISAGREEMENT in element counts (the interesting robustness findings: different
parsers recover differently from real malformed markup).

Speed: p50 over 30 iters of the full extraction per parser per page. bs4 builds
cyclic trees; each iteration's result is dropped with `del r` and we run ONE
gc.collect() after warm-up, before the timed loop (not between every iteration),
keeping GC enabled throughout, consistent with the other benchmarks.

FIXTURE ADMISSION GATE (methodology v3 gate 2):
  Before a page is allowed to count toward the accuracy tally, it must pass:
    (1) title-keyword check   - the <title> contains an expected keyword
    (2) element-count floor   - >= expected minimum links / headings / imgs
    (3) block-page signature  - title/body must NOT match anti-bot challenge
                                phrases ("pardon our interruption", "are you a
                                human", "verify you are human", captcha, etc.)
  Pages that FAIL admission are still recorded (with the reason) but are EXCLUDED
  from the "N of M identical" accuracy statement -- exactly as httpbin's fetch
  timeout was disclosed rather than hidden. v2 let an eBay "Pardon Our
  Interruption" challenge page (2 links / 1 heading / 0 imgs) count toward
  "10 of 11 identical"; this gate makes that impossible.
"""
import gc
import json
import os
import re
import time

REAL = os.environ.get("SLX_REAL_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "fixtures", "real")
RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")

# Per-fixture admission spec: title keyword (lowercased substring) + element floors.
# Floors are deliberately loose (structure sanity, not exact counts).
ADMISSION = {
    "news_bbc.html":                 {"title_kw": "bbc",        "min_links": 50, "min_headings": 5, "min_imgs": 0},
    "news_hackernews.html":          {"title_kw": "hacker news", "min_links": 100, "min_headings": 0, "min_imgs": 0},
    "ecommerce_books.html":          {"title_kw": "books to scrape", "min_links": 40, "min_headings": 5, "min_imgs": 10},
    "ecommerce_webscraper_allinone.html": {"title_kw": "web scraper", "min_links": 20, "min_headings": 3, "min_imgs": 2},
    "docs_python.html":              {"title_kw": "python",     "min_links": 100, "min_headings": 3, "min_imgs": 0},
    "docs_mdn_array.html":           {"title_kw": "array",      "min_links": 100, "min_headings": 10, "min_imgs": 0},
    # old.reddit r/programming: the <title> is just the subreddit name ("programming"),
    # not "reddit". Match the subreddit; the body-signature block check still guards
    # against a login/block interstitial.
    "forum_reddit.html":             {"title_kw": "programming", "min_links": 100, "min_headings": 0, "min_imgs": 0},
    "wiki_scraping.html":            {"title_kw": "web scraping", "min_links": 100, "min_headings": 5, "min_imgs": 0},
    "gov_whitehouse.html":           {"title_kw": "white house", "min_links": 50, "min_headings": 3, "min_imgs": 0},
    "spa_quotes_js.html":            {"title_kw": "quotes",     "min_links": 3, "min_headings": 0, "min_imgs": 0},
    "oldstyle_craigslist.html":      {"title_kw": "craigslist", "min_links": 50, "min_headings": 0, "min_imgs": 0},
}

# Anti-bot / challenge-page signatures (checked against title + first 4KB of text).
BLOCK_SIGNATURES = [
    "pardon our interruption",
    "are you a human",
    "verify you are human",
    "verify you're human",
    "please verify",
    "access denied",
    "captcha",
    "unusual traffic",
    "checking your browser",
    "enable javascript and cookies",
    "request unsuccessful",
]


def pct(xs, p):
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def extract_selectolax(ParserCls, html):
    t = ParserCls(html)
    hrefs = [n.attributes.get("href") for n in t.css("a") if n.attributes.get("href")]
    heads = t.css("h1, h2, h3, h4, h5, h6")
    head_text_len = sum(len((n.text() or "")) for n in heads)
    imgs = [n.attributes.get("src") for n in t.css("img") if n.attributes.get("src")]
    title_node = t.css_first("title")
    title = title_node.text() if title_node else ""
    body_text = (t.body.text() if t.body else "") or ""
    return {"n_links": len(hrefs), "n_headings": len(heads),
            "head_text_len": head_text_len, "n_imgs": len(imgs),
            "hrefs": hrefs, "title": title, "body_head": body_text[:4096]}


def extract_lxml(html):
    import lxml.html
    t = lxml.html.fromstring(html)
    hrefs = [n.get("href") for n in t.cssselect("a") if n.get("href")]
    heads = t.cssselect("h1, h2, h3, h4, h5, h6")
    head_text_len = sum(len((n.text_content() or "")) for n in heads)
    imgs = [n.get("src") for n in t.cssselect("img") if n.get("src")]
    return {"n_links": len(hrefs), "n_headings": len(heads),
            "head_text_len": head_text_len, "n_imgs": len(imgs), "hrefs": hrefs}


def extract_bs4(html, feat):
    from bs4 import BeautifulSoup
    t = BeautifulSoup(html, feat)
    hrefs = [n.get("href") for n in t.select("a") if n.get("href")]
    heads = t.select("h1, h2, h3, h4, h5, h6")
    head_text_len = sum(len(n.get_text() or "") for n in heads)
    imgs = [n.get("src") for n in t.select("img") if n.get("src")]
    return {"n_links": len(hrefs), "n_headings": len(heads),
            "head_text_len": head_text_len, "n_imgs": len(imgs), "hrefs": hrefs}


def extract_parsel(html):
    from parsel import Selector
    s = Selector(text=html)
    hrefs = [h for h in s.css("a::attr(href)").getall()]
    heads = s.css("h1, h2, h3, h4, h5, h6")
    head_text_len = sum(len("".join(h.css("::text").getall())) for h in heads)
    imgs = s.css("img::attr(src)").getall()
    return {"n_links": len(hrefs), "n_headings": len(heads),
            "head_text_len": head_text_len, "n_imgs": len(imgs), "hrefs": hrefs}


def timed(fn, iters=30):
    # GC enabled throughout; per-iteration result freed via `del r`. One collect
    # before timing clears warmup garbage. Consistent with the other benchmarks;
    # no per-iteration full collect (kept out of the timed region regardless).
    for _ in range(2):
        r = fn()
        del r
    gc.collect()
    xs = []
    for _ in range(iters):
        t0 = time.perf_counter()
        r = fn()
        xs.append((time.perf_counter() - t0) * 1000)
        del r
    return pct(xs, 50)


def admit(page, sx):
    """Return (admitted: bool, reason: str). sx is the selectolax_lexbor extract."""
    spec = ADMISSION.get(page)
    title_l = (sx.get("title") or "").lower()
    body_l = (sx.get("body_head") or "").lower()
    # 3) block-page signatures first (most important)
    for sig in BLOCK_SIGNATURES:
        if sig in title_l or sig in body_l:
            return False, f"block-page signature matched: {sig!r}"
    if spec is None:
        return False, "no admission spec (unknown fixture)"
    # 1) title keyword
    if spec["title_kw"] not in title_l:
        return False, f"title missing keyword {spec['title_kw']!r} (got {title_l[:60]!r})"
    # 2) element floors
    if sx["n_links"] < spec["min_links"]:
        return False, f"links {sx['n_links']} < floor {spec['min_links']}"
    if sx["n_headings"] < spec["min_headings"]:
        return False, f"headings {sx['n_headings']} < floor {spec['min_headings']}"
    if sx["n_imgs"] < spec["min_imgs"]:
        return False, f"imgs {sx['n_imgs']} < floor {spec['min_imgs']}"
    return True, "ok"


def main():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser

    pages = sorted(f for f in os.listdir(REAL) if f.endswith(".html") and not f.startswith("_"))
    results = {}
    disagreements = []
    admitted_pages = []
    excluded_pages = []

    for page in pages:
        raw_bytes = open(os.path.join(REAL, page), "rb").read()
        html = raw_bytes.decode("utf-8", errors="replace")
        size = len(raw_bytes)

        r = {}
        r["selectolax_lexbor"] = extract_selectolax(LexborHTMLParser, html)
        r["selectolax_modest"] = extract_selectolax(HTMLParser, html)
        r["lxml"] = extract_lxml(html)
        r["bs4_lxml"] = extract_bs4(html, "lxml")
        r["bs4_htmlparser"] = extract_bs4(html, "html.parser")
        r["parsel"] = extract_parsel(html)

        # ---- ADMISSION GATE ----
        admitted, reason = admit(page, r["selectolax_lexbor"])
        (admitted_pages if admitted else excluded_pages).append(page)

        speed = {}
        speed["selectolax_lexbor"] = timed(lambda: extract_selectolax(LexborHTMLParser, html))
        speed["selectolax_modest"] = timed(lambda: extract_selectolax(HTMLParser, html))
        speed["lxml"] = timed(lambda: extract_lxml(html))
        speed["bs4_lxml"] = timed(lambda: extract_bs4(html, "lxml"))
        speed["bs4_htmlparser"] = timed(lambda: extract_bs4(html, "html.parser"))
        speed["parsel"] = timed(lambda: extract_parsel(html))

        ref = r["lxml"]
        cmp = {}
        for p in r:
            cmp[p] = {
                "n_links": r[p]["n_links"],
                "d_links_vs_lxml": r[p]["n_links"] - ref["n_links"],
                "n_headings": r[p]["n_headings"],
                "d_headings_vs_lxml": r[p]["n_headings"] - ref["n_headings"],
                "n_imgs": r[p]["n_imgs"],
                "d_imgs_vs_lxml": r[p]["n_imgs"] - ref["n_imgs"],
                "speed_p50_ms": round(speed[p], 4),
            }
            # only surface disagreements for ADMITTED pages
            if admitted and (cmp[p]["d_links_vs_lxml"], cmp[p]["d_headings_vs_lxml"], cmp[p]["d_imgs_vs_lxml"]) != (0, 0, 0):
                disagreements.append({"page": page, "parser": p,
                                      **{k: cmp[p][k] for k in cmp[p] if k.startswith(("d_", "n_"))}})

        results[page] = {
            "size_bytes": size,
            "admitted": admitted,
            "admission_reason": reason,
            "title": r["selectolax_lexbor"].get("title", "")[:120],
            "compare": cmp,
            "lxml_ref": {"n_links": ref["n_links"], "n_headings": ref["n_headings"], "n_imgs": ref["n_imgs"]},
        }

        sx = cmp["selectolax_lexbor"]
        flag = "OK " if admitted else "EXCL"
        print(f"[{flag}] {page:<34} size={size:>7} | lexbor links={sx['n_links']:>4}(Δ{sx['d_links_vs_lxml']:+d}) "
              f"head={sx['n_headings']:>3}(Δ{sx['d_headings_vs_lxml']:+d}) img={sx['n_imgs']:>4}(Δ{sx['d_imgs_vs_lxml']:+d}) "
              f"| {reason if not admitted else ''}")

    # accuracy tally over ADMITTED pages only
    n_admitted = len(admitted_pages)
    lexbor_matches = sum(
        1 for p in admitted_pages
        if (results[p]["compare"]["selectolax_lexbor"]["d_links_vs_lxml"],
            results[p]["compare"]["selectolax_lexbor"]["d_headings_vs_lxml"],
            results[p]["compare"]["selectolax_lexbor"]["d_imgs_vs_lxml"]) == (0, 0, 0))

    out = {
        "meta": {
            "n_fixtures_on_disk": len(pages),
            "n_admitted": n_admitted,
            "n_excluded": len(excluded_pages),
            "admitted_pages": admitted_pages,
            "excluded_pages": excluded_pages,
            "lexbor_vs_lxml_identical_admitted": f"{lexbor_matches} of {n_admitted}",
            "gc_policy": "enabled throughout; per-iter result freed via del; no gc.disable",
            "note": "accuracy tally counts ADMITTED pages only; excluded pages disclosed",
        },
        "pages": results,
        "disagreements_vs_lxml": disagreements,
    }
    with open(os.path.join(RAW, "real_world.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nADMITTED {n_admitted}/{len(pages)}; EXCLUDED {excluded_pages}")
    print(f"selectolax-Lexbor vs lxml identical on {lexbor_matches} of {n_admitted} admitted pages")
    print(f"{len(disagreements)} parser/page count-disagreements vs lxml (admitted pages)")
    for d in disagreements:
        print("  DISAGREE", d["page"], d["parser"],
              f"Δlinks={d['d_links_vs_lxml']:+d} Δhead={d['d_headings_vs_lxml']:+d} Δimg={d['d_imgs_vs_lxml']:+d}")
    print("written", os.path.join(RAW, "real_world.json"))


if __name__ == "__main__":
    main()
