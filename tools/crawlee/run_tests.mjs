#!/usr/bin/env node
// Reproducible evaluation material for the Crawlee single-tool pack.
// Demonstrates Crawlee's core differentiator: same framework, swap
// CheerioCrawler (HTTP, no JS) <-> PlaywrightCrawler (real browser).
// This is a research harness, not final blog copy.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = __dirname;
const RAW_DIR = path.join(PROJECT_DIR, 'results');
const LOGS_DIR = path.join(PROJECT_DIR, 'results');
const SHOTS_DIR = path.join(PROJECT_DIR, 'results', 'screenshots');

// Keep Crawlee storage out of the pack; scratch only.
const STORAGE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'crawlee-storage-'));
process.env.CRAWLEE_STORAGE_DIR = STORAGE_DIR;
process.env.CRAWLEE_PURGE_ON_START = '1';

const { CheerioCrawler, PlaywrightCrawler, Configuration, log, LogLevel } = await import('crawlee');
log.setLevel(LogLevel.WARNING);

import { startFixtureServer, PRODUCTS, ARTICLE, DYNAMIC_PRODUCTS } from './fixture-server.mjs';

for (const dir of [RAW_DIR, LOGS_DIR, SHOTS_DIR]) fs.mkdirSync(dir, { recursive: true });

function writeJson(file, payload) {
  fs.writeFileSync(path.join(RAW_DIR, file), JSON.stringify(payload, null, 2) + '\n', 'utf-8');
}

function writeCsv(file, rows) {
  if (!rows.length) {
    fs.writeFileSync(path.join(RAW_DIR, file), '', 'utf-8');
    return;
  }
  const fields = [...new Set(rows.flatMap((r) => Object.keys(r)))].sort();
  const escape = (v) => {
    const s = v === undefined || v === null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [fields.join(',')];
  for (const row of rows) lines.push(fields.map((f) => escape(row[f])).join(','));
  fs.writeFileSync(path.join(RAW_DIR, file), lines.join('\n') + '\n', 'utf-8');
}

function recall(rows, expectedNames) {
  const found = new Set(rows.map((r) => r.name));
  const missing = expectedNames.filter((n) => !found.has(n));
  return {
    found_count: expectedNames.length - missing.length,
    expected_count: expectedNames.length,
    recall: Number(((expectedNames.length - missing.length) / expectedNames.length).toFixed(3)),
    missing,
  };
}

// Fresh Configuration per crawler so runs stay isolated.
function cfg() {
  const c = new Configuration({ persistStorage: false, storageClientOptions: { localDataDirectory: STORAGE_DIR } });
  return c;
}

const now = () => new Date().toISOString();

async function main() {
  const server = await startFixtureServer();
  const base = server.baseUrl;

  const groundTruth = { products: PRODUCTS, article: ARTICLE, dynamic_products: DYNAMIC_PRODUCTS };
  writeJson('local_fixture_ground_truth.json', groundTruth);

  const crawleeVersion = require('crawlee/package.json').version;
  let playwrightVersion = null;
  try { playwrightVersion = require('playwright/package.json').version; } catch {}

  const summary = {
    run_started_at: now(),
    tool: 'crawlee',
    crawlee_version: crawleeVersion,
    playwright_version: playwrightVersion,
    node: process.version,
    platform: `${os.type()} ${os.release()} ${os.arch()}`,
    fixture_base_url: base,
    tests: {},
  };

  try {
    // 1) Static catalog with pagination (CheerioCrawler) -> expect 12.
    {
      const rows = [];
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        maxConcurrency: 2,
        async requestHandler({ $, enqueueLinks }) {
          $('.product-card').each((_, el) => {
            const card = $(el);
            rows.push({
              id: Number(card.attr('data-product-id')),
              name: card.find('.product-name').text().trim(),
              category: card.find('.category').text().trim(),
              price: Number(card.find('.price').text().replace('$', '').trim()),
              rating: Number(card.find('.rating').text().replace(' stars', '').trim()),
            });
          });
          await enqueueLinks({ selector: '.next-page' });
        },
      }, cfg());
      await crawler.run([`${base}/static/catalog?page=1`]);
      rows.sort((a, b) => a.id - b.id);
      writeJson('local_static_catalog.json', rows);
      writeCsv('local_static_catalog.csv', rows);
      summary.tests.local_static_catalog = {
        crawler: 'CheerioCrawler',
        url: `${base}/static/catalog?page=1`,
        success: true,
        items: rows.length,
        pagination_followed: rows.length > 6,
        product_recall: recall(rows, PRODUCTS.map((p) => p.name)),
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
        raw_output: 'results/local_static_catalog.json',
        csv_output: 'results/local_static_catalog.csv',
      };
    }

    // 2) Article extraction with boilerplate separation (CheerioCrawler).
    {
      let article = {};
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        async requestHandler({ $ }) {
          article = {
            title: $('article h1').first().text().trim(),
            author: $('.author').first().text().trim(),
            date: $('time').first().text().trim(),
            body_paragraphs: $('article > p').map((_, el) => $(el).text().trim()).get().filter((t) => t && !t.startsWith('By ')),
            nav_text: $('nav').first().text().trim(),
            aside_text: $('aside').first().text().trim(),
            footer_text: $('footer').first().text().trim(),
          };
        },
      }, cfg());
      await crawler.run([`${base}/article/1`]);
      writeJson('local_article.json', article);
      const paragraphsFound = ARTICLE.body_paragraphs.filter((p) => article.body_paragraphs?.includes(p)).length;
      summary.tests.local_article = {
        crawler: 'CheerioCrawler',
        url: `${base}/article/1`,
        success: true,
        title_found: article.title === ARTICLE.title,
        paragraphs_found: paragraphsFound,
        paragraphs_expected: ARTICLE.body_paragraphs.length,
        boilerplate_available_but_separated: Boolean(article.nav_text || article.footer_text),
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
        raw_output: 'results/local_article.json',
      };
    }

    // 3) Dynamic page WITHOUT JS (CheerioCrawler) -> expect 0 cards (limitation).
    {
      let cardsFound = null;
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        async requestHandler({ $ }) { cardsFound = $('.product-card').length; },
      }, cfg());
      await crawler.run([`${base}/dynamic/catalog`]);
      writeJson('local_dynamic_page_no_js.json', { crawler: 'CheerioCrawler', product_cards_found: cardsFound });
      summary.tests.local_dynamic_page_no_js = {
        crawler: 'CheerioCrawler',
        url: `${base}/dynamic/catalog`,
        success: true,
        expected_limitation_observed: cardsFound === 0,
        product_cards_found: cardsFound,
        note: 'CheerioCrawler does not execute JavaScript; empty result is expected and useful evidence.',
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
      };
    }

    // 4) Dynamic API endpoint (CheerioCrawler + additionalMimeTypes) -> expect 8.
    {
      let rows = [];
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        additionalMimeTypes: ['application/json'],
        async requestHandler({ body, json }) {
          const data = json ?? JSON.parse(body.toString());
          rows = data;
        },
      }, cfg());
      await crawler.run([`${base}/api/dynamic-products`]);
      writeJson('local_dynamic_api.json', rows);
      writeCsv('local_dynamic_api.csv', rows);
      summary.tests.local_dynamic_api = {
        crawler: 'CheerioCrawler',
        url: `${base}/api/dynamic-products`,
        success: true,
        items: rows.length,
        product_recall: recall(rows, DYNAMIC_PRODUCTS.map((p) => p.name)),
        note: 'Reproducing the underlying request avoids a browser for this endpoint.',
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
      };
    }

    // 5) HTTP 500 error handling (CheerioCrawler, 0 retries).
    {
      const errors = [];
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        maxRequestRetries: 0,
        async requestHandler() { /* not expected to reach */ },
        async failedRequestHandler({ request }, error) {
          errors.push({ url: request.url, error_message: String(error?.message || error) });
        },
      }, cfg());
      await crawler.run([`${base}/failure/500`]);
      // Confirm the ground-truth status independently.
      let confirmedStatus = null;
      try { confirmedStatus = (await fetch(`${base}/failure/500`)).status; } catch {}
      writeJson('local_failure_500.json', { crawler: 'CheerioCrawler', confirmed_status: confirmedStatus, crawlee_failed_requests: errors });
      summary.tests.local_failure_500 = {
        crawler: 'CheerioCrawler',
        url: `${base}/failure/500`,
        success: true,
        confirmed_status: confirmedStatus,
        routed_to_failed_handler: errors.length === 1,
        note: 'Crawlee surfaces the 500 via failedRequestHandler after retries are exhausted.',
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
      };
    }

    // 6) Internal-link crawl graph with depth tracking (CheerioCrawler).
    {
      const pages = [];
      const t0 = Date.now();
      const crawler = new CheerioCrawler({
        maxRequestsPerCrawl: 30,
        maxConcurrency: 2,
        async requestHandler({ request, $, enqueueLinks }) {
          const depth = request.userData.depth ?? 0;
          pages.push({ url: request.url, depth, title: $('title').text().trim() });
          if (depth < 2) {
            await enqueueLinks({
              strategy: 'same-hostname',
              transformRequestFunction(req) { req.userData = { depth: depth + 1 }; return req; },
            });
          }
        },
      }, cfg());
      await crawler.run([`${base}/`]);
      pages.sort((a, b) => a.depth - b.depth || a.url.localeCompare(b.url));
      writeJson('local_crawl_graph.json', pages);
      const depthCounts = {};
      for (const p of pages) depthCounts[p.depth] = (depthCounts[p.depth] || 0) + 1;
      summary.tests.local_crawl_graph = {
        crawler: 'CheerioCrawler',
        url: base,
        success: true,
        pages_seen: pages.length,
        depth_counts: depthCounts,
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
      };
    }

    // 7) Dynamic page WITH JS (PlaywrightCrawler) -> expect 8 + screenshot.
    {
      const rows = [];
      let statusText = null;
      const t0 = Date.now();
      const shotPath = path.join(SHOTS_DIR, 'local_dynamic_playwright.png');
      const crawler = new PlaywrightCrawler({
        maxRequestsPerCrawl: 1,
        headless: true,
        async requestHandler({ page }) {
          await page.waitForSelector('#dynamic-products article.product-card', { timeout: 15000 });
          statusText = await page.textContent('#status');
          const cards = await page.$$eval('#dynamic-products article.product-card', (els) => els.map((el) => ({
            id: Number(el.getAttribute('data-product-id')),
            name: el.querySelector('.product-name')?.textContent?.trim(),
            category: el.querySelector('.category')?.textContent?.trim(),
            price: Number(el.querySelector('.price')?.textContent?.replace('$', '').trim()),
            rating: Number(el.querySelector('.rating')?.textContent?.replace(' stars', '').trim()),
          })));
          rows.push(...cards);
          await page.screenshot({ path: shotPath, fullPage: true });
        },
      }, cfg());
      await crawler.run([`${base}/dynamic/catalog`]);
      rows.sort((a, b) => a.id - b.id);
      writeJson('local_dynamic_playwright.json', { status_text: statusText, products: rows });
      summary.tests.local_dynamic_playwright = {
        crawler: 'PlaywrightCrawler',
        url: `${base}/dynamic/catalog`,
        success: rows.length > 0,
        items: rows.length,
        status_text: statusText,
        product_recall: recall(rows, DYNAMIC_PRODUCTS.map((p) => p.name)),
        screenshot: 'results/screenshots/local_dynamic_playwright.png',
        note: 'Same fixture as the CheerioCrawler miss; the browser crawler renders JS and recovers all products.',
        elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
      };
    }

    // 8) Public: Books to Scrape homepage (CheerioCrawler) -> expect 20.
    {
      const rows = [];
      const t0 = Date.now();
      try {
        const crawler = new CheerioCrawler({
          maxRequestsPerCrawl: 1,
          requestHandlerTimeoutSecs: 45,
          async requestHandler({ $ }) {
            $('.product_pod').each((_, el) => {
              const pod = $(el);
              rows.push({
                title: pod.find('h3 a').attr('title'),
                price: pod.find('.price_color').text().trim(),
                availability: pod.find('.availability').text().trim(),
              });
            });
          },
        }, cfg());
        await crawler.run(['https://books.toscrape.com/']);
        writeJson('public_books_to_scrape.json', rows);
        writeCsv('public_books_to_scrape.csv', rows);
        summary.tests.public_books_to_scrape = {
          crawler: 'CheerioCrawler', url: 'https://books.toscrape.com/', tested_on: now(),
          success: rows.length > 0, items: rows.length,
          raw_output: 'results/public_books_to_scrape.json',
          elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
        };
      } catch (error) {
        summary.tests.public_books_to_scrape = { crawler: 'CheerioCrawler', url: 'https://books.toscrape.com/', tested_on: now(), success: false, error: String(error?.message || error) };
      }
    }

    // 9) Public: Quotes JS via CheerioCrawler (no render) -> expect 0 (limitation).
    {
      let quoteNodes = null;
      const t0 = Date.now();
      try {
        const crawler = new CheerioCrawler({
          maxRequestsPerCrawl: 1,
          requestHandlerTimeoutSecs: 45,
          async requestHandler({ $ }) { quoteNodes = $('.quote').length; },
        }, cfg());
        await crawler.run(['https://quotes.toscrape.com/js/']);
        writeJson('public_quotes_js_no_render.json', { crawler: 'CheerioCrawler', quote_nodes_found: quoteNodes });
        summary.tests.public_quotes_js_no_render = {
          crawler: 'CheerioCrawler', url: 'https://quotes.toscrape.com/js/', tested_on: now(),
          success: true, expected_limitation_observed: quoteNodes === 0, quote_nodes_found: quoteNodes,
          elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
        };
      } catch (error) {
        summary.tests.public_quotes_js_no_render = { crawler: 'CheerioCrawler', url: 'https://quotes.toscrape.com/js/', tested_on: now(), success: false, error: String(error?.message || error) };
      }
    }

    // 10) Public: Quotes JS via PlaywrightCrawler (render) -> expect quotes.
    {
      const rows = [];
      const t0 = Date.now();
      try {
        const crawler = new PlaywrightCrawler({
          maxRequestsPerCrawl: 1,
          headless: true,
          requestHandlerTimeoutSecs: 60,
          async requestHandler({ page }) {
            await page.waitForSelector('.quote', { timeout: 20000 });
            const quotes = await page.$$eval('.quote', (els) => els.map((el) => ({
              text: el.querySelector('.text')?.textContent?.trim(),
              author: el.querySelector('.author')?.textContent?.trim(),
            })));
            rows.push(...quotes);
          },
        }, cfg());
        await crawler.run(['https://quotes.toscrape.com/js/']);
        writeJson('public_quotes_js_playwright.json', rows);
        summary.tests.public_quotes_js_playwright = {
          crawler: 'PlaywrightCrawler', url: 'https://quotes.toscrape.com/js/', tested_on: now(),
          success: rows.length > 0, items: rows.length,
          raw_output: 'results/public_quotes_js_playwright.json',
          note: 'Same URL where CheerioCrawler saw 0 quotes; the browser crawler renders them.',
          elapsed_seconds: Number(((Date.now() - t0) / 1000).toFixed(3)),
        };
      } catch (error) {
        summary.tests.public_quotes_js_playwright = { crawler: 'PlaywrightCrawler', url: 'https://quotes.toscrape.com/js/', tested_on: now(), success: false, error: String(error?.message || error) };
      }
    }

    summary.run_completed_at = now();
    writeJson('crawlee-test-summary.json', summary);
    process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
    return 0;
  } finally {
    await server.close();
    try { fs.rmSync(STORAGE_DIR, { recursive: true, force: true }); } catch {}
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error('FATAL', error);
  process.exit(1);
});
