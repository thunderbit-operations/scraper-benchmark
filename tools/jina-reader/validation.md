# jina-reader — Independent Audit (validation)

**VERDICT: PASS WITH FIXES.** Every fidelity headline reproduced independently — I re-ran
`recompute_recall.py`, hand-grepped the 8 ground-truth authors across all seven `.md`
responses, md5-checked the byte-identity claims, and independently fired a key-free anonymous
`curl` that reproduced the 401. No headline, score-driving evidence, or ground-truth number is
wrong. Two **required** fixes returned to the worker (a scorecard arithmetic inconsistency and
an over-shipped "9× / two egresses / GET+POST" reproduction claim) and one **cosmetic** fix I
made in place (a stale cache-trap comment in the harness). Nothing that touches a headline or a
dimension score was auto-edited.

> **Live keyed reproduction is limited by the credential red line:** I never retrieved, read, or
> used a Jina API key, and ran no authenticated fetch. Independent verification was maximized
> within that boundary — (a) offline `recompute_recall.py` (no key), (b) direct inspection of the
> shipped response artifacts, and (c) a **key-free anonymous** `curl` (no `Authorization` header)
> to validate the 401 access finding. The keyed engine/cache matrix itself was verified against
> its **shipped** response bytes, not re-fetched live.

---

## Independent reproduction (what I actually ran / checked)

### 1. `recompute_recall.py` — CONSISTENT (offline, no key)
Ran `python3 tests/recompute_recall.py --check` on Python 3.14.2. All seven cells print `OK`;
`consistent_with_shipped_matrix = True`; exit 0. The regenerated `recall_recompute.json` is
**byte-identical** to the committed copy (the recompute is fully deterministic — my run left the
committed artifact untouched, verified with `cmp`). The script re-derives byte size, distinct-author
recall, and the two degradation flags from the `.md` files and asserts equality against
`engine-matrix.ndjson` — so recall/bytes are provably computed, not hand-typed.

### 2. Hand-grep of the 8 authors — matches the matrix cell-for-cell
Independently (not via the script) grepped `Einstein/Rowling/Austen/Monroe/Gide/Edison/Roosevelt/Martin`
in each response, and md5-checked byte-identity:

| file | my recall | matrix | bytes | md5 group |
|---|:--:|:--:|--:|---|
| `nc_js_direct.md` | **0/8** | 0/8 | 348 | unique (nav chrome only) |
| `nc_js_default.md` (auto) | **8/8** | 8/8 | 1193 | `cce638…` |
| `nc_js_browser.md` | **8/8** | 8/8 | 1193 | `cce638…` |
| `nc_js_browser_wait.md` | **8/8** | 8/8 | 1193 | `cce638…` |
| `cached_js.md` (warm) | **8/8** | 8/8 | 1193 | `cce638…` |
| `nc_static_default.md` | **8/8** | 8/8 | 1787 | `e430af…` |
| `nc_static_direct.md` | **8/8** | 8/8 | 1787 | `e430af…` |

- **H2 confirmed:** `direct` = 0/8 on JS; `browser`/`auto` = 8/8, byte-identical. `nc_js_direct.md`
  is 348 B of nav only ("Login", "Next →", "Made with ❤ by Zyte") — the ten quotes never appear.
- **H3 confirmed and the load-bearing control holds:** `nc_static_direct.md` is **8/8 and
  md5-identical to `nc_static_default.md`** (`e430af…`). This is what proves `direct` = a pure HTTP
  fetch, JS-blind by design, not a lossy engine. The isolation is real, not asserted.
- **Timing reversal (FINDING-04) confirmed from the ndjson:** order `direct 0.99 < browser+wait 1.77
  < browser 1.94 < auto 4.81`; `auto/browser = 2.48` ("~2.5×" ✓), `auto/direct = 4.86` ("~4.9×" ✓),
  warm `auto` 0.956 ("0.96" ✓), static `direct 0.94 < auto 1.69` ✓. Properly caveated as
  single-run / medium confidence with non-crossing operator bands (never used to crown a "fastest").

### 3. Key-free anonymous `curl` — 401 independently reproduced
I sent, from this egress, **no-`Authorization`** requests to `https://r.jina.ai/https://example.com`
and `.../https://quotes.toscrape.com/`. Both returned **HTTP 401**, body
`{"code":401,"name":"AuthenticationRequiredError","status":40103, … "bad network reputation (AS7922)"}`.
This independently reproduces the pack's core access finding (H4/FINDING-05). **Bonus corroboration
of the ASN caveat:** the error blamed **AS7922** from *my* egress too — a different network than the
pack's AS25820 — which strengthens the pack's "don't trust the error's ASN, it's a stale/hardcoded
label" sidebar rather than weakening it.

### 4. Cache honesty — HONEST in prose, one stale comment fixed
All **five** markdown docs correctly demote the cold stale-cache 0/8 to an **unreproduced
observation, explicitly NOT a headline** (research-materials "Cache — honest degradation note, NOT a
headline"; scorecard "never a headline (no shipped artifact)"; README "no headline"; pretest "demoted
… to an observation"; metadata "no cache-trap claim is made"). The shipped `cached_js` cell is warm
**8/8, `cached_snapshot=false`**, which I confirmed. **No md doc fabricates a "cache 0/8 vs no-cache
8/8" A/B off a non-existent artifact.** The single residual defect was in the harness itself:
`run_engine_matrix.sh` still carried `# Cache trap: … returns a stale, quote-less snapshot` as fact
over the `cached_js` fetch — contradicting the pack's own downgrade. I **fixed that comment in place**
(cosmetic) to state the cell is the warm/full snapshot and that the stale 0/8 could not be reproduced.

---

## Required fixes (returned to the worker — NOT auto-edited)

### R1 — Scorecard total does not equal the sum of its dimension scores
Weights sum to 100 ✓, but the eleven dimension **scores** (5, 7, 12, 9, 6, 6, 7, 7, 6, 6, 3) sum to
**74**, while both `scorecard.md` (line 24) and `research-materials.md` (line 256) state **Total = 70**.
A 4-point internal inconsistency (parts ≠ stated whole). I did **not** pick a side — the worker must
reconcile whether the intended total is 74 or a dimension score is mis-stated. (The "70" is labeled
provisional / "do not sum into a headline," which limits blast radius, but a scorecard whose parts
don't add up is still a required fix. This is the check the mozilla-readability pack passed by
re-adding to 84; this pack fails it by 4.)

### R2 — "reproduced 9× across two egresses / GET+POST / header variants" over-shoots the shipped artifacts
The claim appears in `README.md` (58–59), `pretest` (127), `research-materials.md` (168, 231:
"reproduced 9× …"; 164: "two independent egress points"), and `scorecard.md` (30). But the shipped
evidence is **4 `.txt` logs, all GET, all from a single egress** (`95.169.4.109 / AS25820`). The
second egress, the POST attempts, the header variants, and observations 5–9 are **not shipped**. The
underlying 401 finding is solid (4 targets + my own independent anon curl), but the *multiplicity*
quantifiers are claim-without-artifact (methodology Part 6 rule 2). Fix: either ship the remaining
logs, or soften to what's shipped — e.g. "401 on all 4 public targets from one datacenter egress
(2026-07-10); a second egress / POST / header variants observed but not shipped (Gap)."

## Cosmetic fix applied in place
- **F1 (done):** `tests/run_engine_matrix.sh` — replaced the misleading `# Cache trap: … returns a
  stale, quote-less snapshot` comment with an accurate note (warm/full 8/8 cell; stale 0/8 observed
  once, not reproduced; no cache-trap claim). Aligns the harness with the pack's own honest position;
  changes no computed value, headline, or score.

---

## Four-class leak audit (Part 6)

- **D1 self-contradicting winner — PASS.** No "Jina fidelity is high" sentence is contradicted by
  `direct` 0/8 (it is isolated as by-design via the static-8/8 control); no "fast" crown exists —
  FINDING-04 explicitly names `auto` the **slowest** and refuses to crown a fastest. Scorecard latency
  6/10 and JS-fidelity 12/14 are consistent with the evidence.
- **D2 blind instrument — PASS.** The recall counter registers **both** absence (0/8 on `direct`-JS,
  nav only) and presence (8/8 where the eight named authors actually appear); a "found" requires the
  real surname token. The 0-vs-8 split proves it is not stuck-on.
- **D3 mis-attribution — PASS.** The 0/8 is **not** blamed on a Jina defect: the `direct`-on-static
  8/8 control attributes it to rendering-mode choice. The ASN mismatch is held as a caveat, not a bug
  (and my own egress independently shows the AS7922 label is spurious).
- **D4 claim-without-artifact — PASS WITH FIXES.** Every recall/byte number resolves to a shipped
  `.md` (re-run + hand-grep). The two misses are **R2** (the 9×/two-egress/POST/header-variant
  multiplicity) and the now-fixed harness comment; the unreproduced stale cache hit and the un-run
  anon/keyed A/B are both correctly listed as Gaps, not asserted.

## Novelty three-classification — Gate-1 CLEAN
No EXCLUSIVE sits on a documented qualitative fact.
- Engine values exist / `browser` renders JS / `curl`/`direct` doesn't; anonymous throttled, key
  recommended → **DOCUMENTED**. Correct.
- Anonymous 401 `AuthenticationRequiredError` → **KNOWN-ISSUE (#1222)**. Correctly credits prior art
  and under-claims (I could not open #1222 within the red line, but tagging it KNOWN-ISSUE errs toward
  under-claiming, which is the safe direction).
- `direct` 0/8-vs-8/8 ground-truth recall, `direct`-on-static isolation, `auto`-slowest timing
  reversal, access-vs-fidelity decomposition → **EXCLUSIVE (quantification / framing+measurement)** —
  each scoped to a measurement or a synthesis, none to a qualitative discovery. This is the exact place
  a weaker pack mislabels; it does not.

## Anti-hardcoding lint — PASS
Recall/bytes are computed by `recompute_recall.py` from the `.md` files (verified by re-run **and**
independent hand-grep); the `AUTHORS` list is the ground-truth token set, not a stored result; the
shell harness `recall()` greps the response files at run time. No recall/byte conclusion is a hand-typed
constant.

## Secret / abspath / cleanliness scan — CLEAN
- **No real key anywhere.** `grep -rE 'jina_[A-Za-z0-9]{15,}'` over all publish-bound files surfaces
  **only** the four `jina_*_response.txt` filenames and the literal `jina_...` placeholder in
  README/metadata/harness comments. `run_engine_matrix.sh` uses `Authorization: Bearer $JINA_KEY`
  (env-read) and `: "${JINA_KEY:?…}"` (aborts if unset) — **no literal token**.
- **No `Bearer <token>` literal, no `sk-ant`/`sk-or-`/`ghp_`/`AKIA`.**
- **No abspath** (`/Users/richardli`, `/var/folders`, `/private/var`) in any file.
- **No leaked auth in artifacts:** the four 401 logs contain no `Authorization`/`Cookie`/`Set-Cookie`/
  `x-api-key`. `.gitignore` excludes `.env` / `*.key` / logs; the `.md`/`.ndjson`/`.txt`/`.json`
  evidence is intentionally committed.

---

## Residual gaps the writer must keep (the pack lists these — keep them)
1. **Direct anon-vs-keyed fidelity byte-diff not run** (blocked by the 401 from this egress) — H1 rests
   on decomposition; the honest limit is explicitly written. Keep it framed that way; needs a
   residential IP where anonymous returns 200.
2. **Timing is single-run, not a distribution** — the 3-rep bands are operator-observed, not shipped.
3. **Cache stale-hit not reproduced** — no artifact, no headline. Keep as-is.
4. **Boilerplate precision not scored**; single JS fixture, single machine; paid tier / `s.jina.ai` /
   MCP / ReaderLM-v2 all out of scope.

---

_Audited 2026-07-24 in the pack's own layout: ran `recompute_recall.py` (deterministic, committed
artifact left byte-identical), hand-grepped the 8-author recall matrix, md5-verified the byte-identity
claims, and independently reproduced the anonymous 401 with a key-free curl. **Live keyed reproduction
is limited by the credential red line (no key retrieved/used); verification was maximized within that
boundary.** No stray files left in the pack (scratch backup lives outside it)._

**Net status: PASS WITH FIXES.** All fidelity headlines (H2 0/8-vs-8/8, H3 `direct`=pure-HTTP via the
static-twin 8/8, H4 hard 401, FINDING-04 timing reversal, H1 access-vs-fidelity decomposition)
reproduce exactly and are honestly caveated; the cache stale-hit is correctly an unreproduced
observation, not a headline; D1–D3 clean, D4 clean after the two returned fixes; novelty Gate-1 clean;
anti-hardcoding, secret, and abspath scans clean. Required before publishing: **R1** (scorecard total
70 ≠ score sum 74) and **R2** (soften/ship the "9× / two egresses / GET+POST / header variants" claim
to match the 4 shipped GET-from-one-egress logs). One cosmetic harness comment fixed in place.
