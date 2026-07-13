# selectolax pack

Tested version: **0.4.10** (MIT binding; bundles LGPL-2.1 Modest + Apache-2.0 Lexbor engines). [Project on GitHub](https://github.com/rushter/selectolax).

selectolax is a Python binding to the **Modest** and **Lexbor** C engines: a fast HTML5 parser with **CSS selectors**. It is a *parsing library* — **no XPath, no JavaScript rendering, no crawl loop**. Because of that, this pack does **not** use the shared catalog fixtures the crawler packs use; it reproduces a **parser benchmark** instead.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_tests.py          # full run: 3 independent benchmark runs (~15 min)
QUICK=1 python run_tests.py   # fast smoke run (fewer iterations, 1 run)
```

`run_tests.py` generates synthetic fixtures, then runs: the CSS-coverage matrix, an adversarial-input sweep, a non-UTF-8 encoding probe, API/claim verification, production-dimension probes, the real dirty-HTML accuracy check (against committed captures), and the performance benchmarks (via `run_all.py`, which executes each benchmark in **3 fresh processes** and reports cross-run variance). All output lands in `results/`.

Environment of record: **macOS arm64 / Python 3.14.2**. Some results (see FINDING-03 below) are platform-sensitive — re-run on yours.

## What's measured (and what the raw results say)

Every number in `results/*.json` is computed at runtime — no result field is a hardcoded conclusion.

- **Performance vs lxml / BeautifulSoup / parsel** across 1 KB–10 MB (`results/bench_parse.json`, `results/bench_isolate.json`): p50/p90 as **median across 3 runs** with cross-run spread. Before timing, all parsers must produce the **same content hash** (sorted titles + hrefs), or the cell is excluded — so no parser is compared while silently doing less work.
- **selectolax vs BeautifulSoup**: ~10–15x faster on realistic parse+extract (the true multiple depends on the BeautifulSoup backend and how much you extract).
- **selectolax vs lxml**: a **tie** on the full task (<5%). On **parse-only**, **lxml is faster on this machine** (~30%) — see caveat.
- **CSS coverage** (`results/css_coverage.json`): a 41-case matrix across **five** engines incl. **soupsieve**, ending in a **fault-finding pass** (`:lang()`, `:dir()`, two-case `[a=v i]`) chosen to break Lexbor. Each cell runs in an isolated subprocess because some combinations abort the interpreter.
- **Memory** (`results/bench_memory_import.json`): RSS delta measured with **tracemalloc off** (the ranking number), and tracemalloc peak measured in a **separate process** (kept only to show how badly tracemalloc mis-ranks C-backed parsers).
- **Adversarial inputs, encoding, production dimensions** (`results/adversarial.json`, `results/encoding_probe.json`, `results/production_dims.json`): edge inputs, non-UTF-8 behavior, thread scaling / memory growth / node lifecycle.
- **Real dirty HTML** (`results/real_world.json`): 11 committed live-site captures behind a **fixture-admission gate** (title keyword + element floors + anti-bot-signature detection). An eBay "Pardon Our Interruption" challenge page was rejected and replaced; httpbin's fetch timeout is disclosed.

## Honest caveats (also in the root METHODOLOGY)

- **Known behaviors, reproduced — not discovered here.** Two headline behaviors are documented upstream and are reproduced/root-caused/quantified by this pack, with links:
  - Lexbor **silently drops `<a>` and other content inside `<template>`** (spec-inert `DocumentFragment`): [selectolax#146](https://github.com/rushter/selectolax/issues/146), engine [lexbor#170](https://github.com/lexbor/lexbor/issues/170). Switch to the Modest backend to see it. The reverse gotcha: lxml/bs4/Modest surface inert template content a browser never renders.
  - **Non-UTF-8 bytes** are stored raw and decode late: `.text()` **silently corrupts** (Lexbor → U+FFFD, Modest → dropped bytes) while `.html` **raises** `UnicodeDecodeError`. Related to [selectolax#40](https://github.com/rushter/selectolax/issues/40). Fix: pass a decoded `str`.
- **FINDING-03 is counter-consensus and single-platform.** On this bench, **lxml's parse step is faster than selectolax's** — the opposite of most published benchmarks (e.g. [aows.jpt.sh](https://aows.jpt.sh/parsing/) reports selectolax ~4x faster on parse-only). It was cross-checked across four page sizes and two lxml APIs, but it is **macOS arm64 / Python 3.14 only**. Run it on your platform before trusting the direction.
- **Modest crashes the interpreter on `:dir()`** (SIGABRT), and lacks `:is()`/`:where()`. Lexbor is the feature-complete backend; Modest is legacy (its C library is unmaintained).
- **CSS is not a clean sweep for Lexbor.** After the fault-finding pass, **soupsieve scores highest** (it handles `:lang()`/`:dir()`/`[i]`); Lexbor is `UNSUPPORTED` on `:lang()`/`:dir()`. Lexbor still beats the cssselect stack on `:has()` and `[i]`.

Absolute latency numbers are a within-machine signal — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
