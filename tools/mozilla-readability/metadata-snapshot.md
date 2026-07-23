# mozilla-readability — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [mozilla/readability](https://github.com/mozilla/readability) |
| Stars | **11,355** |
| Open issues | **307** |
| License | **Apache-2.0** |
| Default branch | **main** |
| Last push | **2026-07-09T11:32:27Z** |
| Latest GitHub *Release* object | **none** (repo publishes no GitHub Release objects; `releases/latest` → 404) |
| Latest tag | **0.6.0** (also `0.5.0`, `0.4.4`) |
| npm `latest` | **0.6.0** (published **2025-03-03**) |
| Version tested | **0.6.0** (`npm install @mozilla/readability` resolved 0.6.0) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| @mozilla/readability | **0.6.0** |
| jsdom | **29.1.1** |
| Node | **v22.22.3** |
| trafilatura (comparison arm) | **2.1.0** |
| Python (comparison + metrics) | **3.12.13** (uv venv) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-24** |

## Algorithm constants read from the installed source (v0.6.0)

Read from `node_modules/@mozilla/readability/Readability.js` and
`Readability-readerable.js` (documented; cited so the mechanism claims are grounded):

- `DEFAULT_CHAR_THRESHOLD = 500` — min article text length for a "successful" parse
  (below it, the flag-removal **sieve** runs; final fallback returns the longest attempt,
  or `null` only if no attempt has any text).
- `DEFAULT_N_TOP_CANDIDATES = 5`; `DEFAULT_TAGS_TO_SCORE = "section,h2,h3,h4,h5,h6,p,td,pre"`.
- Content score per scored paragraph: `1 + (commaCount + 1) + min(floor(len/100), 3)`;
  paragraphs `< 25` chars are not counted; scores propagate to ancestors with dividers
  (parent 1, grandparent 2, great-grandparent+ `level·3`).
- **Sibling-append gate** (`grabArticle`, ~line 1471): a sibling of the top candidate is
  appended iff its own score clears the sibling threshold, **or**
  `nodeLength > 80 && linkDensity < 0.25`, **or**
  `nodeLength < 80 && nodeLength > 0 && linkDensity === 0 && contains a period`.
- `_getLinkDensity = Σ(linkText.length · coef) / textLength`, `coef = 0.3` for `#` hrefs
  else `1`.
- `unlikelyCandidates` regex matches `…|comment|…|footer|…|menu|…|related|…|sidebar|…|social|sponsor|…`
  (stripped under `FLAG_STRIP_UNLIKELYS` unless `okMaybeItsACandidate` also matches).
- `isProbablyReaderable(doc, {minContentLength = 140, minScore = 20})`: over visible
  `p, pre, article` (+ `div>br` parents, minus `li p`), `score += sqrt(textContentLength − minContentLength)`;
  returns `true` once `score > minScore`.

## Exact commands run

Everything is offline for the Readability arm (fixtures are local). The trafilatura arm
also reads the saved fixture HTML.

```bash
cd tools/mozilla-readability

# 0) deps (Node) — versions pinned in package-lock.json
npm install                 # @mozilla/readability 0.6.0 + jsdom 29.1.1

# 1) build the annotated fixtures + ground truth (single source of truth)
node tests/build_fixtures.mjs        # -> tests/fixtures/*.html + ground_truth.json

# 2) Readability extraction arm (raw text + isProbablyReaderable sweeps; NO metrics)
node tests/run_readability.mjs       # -> artifacts/raw/readability_raw.json

# 3) trafilatura comparison arm (same fixtures) — needs a Python venv
uv venv .venv && uv pip install --python .venv/bin/python trafilatura   # 2.1.0
.venv/bin/python tests/run_trafilatura.py    # -> artifacts/raw/trafilatura_raw.json

# 4) compute precision/recall for BOTH tools from raw text vs labels (one tokenizer)
.venv/bin/python tests/metrics.py    # -> *_metrics.json + comparison.json
```

## Reproducibility notes (honest)

- **A DOM implementation is required at runtime.** `@mozilla/readability` is pure JS but
  operates on a `document`; under Node that means **jsdom** (29.1.1 here). The "no
  dependencies" framing is about the algorithm, not the runtime DOM.
- **Anti-hardcoding split.** `run_readability.mjs` returns only raw extracted
  `textContent` + `isProbablyReaderable` booleans/sweeps + the measured promo link
  density; **all precision/recall is computed in `metrics.py`** from that raw text vs the
  labels in `ground_truth.json`. No metric constant is written by hand.
- **Ground truth is generated with the HTML.** `build_fixtures.mjs` emits the HTML and
  `ground_truth.json` together; every unit's vocabulary is disjoint (sentinel-prefixed
  words), so an extracted token maps to exactly one unit and "recovered/leaked" is exact
  substring/token membership.
- **One tokenizer** for both tools: lowercase, split on `[^a-z0-9]+` — the word-overlap
  word-F1口径 that matches the public benchmark.
- **Fresh DOM per parse.** `Readability.parse()` mutates the DOM, so each call builds a
  new jsdom; determinism verified (3 reps identical on all 22 fixtures).
- **Redaction.** `$HOME`→`~` and `$TMPDIR` / `/var/folders` temp paths → `<TMP>` in every
  written JSON (both arms).
- **Synthetic scope.** All numbers are controlled fixtures; the public real-corpus figure
  (scrapinghub Readability.js word-F1 0.887) is cited as the authoritative real-world
  ranking and is **not** reproduced here.
- **`node_modules/` and `.venv/` are NOT shipped** (gitignored); `package-lock.json`
  pins the JS versions and the exact `uv pip install trafilatura` pins 2.1.0.
