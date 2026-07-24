# ArchiveBox — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design rationale for the pack.

Broad keyword: **`ArchiveBox self-hosted web archiving`**
(`ArchiveBox/ArchiveBox`). Article boundary: ArchiveBox is a **self-hosted
archiver that runs many redundant preservation extractors over the same URL**
(wget/WARC, singlefile, dom, pdf, screenshot, readability, mercury, htmltotext,
title, favicon, headers, media, git, archive.org). It is not a single-output
scraper. This pack judges **which of those redundant outputs actually preserve
which content, and where they silently fail** — the queue focus verbatim:
"Measure which redundant preservation outputs are useful and where they fail."

## SERP scan (first ~20 results, official docs, GitHub issues)

### What the results repeat (consensus, mostly unmeasured)

- ArchiveBox saves "multiple redundant copies" of every page in many formats so
  that if one method fails another still preserves the page. Default extractors
  (per docs) are readability, mercury, htmltotext, singlefile, dom, wget, title,
  favicon, headers, archive.org; pdf/screenshot/media/git are commonly off by
  default.
- Dependency split is well known: **wget** = static HTML/WARC (no JS);
  **chromium** = screenshot/pdf/dom (JS-rendered); **node** = singlefile,
  readability, mercury.
- A large cluster of issues is about **extractors failing when a dependency is
  missing/mis-detected** in Docker: #1689 (chrome not detected), #1278 / #763
  (wrong/failed chrome for singlefile), #1386 / #1055 (singlefile fails), #774
  (single-file / readability FileNotFoundError), #847 (readability failure), #938
  (npm undocumented). Consensus: missing deps → silent/aborting extractor failure.
- Mercury (`@postlight/parser`, formerly mercury-parser) is **deprecated**; issues
  (#1105) and docs note it is being retired.

### What is NOT measured anywhere (the gap)

1. **No controlled measurement of WHICH redundant output captures WHICH content.**
   Everyone repeats "redundant copies" and "wget misses JS"; nobody plants known
   tokens (static vs runtime-injected vs JS-literal vs boilerplate) and reports the
   per-extractor capture matrix on ground truth.
2. **Whether the "redundant" outputs are truly independent.** ArchiveBox's own
   source routes readability/htmltotext/title through a shared `get_html()` that
   reads the chrome capture (dom > singlefile > wget). So their dynamic-content
   coverage may be *inherited* from chrome, not independent — untested publicly.
3. **The two article-text extractors (readability vs mercury) may disagree** on
   dynamic pages because one reads the local rendered capture and the other
   re-fetches the URL. Never quantified.
4. **Where each output fails even with all deps present.** The issue tracker is all
   about *missing* deps; the official image ships every dep valid — so what fails
   *then*? Unmeasured.

### Source evidence

- Official: [ArchiveBox README](https://github.com/ArchiveBox/ArchiveBox),
  [extractors apidocs](https://docs.archivebox.io/dev/apidocs/archivebox/archivebox.extractors.html),
  [Dependencies config](https://github.com/ArchiveBox/ArchiveBox/wiki/Configuration).
- Dependency-failure issue cluster: #1689, #1278, #763, #1386, #1055, #774, #847,
  #938, #690 (`github.com/ArchiveBox/ArchiveBox/issues`).
- Mercury deprecation: #1105 + docs `abx_plugin_mercury`.
- Source read at execution: `/app/archivebox/extractors/{mercury,readability,
  htmltotext,title}.py` inside the image.

## Testable information-gain hypotheses

- **H1 (capture matrix):** On a fixture with four planted tokens (STATIC visible /
  RUNTIME js-injected / JSLIT literal-in-js / BOILER chrome), enumerate which of
  the ~8 content outputs capture each token, plus output sizes and ArchiveBox's own
  per-extractor status. The redundant outputs do NOT all capture the same content.
- **H2 (runtime boundary):** RUNTIME (a token that appears as a contiguous string
  in ZERO served bytes; only the executed DOM materialises it) is captured only by
  chrome-based outputs (dom, singlefile, pdf, screenshot) and by text extractors
  that read those; static wget never gets it.
- **H3 (inherited, not independent — adversarial):** Disabling chrome
  (dom+singlefile+pdf+screenshot) makes readability & htmltotext silently fall back
  to wget HTML and LOSE the runtime token — proving their dynamic-content coverage
  is inherited from the chrome capture, not their own. Redundancy is a dependency
  tree, not N independent copies.
- **H4 (readability vs mercury divergence):** On the dynamic page the two
  article-text extractors disagree — one keeps the runtime token, the other drops
  it — because of different input sources (local rendered capture vs URL re-fetch),
  confirmed by source + server-side fetch counts.
- **H5 (static-vs-dynamic redundancy):** On the STATIC page wget/singlefile/dom are
  genuinely redundant (identical token set); on the DYNAMIC page the redundancy
  breaks exactly at the runtime content. Same tool, opposite redundancy verdict.
- **Robustness:** archiving an HTTP 500 route records failure cleanly without
  aborting the run.

## Test matrix (tied to hypotheses)

| # | Test | Fixture route | Measures | H |
|---|---|---|---|---|
| 1 | FULL config capture matrix | /static + /dynamic | per-output token capture + status + size | H1/H2/H5 |
| 2 | runtime-only token | /dynamic | which outputs get RUNTIME | H2 |
| 3 | NOCHROME fallback | /dynamic (dom/singlefile/pdf/shot off) | readability/htmltotext lose RUNTIME | H3 |
| 4 | mercury vs readability | /dynamic | divergent RUNTIME capture | H4 |
| 5 | fetch attribution | /dynamic, single-extractor configs | server-side hits per extractor | H4 |
| 6 | default-on set | config dump | which extractors run by default | H1 |
| 7 | stability | /dynamic ×3 | token matrix identical across runs | (determinism) |
| 8 | PDF text layer | /dynamic output.pdf | pypdf-extracted tokens | H2 |
| 9 | robustness | /failure/500 | clean-exit + per-extractor failed status | robustness |

Fixture (local, ArchiveBox in a container reaches host `127.0.0.1` via
`host.docker.internal`): three token classes are the key design — STATIC (in
initial HTML), RUNTIME (assembled at runtime, in no served byte), JSLIT (literal in
`app.js`), plus BOILER chrome. This separates byte-preservation from
rendered-capture from article-extraction.

## Boundary / compliance notes

- Evidence phase only; no article, no publish.
- All tests hit the **local fixture only** (no third-party/production targets).
  `SAVE_ARCHIVE_DOTORG` is disabled (would submit localhost to archive.org and is
  pointless/offsite); `SAVE_MEDIA` (yt-dlp) and `SAVE_GIT` disabled (no media/git
  on the fixture) — all disabling is disclosed, not hidden.
- The official image ships every dependency valid, so findings are NOT about
  missing deps (that is the entire public issue cluster); they are about behaviour
  with all deps present. Report that boundary explicitly.
- Container `docker rm` on exit (`--rm`); data dirs are local scratch, gitignored.
