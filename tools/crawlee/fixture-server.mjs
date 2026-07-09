// Local fixture server for the Crawlee single-tool research pack.
// Mirrors the Scrapy pack fixtures so cross-tool results stay comparable.
// Not final blog copy; this only serves reproducible ground-truth pages.

import http from 'node:http';
import { URL } from 'node:url';

export const PRODUCTS = Array.from({ length: 12 }, (_, index) => {
  const i = index + 1;
  return {
    id: i,
    name: `Crawlee Fixture Product ${String(i).padStart(2, '0')}`,
    price: Number((15.0 + i * 2.9).toFixed(2)),
    rating: (i % 5) + 1,
    category: ['analytics', 'commerce', 'ops'][i % 3],
  };
});

export const ARTICLE = {
  title: 'How Operations Teams Evaluate Web Scraping Tools',
  author: 'Thunderbit Research Lab',
  date: '2026-07-09',
  body_paragraphs: [
    'Modern scraping tools are judged by repeatable extraction, not by popularity alone.',
    'A useful evaluation checks setup friction, selectors, crawl control, output shape, error handling, and operational controls.',
    'This fixture includes navigation, related links, and footer text so targeted extraction can be verified against ground truth.',
  ],
};

export const DYNAMIC_PRODUCTS = PRODUCTS.slice(0, 8);

function htmlPage(title, body) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 32px auto; line-height: 1.45; }
    nav, footer, aside { color: #666; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .product-card { border: 1px solid #ddd; padding: 12px; }
    .price { font-weight: 700; }
  </style>
</head>
<body>
${body}
</body>
</html>`;
}

function productCard(product) {
  return `<article class="product-card" data-product-id="${product.id}">
  <h2 class="product-name">${product.name}</h2>
  <p class="category">${product.category}</p>
  <p class="price">$${product.price.toFixed(2)}</p>
  <p class="rating">${product.rating} stars</p>
  <a class="detail-link" href="/product/${product.id}">View detail</a>
</article>`;
}

function send(res, status, body, contentType = 'text/html; charset=utf-8') {
  const payload = Buffer.from(body);
  res.writeHead(status, {
    'Content-Type': contentType,
    'Content-Length': payload.length,
  });
  res.end(payload);
}

function handle(req, res, baseUrl) {
  const parsed = new URL(req.url, baseUrl);
  const path = parsed.pathname;
  const query = parsed.searchParams;

  if (path === '/robots.txt') {
    return send(res, 200, 'User-agent: *\nAllow: /\nDisallow: /blocked-by-robots\nCrawl-delay: 1\n', 'text/plain; charset=utf-8');
  }

  if (path === '/') {
    const body = `<main>
  <h1>Crawlee Fixture Site</h1>
  <ul>
    <li><a href="/static/catalog?page=1">Static catalog</a></li>
    <li><a href="/dynamic/catalog">Dynamic catalog</a></li>
    <li><a href="/article/1">Article fixture</a></li>
    <li><a href="/failure/500">Failure fixture</a></li>
  </ul>
</main>`;
    return send(res, 200, htmlPage('Fixture Home', body));
  }

  if (path === '/ground-truth.json') {
    return send(res, 200, JSON.stringify({ products: PRODUCTS, article: ARTICLE, dynamic_products: DYNAMIC_PRODUCTS }, null, 2), 'application/json');
  }

  if (path === '/static/catalog') {
    const page = Number(query.get('page') || '1');
    const perPage = 6;
    const start = (page - 1) * perPage;
    const subset = PRODUCTS.slice(start, start + perPage);
    const cards = subset.map(productCard).join('\n');
    const nextLink = page === 1 ? '<a class="next-page" href="/static/catalog?page=2">Next page</a>' : '';
    const body = `<nav><a href="/">Home</a> | <a href="/article/1">Research article</a></nav>
<main>
  <h1>Static Product Catalog</h1>
  <section class="grid">${cards}</section>
  ${nextLink}
</main>
<footer>Footer boilerplate that should not be treated as product data.</footer>`;
    return send(res, 200, htmlPage(`Static Catalog Page ${page}`, body));
  }

  if (path.startsWith('/product/')) {
    const productId = Number(path.split('/').pop());
    const product = PRODUCTS[productId - 1];
    const body = `<main>
  <article class="product-detail" data-product-id="${product.id}">
    <h1>${product.name}</h1>
    <dl>
      <dt>Price</dt><dd class="price">$${product.price.toFixed(2)}</dd>
      <dt>Rating</dt><dd>${product.rating} stars</dd>
      <dt>Category</dt><dd>${product.category}</dd>
    </dl>
  </article>
</main>`;
    return send(res, 200, htmlPage(product.name, body));
  }

  if (path === '/dynamic/catalog') {
    const body = `<main>
  <h1>Dynamic Product Catalog</h1>
  <p id="status">Loading products...</p>
  <section id="dynamic-products" class="grid"></section>
</main>
<script>
setTimeout(async () => {
  const response = await fetch('/api/dynamic-products');
  const products = await response.json();
  document.querySelector('#status').textContent = 'Loaded ' + products.length + ' products';
  document.querySelector('#dynamic-products').innerHTML = products.map((product) => \`
    <article class="product-card" data-product-id="\${product.id}">
      <h2 class="product-name">\${product.name}</h2>
      <p class="category">\${product.category}</p>
      <p class="price">$\${Number(product.price).toFixed(2)}</p>
      <p class="rating">\${product.rating} stars</p>
    </article>
  \`).join('');
}, 450);
</script>`;
    return send(res, 200, htmlPage('Dynamic Catalog', body));
  }

  if (path === '/api/dynamic-products') {
    return send(res, 200, JSON.stringify(DYNAMIC_PRODUCTS), 'application/json');
  }

  if (path === '/article/1') {
    const body = `<nav>Home | Products | Pricing | Login</nav>
<main>
  <article>
    <h1>${ARTICLE.title}</h1>
    <p class="byline">By <span class="author">${ARTICLE.author}</span> on <time>${ARTICLE.date}</time></p>
    ${ARTICLE.body_paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join('')}
  </article>
</main>
<aside>
  <h2>Related links</h2>
  <a href="/static/catalog?page=1">Static catalog</a>
  <p>Subscribe to our fictional newsletter.</p>
</aside>
<footer>Copyright fixture footer.</footer>`;
    return send(res, 200, htmlPage(ARTICLE.title, body));
  }

  if (path === '/failure/500') {
    return send(res, 500, 'Intentional fixture failure', 'text/plain');
  }

  return send(res, 404, 'Not found', 'text/plain');
}

export async function startFixtureServer() {
  const server = http.createServer((req, res) => {
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    handle(req, res, baseUrl);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const baseUrl = `http://127.0.0.1:${server.address().port}`;
  return {
    baseUrl,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}
