#!/usr/bin/env node
// Reproducible evaluation material for the Playwright single-tool pack.
// Playwright is a real-browser automation library: JS content renders natively.
// Its cost is browser weight/speed and the lack of a built-in crawl queue.
// Research harness, not final blog copy.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = path.resolve(__dirname, '..');
const RAW_DIR = path.join(PROJECT_DIR, 'artifacts', 'raw');
const LOGS_DIR = path.join(PROJECT_DIR, 'artifacts', 'logs');
const SHOTS_DIR = path.join(PROJECT_DIR, 'artifacts', 'screenshots');

import { startFixtureServer, PRODUCTS, ARTICLE, DYNAMIC_PRODUCTS } from './fixture-server.mjs';

for (const dir of [RAW_DIR, LOGS_DIR, SHOTS_DIR]) fs.mkdirSync(dir, { recursive: true });
const writeJson = (f, p) => fs.writeFileSync(path.join(RAW_DIR, f), JSON.stringify(p, null, 2) + '\n', 'utf-8');
function writeCsv(file, rows) {
  if (!rows.length) return fs.writeFileSync(path.join(RAW_DIR, file), '', 'utf-8');
  const fields = [...new Set(rows.flatMap((r) => Object.keys(r)))].sort();
  const esc = (v) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  fs.writeFileSync(path.join(RAW_DIR, file), [fields.join(','), ...rows.map((r) => fields.map((f) => esc(r[f])).join(','))].join('\n') + '\n', 'utf-8');
}
const recall = (rows, names) => { const f = new Set(rows.map((r) => r.name)); const missing = names.filter((n) => !f.has(n)); return { found_count: names.length - missing.length, expected_count: names.length, recall: Number(((names.length - missing.length) / names.length).toFixed(3)), missing }; };
const now = () => new Date().toISOString();

async function main() {
  const server = await startFixtureServer();
  const base = server.baseUrl;
  writeJson('local_fixture_ground_truth.json', { products: PRODUCTS, article: ARTICLE, dynamic_products: DYNAMIC_PRODUCTS });

  const summary = {
    run_started_at: now(), tool: 'playwright',
    playwright_version: require('playwright/package.json').version,
    node: process.version, platform: `${os.type()} ${os.release()} ${os.arch()}`,
    fixture_base_url: base, tests: {},
  };

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext();
  try {
    // 1) Static catalog + pagination (manual next-link follow).
    {
      const rows = []; const t0 = Date.now();
      const page = await ctx.newPage();
      let url = `${base}/static/catalog?page=1`;
      while (url) {
        await page.goto(url, { waitUntil: 'domcontentloaded' });
        const cards = await page.$$eval('.product-card', (els) => els.map((el) => ({
          id: Number(el.getAttribute('data-product-id')),
          name: el.querySelector('.product-name')?.textContent?.trim(),
          category: el.querySelector('.category')?.textContent?.trim(),
          price: Number(el.querySelector('.price')?.textContent?.replace('$', '').trim()),
          rating: Number(el.querySelector('.rating')?.textContent?.replace(' stars', '').trim()),
        })));
        rows.push(...cards);
        const next = await page.$('.next-page');
        url = next ? new URL(await next.getAttribute('href'), base).href : null;
      }
      await page.close();
      rows.sort((a, b) => a.id - b.id);
      writeJson('local_static_catalog.json', rows); writeCsv('local_static_catalog.csv', rows);
      summary.tests.local_static_catalog = { url: `${base}/static/catalog?page=1`, success: true, items: rows.length, pagination_followed: rows.length > 6, product_recall: recall(rows, PRODUCTS.map((p) => p.name)), elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 2) Article extraction with boilerplate separation.
    {
      const t0 = Date.now(); const page = await ctx.newPage();
      await page.goto(`${base}/article/1`, { waitUntil: 'domcontentloaded' });
      const article = await page.evaluate(() => ({
        title: document.querySelector('article h1')?.textContent?.trim(),
        author: document.querySelector('.author')?.textContent?.trim(),
        date: document.querySelector('time')?.textContent?.trim(),
        body_paragraphs: [...document.querySelectorAll('article > p')].map((p) => p.textContent.trim()).filter((t) => t && !t.startsWith('By ')),
        nav_text: document.querySelector('nav')?.textContent?.trim(),
        footer_text: document.querySelector('footer')?.textContent?.trim(),
      }));
      await page.close();
      writeJson('local_article.json', article);
      summary.tests.local_article = { url: `${base}/article/1`, success: true, title_found: article.title === ARTICLE.title, paragraphs_found: ARTICLE.body_paragraphs.filter((p) => article.body_paragraphs?.includes(p)).length, paragraphs_expected: ARTICLE.body_paragraphs.length, boilerplate_available_but_separated: Boolean(article.nav_text || article.footer_text), elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 3) Dynamic JS page renders natively -> expect 8 + screenshot.
    {
      const t0 = Date.now(); const page = await ctx.newPage();
      await page.goto(`${base}/dynamic/catalog`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#dynamic-products article.product-card', { timeout: 15000 });
      const statusText = await page.textContent('#status');
      const rows = await page.$$eval('#dynamic-products article.product-card', (els) => els.map((el) => ({ id: Number(el.getAttribute('data-product-id')), name: el.querySelector('.product-name')?.textContent?.trim(), category: el.querySelector('.category')?.textContent?.trim(), price: Number(el.querySelector('.price')?.textContent?.replace('$', '').trim()), rating: Number(el.querySelector('.rating')?.textContent?.replace(' stars', '').trim()) })));
      await page.screenshot({ path: path.join(SHOTS_DIR, 'local_dynamic_playwright.png'), fullPage: true });
      await page.close();
      rows.sort((a, b) => a.id - b.id);
      writeJson('local_dynamic_rendered.json', { status_text: statusText, products: rows });
      summary.tests.local_dynamic_rendered = { url: `${base}/dynamic/catalog`, success: rows.length > 0, items: rows.length, status_text: statusText, product_recall: recall(rows, DYNAMIC_PRODUCTS.map((p) => p.name)), screenshot: 'tools/playwright/artifacts/screenshots/local_dynamic_playwright.png', elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 4) Dynamic JSON API via page.request (no DOM).
    {
      const t0 = Date.now();
      const res = await ctx.request.get(`${base}/api/dynamic-products`);
      const rows = await res.json();
      writeJson('local_dynamic_api.json', rows); writeCsv('local_dynamic_api.csv', rows);
      summary.tests.local_dynamic_api = { url: `${base}/api/dynamic-products`, success: true, items: rows.length, product_recall: recall(rows, DYNAMIC_PRODUCTS.map((p) => p.name)), note: 'page.request reaches the API without rendering a DOM.', elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 5) HTTP 500 handling.
    {
      const t0 = Date.now(); const page = await ctx.newPage();
      const resp = await page.goto(`${base}/failure/500`, { waitUntil: 'domcontentloaded' });
      const status = resp.status();
      await page.close();
      writeJson('local_failure_500.json', { status, handled: true });
      summary.tests.local_failure_500 = { url: `${base}/failure/500`, success: true, confirmed_status: status, note: 'Playwright returns the response object; status is inspectable, navigation does not throw on 500.', elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 6) Manual BFS crawl graph (no built-in queue).
    {
      const t0 = Date.now();
      const seen = new Map(); const queue = [{ url: `${base}/`, depth: 0 }];
      const page = await ctx.newPage();
      while (queue.length && seen.size < 30) {
        const { url, depth } = queue.shift();
        const key = url.split('#')[0];
        if (seen.has(key)) continue;
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded' }).catch(() => null);
        if (!resp) continue;
        seen.set(key, { url: key, depth, title: await page.title() });
        if (depth < 2) {
          const hrefs = await page.$$eval('a[href]', (els) => els.map((a) => a.getAttribute('href')));
          for (const h of hrefs) {
            const abs = new URL(h, base).href.split('#')[0];
            if (abs.startsWith(base) && !seen.has(abs)) queue.push({ url: abs, depth: depth + 1 });
          }
        }
      }
      await page.close();
      const pages = [...seen.values()].sort((a, b) => a.depth - b.depth || a.url.localeCompare(b.url));
      writeJson('local_crawl_graph.json', pages);
      const depthCounts = {}; for (const p of pages) depthCounts[p.depth] = (depthCounts[p.depth] || 0) + 1;
      summary.tests.local_crawl_graph = { url: base, success: true, pages_seen: pages.length, depth_counts: depthCounts, note: 'Playwright has no built-in crawl queue; BFS was implemented by hand.', elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
    }

    // 7) Public: Books to Scrape (rendered).
    {
      const t0 = Date.now();
      try {
        const page = await ctx.newPage();
        await page.goto('https://books.toscrape.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
        const rows = await page.$$eval('.product_pod', (els) => els.map((el) => ({ title: el.querySelector('h3 a')?.getAttribute('title'), price: el.querySelector('.price_color')?.textContent?.trim(), availability: el.querySelector('.availability')?.textContent?.trim() })));
        await page.close();
        writeJson('public_books_to_scrape.json', rows); writeCsv('public_books_to_scrape.csv', rows);
        summary.tests.public_books_to_scrape = { url: 'https://books.toscrape.com/', tested_on: now(), success: rows.length > 0, items: rows.length, elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
      } catch (e) { summary.tests.public_books_to_scrape = { url: 'https://books.toscrape.com/', tested_on: now(), success: false, error: String(e?.message || e) }; }
    }

    // 8) Public: Quotes JS (rendered).
    {
      const t0 = Date.now();
      try {
        const page = await ctx.newPage();
        await page.goto('https://quotes.toscrape.com/js/', { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForSelector('.quote', { timeout: 20000 });
        const rows = await page.$$eval('.quote', (els) => els.map((el) => ({ text: el.querySelector('.text')?.textContent?.trim(), author: el.querySelector('.author')?.textContent?.trim() })));
        await page.close();
        writeJson('public_quotes_js_rendered.json', rows);
        summary.tests.public_quotes_js_rendered = { url: 'https://quotes.toscrape.com/js/', tested_on: now(), success: rows.length > 0, items: rows.length, note: 'JS-rendered quotes; Playwright renders them natively.', elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)) };
      } catch (e) { summary.tests.public_quotes_js_rendered = { url: 'https://quotes.toscrape.com/js/', tested_on: now(), success: false, error: String(e?.message || e) }; }
    }

    summary.run_completed_at = now();
    writeJson('playwright-test-summary.json', summary);
    process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
    return 0;
  } finally {
    await ctx.close(); await browser.close(); await server.close();
  }
}
main().then((c) => process.exit(c)).catch((e) => { console.error('FATAL', e); process.exit(1); });
