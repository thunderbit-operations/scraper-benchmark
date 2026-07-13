# selectolax pack

Tested version: **0.4.10** (MIT binding; bundles LGPL-2.1 Modest + Apache-2.0 Lexbor engines). [Project on GitHub](https://github.com/rushter/selectolax).

selectolax is a Python binding to the **Modest** and **Lexbor** C engines: a fast HTML5 parser with **CSS selectors**. It is a *parsing library* — **no XPath, no JavaScript rendering, no crawl loop**. Because of that, this pack does **not** use the shared catalog fixtures the crawler packs use; it reproduces a **parser benchmark** instead.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_tests.py          # full run: 3 separate benchmark runs (~15 min)
QUICK=1 python run_tests.py   # fast smoke run (fewer iterations, 1 run)
```

`run_tests.py` generates synthetic fixtures, then runs: the CSS-coverage matrix, an adversarial-input sweep, a non-UTF-8 encoding probe, API/claim verification, the `<template>` minimal reproduction, production-dimension probes, the real dirty-HTML accuracy check (against committed captures), the performance benchmarks (via `run_all.py`, which executes each benchmark in **3 fresh processes** and reports cross-run variance), the parse-only two-lxml-API cross-check, and finally `build_summary.py` (which computes `selectolax-test-summary.json` from the raw JSONs). All output lands in `results/`.

Environment of record: **macOS arm64 / Python 3.14.2**. Some results (see FINDING-03 below) are platform-sensitive — re-run on yours.

## What's measured (and what the raw results say)

Every number in `results/*.json` is computed at runtime — no result field is a hardcoded conclusion. Even the roll-up `results/selectolax-test-summary.json` is **generated** by `tests/build_summary.py`, which derives every field from the other raw JSONs (so it can't drift from them).

- **Performance vs lxml / BeautifulSoup / parsel** across 1 KB–10 MB (`results/bench_parse.json`, `results/bench_isolate.json`): p50/p90 as **median across 3 runs** with cross-run spread. Before timing, all parsers must produce the **same content hash** (sorted titles + hrefs), or the cell is excluded — so no parser is compared while silently doing less work.
- **selectolax vs BeautifulSoup**: ~10–15x faster on realistic parse+extract (the true multiple depends on the BeautifulSoup backend and how much you extract).
- **selectolax vs lxml**: a **tie** on the full task at 100 KB / 1 MB (<5%), with Lexbor a genuine winner only at 10 MB (8.1%, non-overlapping runs). On **parse-only**, **lxml is faster on this machine** (~33%) — see caveat.
- **Bulk CSS query** (100k nodes, `results/bench_isolate.json`): lxml and selectolax-Modest are **tied** (within 2.6%, overlapping runs); Lexbor is ~15% slower. All three C engines are ~5-7x faster than parsel/BeautifulSoup. (selectolax is **not** the bulk-query winner — that framing was corrected.)
- **CSS coverage** (`results/css_coverage.json`): a 41-case matrix across **five** engines incl. **soupsieve**, ending in a **fault-finding pass** (`:lang()`, `:dir()`, two-case `[a=v i]`) chosen to break Lexbor. Each cell runs in an isolated subprocess because some combinations abort the interpreter.
- **Memory** (`results/bench_memory_import.json`): RSS delta measured with **tracemalloc off** (the ranking number), and tracemalloc peak measured in a **separate process** (kept only to show how badly tracemalloc mis-ranks C-backed parsers).
- **Adversarial inputs, encoding, production dimensions** (`results/adversarial.json`, `results/encoding_probe.json`, `results/production_dims.json`): edge inputs, non-UTF-8 behavior, thread scaling / memory growth / node lifecycle. The leak check samples **current RSS** (not a high-water mark) in a fresh subprocess and includes a **known-leak calibration** subject (climbs +198 MB) so "no leak" rests on a demonstrably sensitive instrument. On deeply-nested input, **lxml silently drops the deepest content (`has_deep: false`) while both selectolax engines keep it** — the mirror image of the `<template>` gotcha.
- **Real dirty HTML** (`results/real_world.json`): 11 committed live-site captures behind a **fixture-admission gate** (title keyword + element floors + anti-bot-signature detection). An eBay "Pardon Our Interruption" challenge page was rejected and replaced; httpbin's fetch timeout is disclosed.

## Caveats carried with the numbers (also in the root METHODOLOGY)

- **Known behaviors, reproduced — not discovered here.** Two headline behaviors are documented upstream and are reproduced/root-caused/quantified by this pack, with links:
  - Lexbor **silently drops `<a>` and other content inside `<template>`** (spec-inert `DocumentFragment`): [selectolax#146](https://github.com/rushter/selectolax/issues/146), engine [lexbor#170](https://github.com/lexbor/lexbor/issues/170). Switch to the Modest backend to see it. The reverse gotcha: lxml/bs4/Modest surface inert template content a browser never renders.
  - **Non-UTF-8 bytes** are stored raw and decode late: `.text()` **silently corrupts** (Lexbor → U+FFFD, Modest → dropped bytes) while `.html` **raises** `UnicodeDecodeError`. Related to [selectolax#40](https://github.com/rushter/selectolax/issues/40). Fix: pass a decoded `str`.
- **FINDING-03 is counter-consensus and single-platform.** On this bench, **lxml's parse step is faster than selectolax's** — the opposite of most published benchmarks (e.g. [aows.jpt.sh](https://aows.jpt.sh/parsing/) reports selectolax ~4x faster on parse-only). It was cross-checked across four page sizes and **two lxml APIs** (`lxml.html` + `lxml.etree`, committed in `results/etree_crosscheck.json` — both beat selectolax-Lexbor at every size), but it is **macOS arm64 / Python 3.14 only**. Run it on your platform before trusting the direction.
- **Modest crashes the interpreter on `:dir()`** (SIGABRT), and lacks `:is()`/`:where()`. Lexbor is the feature-complete backend; Modest is legacy (its C library is unmaintained).
- **CSS is not a clean sweep for Lexbor.** After the fault-finding pass, **soupsieve scores highest (41/41 vs Lexbor 39/41)** — it handles `:lang()`/`:dir()`/`[i]` and evaluates the README `:has()` compound correctly; Lexbor is `UNSUPPORTED` on `:lang()`/`:dir()`. Lexbor beats the **cssselect** stack (lxml/parsel) on `:has()` and `[i]`, but not soupsieve. (cssselect has parsed `:has()` since 1.2.0 / 2022-10; lxml/parsel mis-evaluate the compound — "supported but buggy," not "unsupported.")

Absolute latency numbers are a within-machine signal — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
