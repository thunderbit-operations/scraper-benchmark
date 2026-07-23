#!/usr/bin/env node
// build_fixtures.mjs — SINGLE SOURCE OF TRUTH for the annotated fixtures.
//
// Writes tests/fixtures/*.html and tests/fixtures/ground_truth.json together, so the
// HTML and its ground-truth labels can never drift. Every labeled text block carries a
// UNIQUE sentinel token (a single lowercase-alphanumeric word, e.g. "zzart01"), so
// downstream "recovered / leaked" is exact substring membership in the extracted text —
// never fuzzy-matched, never guessed. Ground truth records, per unit:
//   { id, label: "article"|"boilerplate", btype, sentinel, text }
// plus each fixture's structural intent. No metric is computed here.
//
// Determinism: pure string assembly, no randomness — byte-identical on every run.
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIX_DIR = join(HERE, "fixtures");
mkdirSync(FIX_DIR, { recursive: true });

// ---- helpers ---------------------------------------------------------------
// Deterministic per-unit vocabulary so token-level precision/recall is meaningful and
// fair: EVERY word begins with the unit's (unique) sentinel prefix, so the token sets
// of different units are DISJOINT — an extracted word maps to exactly one unit, letting
// token-level metrics detect partial extraction and boilerplate contamination cleanly.
// Occasional commas keep the comma-based scoring realistic; trailing period.
function hashStr(s) {
  let h = 2166136261 >>> 0;
  for (let k = 0; k < s.length; k++) {
    h ^= s.charCodeAt(k);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function makeText(sentinel, targetChars) {
  const words = [];
  let i = 0;
  let len = 0;
  while (len < targetChars) {
    let w = sentinel + hashStr(`${sentinel}:${i}`).toString(36).slice(0, 4);
    i++;
    if (i % 10 === 0) w += ","; // realistic comma cadence for the scorer
    words.push(w);
    len += w.length + 1;
  }
  return words.join(" ").replace(/,$/, "") + ".";
}

// A unit: label article|boilerplate, btype (nav/ad/aside/footer/related/comments/etc),
// sentinel token, and the plain text (unique-vocab prose) used for token-level GT.
function unit(id, label, btype, sentinel, proseChars = 160) {
  const text = makeText(sentinel, proseChars);
  return { id, label, btype, sentinel, text };
}

// paragraph HTML for a unit; optional link markup to control link density
function p(u, { linkChars = 0, tag = "p", cls = "", href = "/x" } = {}) {
  const clsAttr = cls ? ` class="${cls}"` : "";
  if (linkChars <= 0) return `<${tag}${clsAttr}>${u.text}</${tag}>`;
  // wrap the first `linkChars` chars of the text in an <a> to raise link density
  const head = u.text.slice(0, linkChars);
  const tail = u.text.slice(linkChars);
  return `<${tag}${clsAttr}><a href="${href}">${head}</a>${tail}</${tag}>`;
}

function htmlDoc(title, bodyInner) {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${title}</title></head><body>${bodyInner}</body></html>`;
}

const fixtures = {}; // name -> { html, description, units, intent }

function register(name, description, intent, units, html) {
  fixtures[name] = { description, intent, units, html };
  writeFileSync(join(FIX_DIR, `${name}.html`), html + "\n", "utf-8");
}

// ===========================================================================
// F1 — canonical, well-structured news article with realistic chrome.
// Article prose is inside <article>; chrome uses TYPICAL class names (nav/ad/sidebar/
// footer/comments hit the unlikelyCandidates regex → expected to strip). One extra
// "related/promo" block uses a NEUTRAL class + long low-link prose (the leak risk).
// ===========================================================================
{
  const A1 = unit("f1-art-01", "article", "body", "zzart01", 300);
  const A2 = unit("f1-art-02", "article", "body", "zzart02", 340);
  const A3 = unit("f1-art-03", "article", "body", "zzart03", 260);
  const A4 = unit("f1-art-04", "article", "body", "zzart04", 280);
  const NAV = unit("f1-nav", "boilerplate", "nav", "zznav01", 60);
  const AD = unit("f1-ad", "boilerplate", "ad", "zzad01", 90);
  const ASIDE = unit("f1-aside", "boilerplate", "aside", "zzaside01", 120);
  const FOOT = unit("f1-footer", "boilerplate", "footer", "zzfooter01", 80);
  const COMM = unit("f1-comments", "boilerplate", "comments", "zzcomments01", 150);
  // neutral-classed long low-link promo — dodges unlikely-regex, tests sibling append
  const PROMO = unit("f1-promo", "boilerplate", "related-promo-neutral", "zzpromo01", 200);
  const units = [A1, A2, A3, A4, NAV, AD, ASIDE, FOOT, COMM, PROMO];
  const body = `
<header class="site-header"><nav class="nav-menu">${NAV.text}</nav></header>
<div class="ad-banner">${AD.text}</div>
<div id="page">
  <article class="post-content">
    <h1>How Operations Teams Evaluate Web Scraping Tools</h1>
    ${p(A1)}
    ${p(A2)}
    ${p(A3)}
    ${p(A4)}
  </article>
  <p class="teaser-block">${PROMO.text}</p>
  <aside class="sidebar">${ASIDE.text}</aside>
</div>
<section class="comments">${COMM.text}</section>
<footer class="site-footer">${FOOT.text}</footer>`;
  register(
    "f1_canonical",
    "Well-formed news article in <article> with realistic chrome (nav/ad/sidebar/footer/comments on unlikely-regex classes) plus one neutral-classed long low-link promo sibling.",
    "Baseline article recall + per-boilerplate-class leak. Predict chrome strips; neutral promo is the leak risk (sibling append).",
    units,
    htmlDoc("Canonical article", body)
  );
}

// ===========================================================================
// F1-malformed — same content, misnested / unclosed tags (jsdom quirk sensitivity).
// ===========================================================================
{
  const A1 = unit("fm-art-01", "article", "body", "zzmart01", 300);
  const A2 = unit("fm-art-02", "article", "body", "zzmart02", 340);
  const A3 = unit("fm-art-03", "article", "body", "zzmart03", 260);
  const NAV = unit("fm-nav", "boilerplate", "nav", "zzmnav01", 60);
  const FOOT = unit("fm-footer", "boilerplate", "footer", "zzmfooter01", 80);
  const units = [A1, A2, A3, NAV, FOOT];
  // Intentionally malformed: unclosed <p>, misnested <b>/<i>, stray </div>
  const body = `
<header><nav class="nav-menu">${NAV.text}</nav>
<div id="page">
  <article class="post-content">
    <h1>Malformed article <b>bold <i>and italic</b> crossed</i>
    <p>${A1.text}
    <p>${A2.text}</p>
    <p>${A3.text}
  </article></div></div>
<footer>${FOOT.text}</footer>`;
  register(
    "f1_malformed",
    "Same shape as f1 but with unclosed <p>, misnested <b>/<i>, and a stray </div> — measures jsdom parse-quirk sensitivity of recall.",
    "Does malformed HTML (jsdom's HTML5 tree-builder recovery) change article recall vs the well-formed twin?",
    units,
    htmlDoc("Malformed article", body)
  );
}

// ===========================================================================
// F2-adv — the sibling-append inclusion boundary (source ~line 1471):
//   a sibling <p> of the top candidate is appended iff its own score clears the
//   sibling threshold OR (nodeLength > 80 && linkDensity < 0.25), OR
//   (nodeLength < 80 && linkDensity === 0 && contains a period).
// A decisive 4-paragraph <article> is the top candidate; the neutral-classed promo
// blocks are TRUE siblings (direct children of #page, not inside the article), each
// ~120 chars (>80, low self-score) varying ONLY link density, to isolate the 0.25 gate.
// ===========================================================================
// ONE promo sibling per fixture (isolation): a decisive 4-paragraph <article> is the
// clear top candidate; a single neutral-classed sibling <p> under #page is the only
// other block, so accumulation into #page can't flip the winner. Vary only the promo's
// length + link density across fixtures to map the append gate.
{
  const strongArticle = (prefix) => [
    unit(`${prefix}-art-01`, "article", "body", `${prefix}a1`, 320),
    unit(`${prefix}-art-02`, "article", "body", `${prefix}a2`, 300),
    unit(`${prefix}-art-03`, "article", "body", `${prefix}a3`, 300),
    unit(`${prefix}-art-04`, "article", "body", `${prefix}a4`, 280),
  ];
  const variants = [
    { name: "f2_sib_len120_ld000", sent: "zzsibp000", len: 120, linkChars: 0, btype: "sibling-len120-ld0.00", period: true },
    { name: "f2_sib_len120_ld015", sent: "zzsibp015", len: 120, linkChars: 18, btype: "sibling-len120-ld0.15", period: true },
    { name: "f2_sib_len120_ld029", sent: "zzsibp029", len: 120, linkChars: 35, btype: "sibling-len120-ld0.29", period: true },
    { name: "f2_sib_len120_ld050", sent: "zzsibp050", len: 120, linkChars: 60, btype: "sibling-len120-ld0.50", period: true },
    { name: "f2_sib_len60_period", sent: "zzsibsp", len: 60, linkChars: 0, btype: "sibling-len60-period-ld0", period: true },
    { name: "f2_sib_len60_noperiod", sent: "zzsibsn", len: 60, linkChars: 0, btype: "sibling-len60-noperiod-ld0", period: false },
  ];
  for (const v of variants) {
    const arts = strongArticle(v.name.replace(/[^a-z0-9]/g, "").slice(0, 8));
    const promo = unit(`${v.name}-promo`, "boilerplate", v.btype, v.sent, v.len);
    if (!v.period) promo.text = makeText(v.sent, v.len).replace(/\.$/, ""); // no trailing period
    const units = [...arts, promo];
    const promoHtml = p(promo, { cls: "teaser", linkChars: v.linkChars });
    const body = `
<div id="page">
  <article class="post-content">
    <h1>Sibling append: ${v.btype}</h1>
    ${arts.map((u) => p(u)).join("\n    ")}
  </article>
  ${promoHtml}
</div>`;
    register(
      v.name,
      `Decisive 4-paragraph <article> + ONE neutral-classed sibling <p> (${v.btype}). Isolates the (len>80 && linkDensity<0.25) append gate.`,
      "Predict: len120 with linkDensity<0.25 LEAKS; >=0.25 DROPS; short(<80)+period+0-link may LEAK (second branch); short(<80) no-period DROPS.",
      units,
      htmlDoc(v.name, body)
    );
  }
}

// ===========================================================================
// F3-short — the charThreshold=500 cliff. One article whose total body length is swept.
// Generated as several fixtures f3_short_<len>; each is a single clean article.
// ===========================================================================
const F3_LENGTHS = [120, 300, 460, 520, 800, 1500];
for (const len of F3_LENGTHS) {
  const A = unit(`f3-${len}-art`, "article", "body", `zzshort${len}`, len);
  const units = [A];
  const body = `
<div id="page">
  <article class="post-content">
    <h1>Short article length ${len}</h1>
    <p>${A.text}</p>
  </article>
</div>`;
  register(
    `f3_short_${len}`,
    `Single clean article, body ~${len} chars. Used to sweep the charThreshold=500 cliff (parse null/degraded below threshold).`,
    "Predict: parse() returns null / degrades when article text < charThreshold (default 500); cliff moves when charThreshold option changes.",
    units,
    htmlDoc(`Short ${len}`, body)
  );
}

// f3_empty — a page with only a nav + a ~30-char blurb, no real article body.
// Bounds where parse() ACTUALLY returns null (vs the sieve fallback recovering short
// clean articles). Labeled: the blurb is the only "article-ish" text.
{
  const NAV = unit("f3e-nav", "boilerplate", "nav", "zzemptynav", 40);
  const BLURB = unit("f3e-blurb", "article", "body", "zzemptyblurb", 24);
  const units = [NAV, BLURB];
  const body = `
<div id="page">
  <nav class="nav-menu">${NAV.text}</nav>
  <div class="content"><p>${BLURB.sentinel} hi.</p></div>
</div>`;
  BLURB.text = `${BLURB.sentinel} hi.`;
  register(
    "f3_empty",
    "A page with only a nav and a ~10-char blurb — essentially no article. Bounds where parse() returns null.",
    "Predict: parse() returns null (no attempt yields meaningful text) — the true null boundary, unlike short-but-clean articles which the sieve recovers.",
    units,
    htmlDoc("Empty", body)
  );
}

// ===========================================================================
// F4-sem — structural sensitivity. SAME article content, two skins:
//   f4_semantic: <main><article><h1> + descriptive ids
//   f4_neutral : <div class="x1">... no semantic tags, generic classes
// ===========================================================================
{
  const mk = (prefix) => [
    unit(`${prefix}-art-01`, "article", "body", `zz${prefix}01`, 300),
    unit(`${prefix}-art-02`, "article", "body", `zz${prefix}02`, 320),
    unit(`${prefix}-art-03`, "article", "body", `zz${prefix}03`, 280),
    unit(`${prefix}-art-04`, "article", "body", `zz${prefix}04`, 260),
  ];
  const NAVs = unit("f4s-nav", "boilerplate", "nav", "zzf4snav", 60);
  const NAVn = unit("f4n-nav", "boilerplate", "nav", "zzf4nnav", 60);
  const semU = mk("f4s");
  const neuU = mk("f4n");
  const semBody = `
<header><nav class="nav-menu">${NAVs.text}</nav></header>
<main><article class="post-content"><h1>Structural sensitivity (semantic)</h1>
  ${semU.map((u) => p(u)).join("\n  ")}
</article></main>`;
  const neuBody = `
<div class="top"><div class="menu-row">${NAVn.text}</div></div>
<div class="x1"><div class="x2">
  ${neuU.map((u) => p(u, { tag: "div" })).join("\n  ")}
</div></div>`;
  register(
    "f4_semantic",
    "Article wrapped in <main><article><h1> with descriptive classes; plus a nav.",
    "Baseline recall WITH the semantic scaffold Readability's heuristics favor.",
    [...semU, NAVs],
    htmlDoc("Semantic", semBody)
  );
  register(
    "f4_neutral",
    "IDENTICAL article text but neutralized: no <article>/<main>/<h1>, generic <div class=x> wrappers, paragraphs as <div>.",
    "Recall WITHOUT semantic scaffold — measures structural sensitivity delta vs f4_semantic.",
    [...neuU, NAVn],
    htmlDoc("Neutral", neuBody)
  );
}

// ===========================================================================
// F5-ipr — isProbablyReaderable false-negative shapes.
//   li_only    : real content in <ul><li> (issue #662 shape), no <p>
//   many_short : many <p>, each < 140 chars (below minContentLength)
//   one_long   : single <p> > 140 chars (control — should be readerable)
//   normal     : proper multi-paragraph article (control)
// ===========================================================================
{
  // li-only
  {
    const items = [1, 2, 3, 4, 5, 6].map((i) =>
      unit(`f5li-${i}`, "article", "body", `zzli0${i}`, 180)
    );
    const body = `<div id="page"><h1>List article</h1><ul>${items
      .map((u) => `<li>${u.text}</li>`)
      .join("")}</ul></div>`;
    register(
      "f5_ipr_li_only",
      "Real article content lives entirely in <ul><li> (issue #662 shape); isProbablyReaderable queries only p/pre/article.",
      "Predict: isProbablyReaderable() = false (no p/pre/article nodes) even though content is substantial; contrast with parse().",
      items,
      htmlDoc("Li only", body)
    );
  }
  // many short (<140 each)
  {
    const items = Array.from({ length: 10 }, (_, i) =>
      unit(`f5ms-${i + 1}`, "article", "body", `zzms${String(i + 1).padStart(2, "0")}`, 110)
    );
    const body = `<div id="page"><h1>Many short paragraphs</h1>${items
      .map((u) => `<p>${u.text}</p>`)
      .join("")}</div>`;
    register(
      "f5_ipr_many_short",
      "Ten <p> paragraphs, each < minContentLength (140 chars). Each alone scores 0 in the sqrt(len-140) formula.",
      "Predict: isProbablyReaderable() = false (each paragraph below minContentLength scores nothing) though total content is large; contrast with parse().",
      items,
      htmlDoc("Many short", body)
    );
  }
  // one long (>140) control
  {
    const u = unit("f5ol", "article", "body", "zzonelong", 400);
    const body = `<div id="page"><h1>One long paragraph</h1><p>${u.text}</p></div>`;
    register(
      "f5_ipr_one_long",
      "Single <p> well over minContentLength — control that SHOULD be readerable.",
      "Control: isProbablyReaderable() = true expected.",
      [u],
      htmlDoc("One long", body)
    );
  }
  // normal control
  {
    const items = [1, 2, 3].map((i) =>
      unit(`f5n-${i}`, "article", "body", `zznorm0${i}`, 300)
    );
    const body = `<div id="page"><article><h1>Normal</h1>${items
      .map((u) => `<p>${u.text}</p>`)
      .join("")}</article></div>`;
    register(
      "f5_ipr_normal",
      "Ordinary multi-paragraph article — control (readerable + parse succeeds).",
      "Control: isProbablyReaderable() = true AND parse() succeeds.",
      items,
      htmlDoc("Normal", body)
    );
  }
}

// ===========================================================================
// F6-nonprose — recall on non-prose legitimate article content.
//   prose paras (to ensure article is selected) + <table> + <pre> code + sub-25-char
//   one-line <p> + figure <figcaption>. All labeled ARTICLE.
// ===========================================================================
{
  const P1 = unit("f6-prose-01", "article", "prose", "zznp_prose01", 320);
  const P2 = unit("f6-prose-02", "article", "prose", "zznp_prose02", 300);
  const TCELL1 = unit("f6-table-01", "article", "table-cell", "zznp_tbl01", 20);
  const TCELL2 = unit("f6-table-02", "article", "table-cell", "zznp_tbl02", 20);
  const CODE = unit("f6-code", "article", "pre-code", "zznp_code01", 120);
  const SHORT1 = unit("f6-short-01", "article", "short-line", "zznp_short01", 8);
  const SHORT2 = unit("f6-short-02", "article", "short-line", "zznp_short02", 8);
  const CAP1 = unit("f6-cap-01", "article", "figcaption", "zznp_cap01", 18);
  const units = [P1, P2, TCELL1, TCELL2, CODE, SHORT1, SHORT2, CAP1];
  const body = `
<div id="page"><article class="post-content"><h1>Non-prose content</h1>
  ${p(P1)}
  <table><thead><tr><th>Metric</th><th>Value</th></tr></thead>
  <tbody><tr><td>${TCELL1.text}</td><td>${TCELL2.text}</td></tr></tbody></table>
  <pre><code>${CODE.text}</code></pre>
  <p>${SHORT1.sentinel} ok.</p>
  <p>${SHORT2.sentinel} ok.</p>
  <figure><img src="/i.png" alt="x"><figcaption>${CAP1.text}</figcaption></figure>
  ${p(P2)}
</article></div>`;
  // For sub-25-char one-line paras the "text" is just the sentinel + "ok."; recompute
  SHORT1.text = `${SHORT1.sentinel} ok.`;
  SHORT2.text = `${SHORT2.sentinel} ok.`;
  register(
    "f6_nonprose",
    "Article whose legitimate content includes a data <table>, a <pre> code block, sub-25-char one-line <p>, and a <figcaption> alongside prose.",
    "Predict: prose recovered; sub-25-char lines (uncounted by scoring) + some table/caption text at risk of being dropped.",
    units,
    htmlDoc("Non-prose", body)
  );
}

// ---- write ground truth ----------------------------------------------------
const groundTruth = {};
for (const [name, f] of Object.entries(fixtures)) {
  groundTruth[name] = {
    description: f.description,
    intent: f.intent,
    units: f.units.map(({ id, label, btype, sentinel, text }) => ({
      id,
      label,
      btype,
      sentinel,
      text,
    })),
  };
}
writeFileSync(
  join(FIX_DIR, "ground_truth.json"),
  JSON.stringify(groundTruth, null, 2) + "\n",
  "utf-8"
);

const nUnits = Object.values(groundTruth).reduce((a, g) => a + g.units.length, 0);
console.log(
  `wrote ${Object.keys(fixtures).length} fixtures, ${nUnits} labeled units -> ${FIX_DIR}`
);
