// Reproducible evaluation material for the Colly single-tool pack.
// Colly is a Go HTTP scraping framework (no JS execution). This harness mirrors
// the other packs' fixtures and writes raw artifacts + a summary. Not final blog copy.
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/gocolly/colly/v2"
)

type Product struct {
	ID       int     `json:"id"`
	Name     string  `json:"name"`
	Price    float64 `json:"price"`
	Rating   int     `json:"rating"`
	Category string  `json:"category"`
}

var products []Product
var dynamic []Product

var article = map[string]interface{}{
	"title":  "How Operations Teams Evaluate Web Scraping Tools",
	"author": "Thunderbit Research Lab",
	"paragraphs": []string{
		"Modern scraping tools are judged by repeatable extraction, not by popularity alone.",
		"A useful evaluation checks setup friction, selectors, crawl control, output shape, error handling, and operational controls.",
		"This fixture includes navigation, related links, and footer text so targeted extraction can be verified against ground truth.",
	},
}

func init() {
	cats := []string{"analytics", "commerce", "ops"}
	for i := 1; i <= 12; i++ {
		products = append(products, Product{
			ID: i, Name: fmt.Sprintf("Colly Fixture Product %02d", i),
			Price: float64(int((15.0+float64(i)*2.9)*100)) / 100, Rating: (i % 5) + 1,
			Category: cats[i%3],
		})
	}
	dynamic = products[:8]
}

func card(p Product) string {
	return fmt.Sprintf(`<article class="product-card" data-product-id="%d"><h2 class="product-name">%s</h2><p class="category">%s</p><p class="price">$%.2f</p><p class="rating">%d stars</p><a class="detail-link" href="/product/%d">detail</a></article>`,
		p.ID, p.Name, p.Category, p.Price, p.Rating, p.ID)
}

func pageHTML(title, body string) string {
	return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>` + title + `</title></head><body>` + body + `</body></html>`
}

func fixtureServer() *httptest.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/static/catalog", func(w http.ResponseWriter, r *http.Request) {
		pg, _ := strconv.Atoi(r.URL.Query().Get("page"))
		if pg == 0 {
			pg = 1
		}
		start := (pg - 1) * 6
		var b strings.Builder
		for _, p := range products[start:min(start+6, len(products))] {
			b.WriteString(card(p))
		}
		next := ""
		if pg == 1 {
			next = `<a class="next-page" href="/static/catalog?page=2">Next</a>`
		}
		fmt.Fprint(w, pageHTML("Catalog", `<nav><a href="/">Home</a></nav><main><h1>Catalog</h1><section>`+b.String()+`</section>`+next+`</main><footer>Footer.</footer>`))
	})
	mux.HandleFunc("/product/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, pageHTML("Product", `<main><article class="product-detail"><h1>Detail</h1></article></main>`))
	})
	mux.HandleFunc("/article/1", func(w http.ResponseWriter, r *http.Request) {
		var b strings.Builder
		for _, p := range article["paragraphs"].([]string) {
			b.WriteString("<p>" + p + "</p>")
		}
		fmt.Fprint(w, pageHTML(article["title"].(string), `<nav>Home Login</nav><main><article><h1>`+article["title"].(string)+`</h1><p class="byline">By <span class="author">`+article["author"].(string)+`</span></p>`+b.String()+`</article></main><footer>Copyright.</footer>`))
	})
	mux.HandleFunc("/dynamic/catalog", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, pageHTML("Dynamic", `<main><h1>Dynamic</h1><section id="dynamic-products"></section></main><script>/* JS injects cards; HTTP sees none */</script>`))
	})
	mux.HandleFunc("/api/dynamic-products", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(dynamic)
	})
	mux.HandleFunc("/failure/500", func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		fmt.Fprint(w, pageHTML("Home", `<main><h1>Home</h1><ul><li><a href="/static/catalog?page=1">Catalog</a></li><li><a href="/article/1">Article</a></li><li><a href="/dynamic/catalog">Dynamic</a></li></ul></main>`))
	})
	return httptest.NewServer(mux)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

var RAW string

func writeJSON(name string, v interface{}) {
	b, _ := json.MarshalIndent(v, "", "  ")
	os.WriteFile(filepath.Join(RAW, name), append(b, '\n'), 0o644)
}

func main() {
	projectDir, _ := filepath.Abs(".")
	RAW = filepath.Join(projectDir, "results")
	os.MkdirAll(RAW, 0o755)

	srv := fixtureServer()
	defer srv.Close()
	base := srv.URL

	summary := map[string]interface{}{
		"run_started_at":  time.Now().UTC().Format(time.RFC3339),
		"tool":            "colly",
		"go_version":      "",
		"fixture_base_url": base,
		"tests":           map[string]interface{}{},
	}
	tests := summary["tests"].(map[string]interface{})
	writeJSON("local_fixture_ground_truth.json", map[string]interface{}{"products": products, "article": article, "dynamic_products": dynamic})

	// 1) Static catalog + pagination.
	{
		t0 := time.Now()
		var rows []Product
		c := colly.NewCollector()
		c.OnHTML(".product-card", func(e *colly.HTMLElement) {
			id, _ := strconv.Atoi(e.Attr("data-product-id"))
			price, _ := strconv.ParseFloat(strings.TrimPrefix(strings.TrimSpace(e.ChildText(".price")), "$"), 64)
			rating, _ := strconv.Atoi(strings.TrimSpace(strings.TrimSuffix(e.ChildText(".rating"), " stars")))
			rows = append(rows, Product{ID: id, Name: e.ChildText(".product-name"), Price: price, Rating: rating, Category: e.ChildText(".category")})
		})
		c.OnHTML(".next-page", func(e *colly.HTMLElement) { e.Request.Visit(e.Attr("href")) })
		c.Visit(base + "/static/catalog?page=1")
		c.Wait()
		sort.Slice(rows, func(i, j int) bool { return rows[i].ID < rows[j].ID })
		writeJSON("local_static_catalog.json", rows)
		found := map[string]bool{}
		for _, r := range rows {
			found[r.Name] = true
		}
		hit := 0
		for _, p := range products {
			if found[p.Name] {
				hit++
			}
		}
		tests["local_static_catalog"] = map[string]interface{}{
			"url": base + "/static/catalog?page=1", "success": true, "items": len(rows),
			"pagination_followed": len(rows) > 6,
			"recall":              float64(hit) / float64(len(products)),
			"elapsed_seconds":     time.Since(t0).Seconds(),
		}
	}

	// 2) Article.
	{
		t0 := time.Now()
		var title string
		var paras []string
		c := colly.NewCollector()
		c.OnHTML("article", func(e *colly.HTMLElement) {
			title = e.ChildText("h1")
			e.ForEach("p", func(_ int, el *colly.HTMLElement) {
				t := strings.TrimSpace(el.Text)
				if t != "" && !strings.HasPrefix(t, "By ") {
					paras = append(paras, t)
				}
			})
		})
		c.Visit(base + "/article/1")
		c.Wait()
		writeJSON("local_article.json", map[string]interface{}{"title": title, "paragraphs": paras})
		pf := 0
		for _, want := range article["paragraphs"].([]string) {
			for _, got := range paras {
				if got == want {
					pf++
				}
			}
		}
		tests["local_article"] = map[string]interface{}{
			"url": base + "/article/1", "success": true,
			"title_found": title == article["title"].(string),
			"paragraphs_found": pf, "paragraphs_expected": len(article["paragraphs"].([]string)),
			"elapsed_seconds": time.Since(t0).Seconds(),
		}
	}

	// 3) Dynamic page (no JS) -> 0 cards.
	{
		t0 := time.Now()
		n := 0
		c := colly.NewCollector()
		c.OnHTML(".product-card", func(e *colly.HTMLElement) { n++ })
		c.Visit(base + "/dynamic/catalog")
		c.Wait()
		writeJSON("local_dynamic_page_no_js.json", map[string]interface{}{"product_cards_found": n})
		tests["local_dynamic_page_no_js"] = map[string]interface{}{
			"url": base + "/dynamic/catalog", "success": true,
			"expected_limitation_observed": n == 0, "product_cards_found": n,
			"note":            "Colly is HTTP-only and does not execute JavaScript.",
			"elapsed_seconds": time.Since(t0).Seconds(),
		}
	}

	// 4) Dynamic JSON API (OnResponse).
	{
		t0 := time.Now()
		var data []Product
		c := colly.NewCollector()
		c.OnResponse(func(r *colly.Response) { json.Unmarshal(r.Body, &data) })
		c.Visit(base + "/api/dynamic-products")
		c.Wait()
		writeJSON("local_dynamic_api.json", data)
		tests["local_dynamic_api"] = map[string]interface{}{
			"url": base + "/api/dynamic-products", "success": true, "items": len(data),
			"recall":          float64(len(data)) / float64(len(dynamic)),
			"elapsed_seconds": time.Since(t0).Seconds(),
		}
	}

	// 5) HTTP 500 (OnError).
	{
		t0 := time.Now()
		var status int
		c := colly.NewCollector()
		c.OnError(func(r *colly.Response, err error) { status = r.StatusCode })
		c.OnResponse(func(r *colly.Response) { status = r.StatusCode })
		c.Visit(base + "/failure/500")
		c.Wait()
		writeJSON("local_failure_500.json", map[string]interface{}{"status": status})
		tests["local_failure_500"] = map[string]interface{}{
			"url": base + "/failure/500", "success": true, "confirmed_status": status,
			"note":            "Colly routes non-2xx to OnError with the response status code.",
			"elapsed_seconds": time.Since(t0).Seconds(),
		}
	}

	// 6) Crawl graph with MaxDepth.
	{
		t0 := time.Now()
		type pg struct {
			URL   string `json:"url"`
			Depth int    `json:"depth"`
		}
		seen := map[string]int{}
		c := colly.NewCollector(colly.MaxDepth(2))
		c.OnRequest(func(r *colly.Request) {
			d, _ := strconv.Atoi(r.Ctx.Get("depth"))
			seen[r.URL.String()] = d
		})
		c.OnHTML("a[href]", func(e *colly.HTMLElement) {
			d, _ := strconv.Atoi(e.Request.Ctx.Get("depth"))
			req := e.Request.AbsoluteURL(e.Attr("href"))
			if strings.HasPrefix(req, base) {
				ctx := colly.NewContext()
				ctx.Put("depth", strconv.Itoa(d+1))
				c.Request("GET", req, nil, ctx, nil)
			}
		})
		ctx := colly.NewContext()
		ctx.Put("depth", "0")
		c.Request("GET", base+"/", nil, ctx, nil)
		c.Wait()
		var pages []pg
		for u, d := range seen {
			pages = append(pages, pg{URL: u, Depth: d})
		}
		sort.Slice(pages, func(i, j int) bool {
			if pages[i].Depth != pages[j].Depth {
				return pages[i].Depth < pages[j].Depth
			}
			return pages[i].URL < pages[j].URL
		})
		writeJSON("local_crawl_graph.json", pages)
		depthCounts := map[string]int{}
		for _, p := range pages {
			depthCounts[strconv.Itoa(p.Depth)]++
		}
		tests["local_crawl_graph"] = map[string]interface{}{
			"url": base, "success": true, "pages_seen": len(pages), "depth_counts": depthCounts,
			"note":            "colly.MaxDepth(2) + AbsoluteURL crawl.",
			"elapsed_seconds": time.Since(t0).Seconds(),
		}
	}

	// 7) Public: Books to Scrape.
	{
		t0 := time.Now()
		type book struct {
			Title string `json:"title"`
			Price string `json:"price"`
		}
		var books []book
		c := colly.NewCollector()
		c.SetRequestTimeout(45 * time.Second)
		c.OnHTML(".product_pod", func(e *colly.HTMLElement) {
			books = append(books, book{Title: e.ChildAttr("h3 a", "title"), Price: strings.TrimSpace(e.ChildText(".price_color"))})
		})
		err := c.Visit("https://books.toscrape.com/")
		c.Wait()
		if err != nil {
			tests["public_books_to_scrape"] = map[string]interface{}{"url": "https://books.toscrape.com/", "tested_on": time.Now().UTC().Format(time.RFC3339), "success": false, "error": err.Error()}
		} else {
			writeJSON("public_books_to_scrape.json", books)
			tests["public_books_to_scrape"] = map[string]interface{}{"url": "https://books.toscrape.com/", "tested_on": time.Now().UTC().Format(time.RFC3339), "success": len(books) > 0, "items": len(books), "elapsed_seconds": time.Since(t0).Seconds()}
		}
	}

	// 8) Public: Quotes JS (no render) -> 0.
	{
		t0 := time.Now()
		n := 0
		c := colly.NewCollector()
		c.SetRequestTimeout(45 * time.Second)
		c.OnHTML(".quote", func(e *colly.HTMLElement) { n++ })
		err := c.Visit("https://quotes.toscrape.com/js/")
		c.Wait()
		if err != nil {
			tests["public_quotes_js_no_render"] = map[string]interface{}{"url": "https://quotes.toscrape.com/js/", "tested_on": time.Now().UTC().Format(time.RFC3339), "success": false, "error": err.Error()}
		} else {
			writeJSON("public_quotes_js_no_render.json", map[string]interface{}{"quote_nodes_found": n})
			tests["public_quotes_js_no_render"] = map[string]interface{}{"url": "https://quotes.toscrape.com/js/", "tested_on": time.Now().UTC().Format(time.RFC3339), "success": true, "expected_limitation_observed": n == 0, "quote_nodes_found": n, "elapsed_seconds": time.Since(t0).Seconds()}
		}
	}

	summary["run_completed_at"] = time.Now().UTC().Format(time.RFC3339)
	writeJSON("colly-test-summary.json", summary)
	b, _ := json.MarshalIndent(summary, "", "  ")
	fmt.Println(string(b))
}
