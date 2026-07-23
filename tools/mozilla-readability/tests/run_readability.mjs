#!/usr/bin/env node
// run_readability.mjs — the Readability extraction arm. Reads every fixture + the
// ground truth, runs Readability.parse() and isProbablyReaderable() (with the option
// sweeps the hypotheses need), and dumps the RAW extracted text + booleans + timings.
// NO precision/recall is computed here (anti-hardcoding split — metrics.py owns that).
//
// Because Readability.parse() mutates the DOM, a FRESH JSDOM is built per parse call.
// Determinism: the default parse is run 3x per fixture and the extracted text compared.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import { Readability, isProbablyReaderable } from "@mozilla/readability";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const READABILITY_VERSION = require("@mozilla/readability/package.json").version;
const JSDOM_VERSION = require("jsdom/package.json").version;

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = dirname(HERE);
const FIX_DIR = join(HERE, "fixtures");
const RAW_DIR = join(PROJECT, "artifacts", "raw");
mkdirSync(RAW_DIR, { recursive: true });

const FIXTURE_URL = "http://fixture.local/article"; // stable base for URL resolution

// ---- redaction: $HOME + $TMPDIR/private tmp paths -> ~ / <TMP> ----
const HOME = process.env.HOME || "";
const TMP = (process.env.TMPDIR || "").replace(/\/$/, "");
function redact(obj) {
  if (typeof obj === "string") {
    let s = obj;
    if (HOME) s = s.split(HOME).join("~");
    if (TMP) s = s.split(TMP).join("<TMP>");
    s = s.replace(/\/private\/var\/folders\/[^\s"']*/g, "<TMP>");
    s = s.replace(/\/var\/folders\/[^\s"']*/g, "<TMP>");
    return s;
  }
  if (Array.isArray(obj)) return obj.map(redact);
  if (obj && typeof obj === "object") {
    const o = {};
    for (const [k, v] of Object.entries(obj)) o[k] = redact(v);
    return o;
  }
  return obj;
}

function loadDoc(html) {
  return new JSDOM(html, { url: FIXTURE_URL }).window.document;
}

function parseOnce(html, options = {}) {
  const doc = loadDoc(html);
  const t0 = process.hrtime.bigint();
  const article = new Readability(doc, options).parse();
  const t1 = process.hrtime.bigint();
  const elapsed_ms = Number(t1 - t0) / 1e6;
  if (!article) {
    return { parse_ok: false, elapsed_ms, extracted_text: "", extracted_html_len: 0 };
  }
  return {
    parse_ok: true,
    elapsed_ms,
    title: article.title ?? null,
    byline: article.byline ?? null,
    excerpt: article.excerpt ?? null,
    length: article.length ?? null,
    siteName: article.siteName ?? null,
    // textContent is what downstream metrics measure recall/leak against
    extracted_text: article.textContent ?? "",
    extracted_html_len: (article.content ?? "").length,
  };
}

const fixtures = JSON.parse(readFileSync(join(FIX_DIR, "ground_truth.json"), "utf-8"));

const out = {
  run_started_at: new Date().toISOString(),
  tool: "@mozilla/readability",
  readability_version: READABILITY_VERSION,
  jsdom_version: JSDOM_VERSION,
  node_version: process.version,
  fixture_url_base: FIXTURE_URL,
  fixtures: {},
};

for (const name of Object.keys(fixtures)) {
  const html = readFileSync(join(FIX_DIR, `${name}.html`), "utf-8");
  const doc = loadDoc(html);
  const ipr_default = isProbablyReaderable(doc);

  // default parse
  const def = parseOnce(html);

  // determinism: 3 reps, compare extracted text
  const reps = [];
  for (let i = 0; i < 3; i++) reps.push(parseOnce(html).extracted_text);
  const determinism = {
    reps_extracted_len: reps.map((t) => t.length),
    all_identical: reps.every((t) => t === reps[0]),
  };

  const rec = {
    is_probably_readerable_default: ipr_default,
    default: def,
    determinism,
  };

  // H3: charThreshold sweep for the F3 short fixtures
  if (name.startsWith("f3_short_")) {
    rec.charThreshold_sweep = [200, 500, 1000].map((ct) => {
      const r = parseOnce(html, { charThreshold: ct });
      return {
        charThreshold: ct,
        parse_ok: r.parse_ok,
        extracted_len: r.extracted_text.length,
        article_length: r.length ?? 0,
      };
    });
  }

  // H2: measure the ACTUAL link density + innerText length of the promo sibling, the
  // way Readability computes it (link text / total text), so the boundary is exact.
  if (name.startsWith("f2_sib")) {
    const teaser = doc.querySelector("p.teaser");
    if (teaser) {
      const totalText = (teaser.textContent || "").trim();
      let linkLen = 0;
      for (const a of teaser.querySelectorAll("a")) {
        const href = a.getAttribute("href") || "";
        const coef = /^#/.test(href) ? 0.3 : 1;
        linkLen += (a.textContent || "").length * coef;
      }
      rec.promo_geometry = {
        inner_text_len: totalText.length,
        link_text_len: linkLen,
        link_density: totalText.length ? linkLen / totalText.length : 0,
        over_80_chars: totalText.length > 80,
        leaked: (def.extracted_text || "").includes(
          fixtures[name].units.find((u) => u.label === "boilerplate").sentinel
        ),
      };
    }
  }

  // H5: minScore sweep for the F5 isProbablyReaderable fixtures
  if (name.startsWith("f5_ipr_")) {
    rec.minScore_sweep = [1, 5, 10, 20, 40, 80].map((ms) => ({
      minScore: ms,
      is_probably_readerable: isProbablyReaderable(loadDoc(html), { minScore: ms }),
    }));
    // also sweep minContentLength at default minScore
    rec.minContentLength_sweep = [40, 100, 140, 200].map((mcl) => ({
      minContentLength: mcl,
      is_probably_readerable: isProbablyReaderable(loadDoc(html), {
        minContentLength: mcl,
      }),
    }));
    rec.parse_ok = def.parse_ok; // predictor vs actual parse success
  }

  out.fixtures[name] = rec;
}

out.run_completed_at = new Date().toISOString();
const outPath = join(RAW_DIR, "readability_raw.json");
writeFileSync(outPath, JSON.stringify(redact(out), null, 2) + "\n", "utf-8");
console.log(
  `readability arm done: ${Object.keys(out.fixtures).length} fixtures -> ${redact(outPath)}`
);
