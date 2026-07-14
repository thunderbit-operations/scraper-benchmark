#!/usr/bin/env node
// -*- coding: utf-8 -*-
/**
 * Crawlee engine-parity API-surface probe —— 中立、非计时、免 key、不下载浏览器。
 *
 * 目的（Batch B 之后的补测）：
 *   Batch B 记录了 CheerioCrawler ↔ PlaywrightCrawler 的 unified-API parity。
 *   本探针补齐第三种引擎 PuppeteerCrawler，程序化列出
 *   CheerioCrawler / PlaywrightCrawler / PuppeteerCrawler 三者
 *   共有 vs 各自独有的原型方法、原型继承链、以及 handler-context 表面差异。
 *
 * 原则（品牌 / v3 口径，最高优先级）：
 *   - 零计时：不测吞吐 / 延迟 / 启动时间，只比 API 表面（存在性 + 继承结构）。
 *   - 不启动浏览器、不下载 chromium、不发起任何网络导航。
 *     只从已装的 `crawlee`（3.17.0）import 类对象并做静态自省。
 *   - 每个字段都由本次运行计算得出（反硬编码）。
 *   - 只记录「某方法/属性是否存在」这一存在性事实，不做任何能力评判。
 *
 * 说明：`puppeteer` peer dep 是 @crawlee/puppeteer 的 optional peer，本环境未安装。
 *   PuppeteerCrawler 类本身仍从顶层 `crawlee` 正常 export 并可自省——
 *   这正好证明「类结构 / API 表面」不依赖浏览器运行时。
 *   要真正 .run() 才需要 `npm i puppeteer` + 浏览器下载（同 Playwright 的 friction，见 RM）。
 *
 * 输出：results/crawlee_puppeteer_parity_api_surface.json
 * 运行：node tests/puppeteer_parity_api_surface.mjs
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, 'results', 'crawlee_puppeteer_parity_api_surface.json');
const require = createRequire(import.meta.url);

// 已装 crawlee 版本（从 node_modules 的 package.json 读，不硬编码）
function installedCrawleeVersion() {
  try {
    const p = require.resolve('crawlee/package.json');
    return JSON.parse(readFileSync(p, 'utf8')).version;
  } catch (e) {
    return `(err: ${e.message})`;
  }
}

// 原型继承链的类名序列（до BasicCrawler / Object）
function protoChain(cls) {
  const chain = [];
  let c = cls;
  while (c && c.name) {
    chain.push(c.name);
    c = Object.getPrototypeOf(c);
  }
  return chain;
}

// cls 是否在链上继承自名为 targetName 的类
function extendsClassNamed(cls, targetName) {
  let c = cls;
  while (c && c.name) {
    if (c.name === targetName) return true;
    c = Object.getPrototypeOf(c);
  }
  return false;
}

// 公开原型方法名（own + inherited，剔除 constructor / _private / Object.prototype）
function protoMethods(cls) {
  const set = new Set();
  let proto = cls.prototype;
  while (proto && proto !== Object.prototype) {
    for (const k of Object.getOwnPropertyNames(proto)) {
      if (k === 'constructor' || k.startsWith('_')) continue;
      const d = Object.getOwnPropertyDescriptor(proto, k);
      if (d && typeof d.value === 'function') set.add(k);
    }
    proto = Object.getPrototypeOf(proto);
  }
  return [...set].sort();
}

async function main() {
  const crawlee = await import('crawlee');

  const result = {
    tool: 'crawlee',
    probe: 'engine-parity API surface (Cheerio vs Playwright vs Puppeteer)',
    measured_at_utc: new Date().toISOString(),
    node: process.version,
    installed_crawlee_version: installedCrawleeVersion(),
    puppeteer_peer_installed: (() => {
      try { require.resolve('puppeteer'); return true; } catch { return false; }
    })(),
    note:
      'capability inventory only; class import + prototype introspection; zero timing; ' +
      'no browser launch, no chromium download, no network navigation. ' +
      'Every field is computed at runtime (anti-hardcode).',
  };

  // --- 1) 顶层 export 存在性（三引擎 + queue/storage/router 工厂） ---
  const exportNames = [
    'CheerioCrawler', 'PlaywrightCrawler', 'PuppeteerCrawler',
    'BasicCrawler', 'HttpCrawler', 'BrowserCrawler', 'JSDOMCrawler',
    'RequestQueue', 'Dataset', 'KeyValueStore', 'Router',
    'createCheerioRouter', 'createPlaywrightRouter', 'createPuppeteerRouter', 'createBasicRouter',
  ];
  const exportsCheck = {};
  for (const n of exportNames) exportsCheck[n] = typeof crawlee[n];
  result.top_level_exports = exportsCheck;

  const { CheerioCrawler, PlaywrightCrawler, PuppeteerCrawler } = crawlee;

  if (typeof PuppeteerCrawler !== 'function') {
    result.error = 'PuppeteerCrawler not exported from crawlee; parity probe cannot run';
    write(result);
    return;
  }

  // --- 2) 每类的继承链 + 是否 extends BasicCrawler + 公开原型方法 ---
  const engines = {
    CheerioCrawler,
    PlaywrightCrawler,
    PuppeteerCrawler,
  };
  const perEngine = {};
  const methodSets = {};
  for (const [label, cls] of Object.entries(engines)) {
    const methods = protoMethods(cls);
    methodSets[label] = new Set(methods);
    perEngine[label] = {
      prototype_chain: protoChain(cls),
      extends_BasicCrawler: extendsClassNamed(cls, 'BasicCrawler'),
      extends_BrowserCrawler: extendsClassNamed(cls, 'BrowserCrawler'),
      extends_HttpCrawler: extendsClassNamed(cls, 'HttpCrawler'),
      public_method_count: methods.length,
      public_methods: methods,
    };
  }
  result.per_engine = perEngine;

  // --- 3) 交集 / 差集（parity 的量化边界） ---
  const ch = methodSets.CheerioCrawler;
  const pl = methodSets.PlaywrightCrawler;
  const pu = methodSets.PuppeteerCrawler;
  const sharedAll = [...ch].filter((x) => pl.has(x) && pu.has(x)).sort();
  const cheerioOnly = [...ch].filter((x) => !(pl.has(x) && pu.has(x))).sort();
  const browserSharedNotCheerio = [...pl].filter((x) => pu.has(x) && !ch.has(x)).sort();
  const plNotPu = [...pl].filter((x) => !pu.has(x)).sort();
  const puNotPl = [...pu].filter((x) => !pl.has(x)).sort();

  result.parity = {
    shared_by_all_three_count: sharedAll.length,
    shared_by_all_three: sharedAll,
    cheerio_only: cheerioOnly,
    browser_only_shared_by_playwright_and_puppeteer: browserSharedNotCheerio,
    playwright_not_in_puppeteer: plNotPu,
    puppeteer_not_in_playwright: puNotPl,
    // 关键断言：Puppeteer 与 Playwright 原型方法集是否逐一相同
    puppeteer_playwright_prototype_methods_identical:
      plNotPu.length === 0 && puNotPl.length === 0,
  };

  // --- 4) handler-context 表面（从 .d.ts 静态读取的结构事实，不执行） ---
  //   说明 parity 的边界：三引擎的 requestHandler 都收到同一 RestrictedCrawlingContext
  //   基础成员；引擎特有的是内容句柄（Cheerio: $ ；browser: page）。
  //   这里如实标注「来源=类型定义文件」，不是运行期自省——因为 context 是运行时才注入。
  const dtsFacts = readContextDtsFacts(require);
  result.handler_context_from_type_defs = dtsFacts;

  write(result);
}

// 从已装 @crawlee 的 .d.ts 里静态确认 context 结构（存在性 grep，不 eval 类型）
// 注意：内部 .d.ts 子路径被各包 package.json 的 "exports" map 挡住，require.resolve 会失败。
// 因此从各包 package.json 的位置推出包根目录，再拼内部相对路径直接读文件系统。
function readContextDtsFacts(req) {
  const facts = { source: 'static read of installed @crawlee/*/**.d.ts (structural, not executed)' };
  const pkgRoot = (pkgName) => dirname(req.resolve(`${pkgName}/package.json`));
  const grab = (pkgName, relFile, iface, needles) => {
    try {
      const p = join(pkgRoot(pkgName), relFile);
      const text = readFileSync(p, 'utf8');
      const start = text.indexOf(`export interface ${iface}`);
      if (start < 0) return { found: false };
      // 取该 interface 声明起点后的一段（含 extends 子句 + body 到下一个 export/EOF）
      const nextExport = text.indexOf('\nexport ', start + 1);
      const chunk = text.slice(start, nextExport < 0 ? undefined : nextExport);
      const hits = {};
      for (const nd of needles) hits[nd] = chunk.includes(nd);
      // 抽 extends 子句首行
      const firstLine = chunk.split('\n')[0].slice(0, 400);
      return { found: true, declaration_head: firstLine, contains: hits };
    } catch (e) {
      return { found: false, error: e.message };
    }
  };

  facts.RestrictedCrawlingContext = grab(
    '@crawlee/core', 'crawlers/crawler_commons.d.ts',
    'RestrictedCrawlingContext',
    ['request', 'pushData', 'enqueueLinks', 'addRequests', 'useState', 'getKeyValueStore', 'log'],
  );
  facts.BrowserCrawlingContext = grab(
    '@crawlee/browser', 'internals/browser-crawler.d.ts',
    'BrowserCrawlingContext',
    ['page', 'response', 'browserController'],
  );
  facts.CheerioCrawlingContext = grab(
    '@crawlee/cheerio', 'internals/cheerio-crawler.d.ts',
    'CheerioCrawlingContext',
    ['$:', 'parseWithCheerio', 'waitForSelector'],
  );
  facts.PlaywrightCrawlingContext = grab(
    '@crawlee/playwright', 'internals/playwright-crawler.d.ts',
    'PlaywrightCrawlingContext',
    ['BrowserCrawlingContext', 'PlaywrightCrawler', 'Page'],
  );
  facts.PuppeteerCrawlingContext = grab(
    '@crawlee/puppeteer', 'internals/puppeteer-crawler.d.ts',
    'PuppeteerCrawlingContext',
    ['BrowserCrawlingContext', 'PuppeteerCrawler', 'Page'],
  );
  return facts;
}

function write(result) {
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(result, null, 2), 'utf8');
  console.log(`wrote ${OUT}`);
  console.log(`  crawlee: ${result.installed_crawlee_version}  node: ${result.node}`);
  if (result.parity) {
    console.log(`  shared by all three: ${result.parity.shared_by_all_three_count} public methods`);
    console.log(
      `  puppeteer==playwright prototype methods identical: ${result.parity.puppeteer_playwright_prototype_methods_identical}`,
    );
    console.log(`  cheerio-only: [${result.parity.cheerio_only.join(', ')}]`);
    console.log(
      `  browser-only (pw+pptr): [${result.parity.browser_only_shared_by_playwright_and_puppeteer.join(', ')}]`,
    );
  }
}

main().catch((e) => {
  console.error('probe failed:', e);
  process.exit(1);
});
