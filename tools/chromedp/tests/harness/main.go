// Command chromedp_probe is the evidence harness for the chromedp evaluation pack.
//
// It compiles to a single binary with sub-commands, each driving a real Chrome via
// chromedp against the local Python fixture and printing a JSON result to stdout.
// The Python runners start the fixture, invoke this binary, and compute recall vs
// the fixture's ground truth — so no verdict/observation string is hardcoded here;
// this program returns raw extracted content and measured booleans/timings only.
//
// We intentionally build a binary and run it (not `go test`) to avoid the Go-1.25+
// `go test` runner incompatibility with NewExecAllocator (chromedp issue #1591).
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/chromedp/chromedp"
)

func redact(s string) string {
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		return strings.ReplaceAll(s, home, "~")
	}
	return s
}

func emit(v any) {
	b, _ := json.Marshal(v)
	// Redact any home-prefixed absolute path in the serialized output.
	fmt.Println(redact(string(b)))
}

func fail(msg string, err error) {
	emit(map[string]any{"error": msg, "detail": redact(fmt.Sprint(err))})
	os.Exit(1)
}

// allocOpts builds exec-allocator options with an explicit Chrome path and a chosen
// user-data-dir (so processes are identifiable via pgrep on that dir).
func allocOpts(chromePath, userDataDir string) []chromedp.ExecAllocatorOption {
	opts := append([]chromedp.ExecAllocatorOption{}, chromedp.DefaultExecAllocatorOptions[:]...)
	if chromePath != "" {
		opts = append(opts, chromedp.ExecPath(chromePath))
	}
	if userDataDir != "" {
		opts = append(opts, chromedp.UserDataDir(userDataDir))
	}
	return opts
}

// countBrowserProcs returns how many *browser* (main, not --type=renderer/gpu/...)
// Chrome processes carry the given user-data-dir substring — process-truth, the
// analog of the fixture's server-side hit counter.
func countBrowserProcs(dirKey string) int {
	out, err := exec.Command("pgrep", "-f", dirKey).Output()
	if err != nil {
		return 0
	}
	n := 0
	for _, line := range strings.Fields(string(out)) {
		cmd, err := exec.Command("ps", "-p", line, "-o", "command=").Output()
		if err != nil {
			continue
		}
		c := string(cmd)
		if !strings.Contains(c, dirKey) {
			continue
		}
		// Main browser process has no --type= flag; helpers (renderer/gpu/utility) do.
		if !strings.Contains(c, "--type=") {
			n++
		}
	}
	return n
}

// ---------------------------------------------------------------------------
// recall: navigate then apply one wait strategy, return the rendered outerHTML +
// the hrefs present. Python computes A/B/C recall from the ground-truth markers.
// ---------------------------------------------------------------------------
func cmdRecall(args []string) {
	fs := flag.NewFlagSet("recall", flag.ExitOnError)
	url := fs.String("url", "", "page URL (e.g. base/classes?delay=800)")
	chrome := fs.String("chrome", "", "chrome exec path")
	strategy := fs.String("strategy", "none", "none|waitready|waitvisible|poll")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	_ = fs.Parse(args)

	opts := allocOpts(*chrome, *userDataDir)
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
	defer cancelAlloc()
	ctx, cancel := chromedp.NewContext(allocCtx)
	defer cancel()
	ctx, cancelT := context.WithTimeout(ctx, 30*time.Second)
	defer cancelT()

	var outer string
	var hrefs []string
	started := time.Now()

	tasks := chromedp.Tasks{chromedp.Navigate(*url)}
	switch *strategy {
	case "none":
		// read immediately after Navigate (which returns on the load event)
	case "waitready":
		tasks = append(tasks, chromedp.WaitReady("body", chromedp.ByQuery))
	case "waitvisible":
		// wait keyed to the class-C node id (unambiguous CSS via ByQuery)
		tasks = append(tasks, chromedp.WaitVisible("#delayed-injected", chromedp.ByQuery))
	case "poll":
		tasks = append(tasks, chromedp.ActionFunc(func(ctx context.Context) error {
			deadline := time.Now().Add(10 * time.Second)
			for time.Now().Before(deadline) {
				var html string
				if err := chromedp.OuterHTML("html", &html, chromedp.ByQuery).Do(ctx); err == nil {
					if strings.Contains(html, "DELAYED"+"_INJECTED_"+"MARKER"+"_C") {
						return nil
					}
				}
				time.Sleep(100 * time.Millisecond)
			}
			return nil // timed out; recall will show the miss
		}))
	default:
		fail("unknown strategy", errors.New(*strategy))
	}
	tasks = append(tasks,
		chromedp.OuterHTML("html", &outer, chromedp.ByQuery),
		chromedp.Evaluate(`Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href'))`, &hrefs),
	)

	if err := chromedp.Run(ctx, tasks); err != nil {
		fail("run failed", err)
	}
	emit(map[string]any{
		"strategy":       *strategy,
		"url":            *url,
		"elapsed_ms":     time.Since(started).Milliseconds(),
		"outer_html_len": len(outer),
		"outer_html":     outer,
		"hrefs":          hrefs,
	})
}

// runOne runs a single action under its own timeout and reports return/timeout+ms.
func runOne(parent context.Context, timeout time.Duration, action chromedp.Action) (bool, int64, string) {
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	started := time.Now()
	err := chromedp.Run(ctx, action)
	ms := time.Since(started).Milliseconds()
	if err == nil {
		return true, ms, ""
	}
	return false, ms, redact(err.Error())
}

// ---------------------------------------------------------------------------
// waitsem: WaitReady vs WaitVisible on an attached-but-hidden (display:none) node,
// plus the selector-semantics contrast (#440) on a visible node.
// ---------------------------------------------------------------------------
func cmdWaitsem(args []string) {
	fs := flag.NewFlagSet("waitsem", flag.ExitOnError)
	url := fs.String("url", "", "waitsem page URL")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	_ = fs.Parse(args)

	opts := allocOpts(*chrome, *userDataDir)
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
	defer cancelAlloc()
	ctx, cancel := chromedp.NewContext(allocCtx)
	defer cancel()

	if err := chromedp.Run(ctx, chromedp.Navigate(*url)); err != nil {
		fail("navigate failed", err)
	}

	const to = 4 * time.Second
	// attached-but-hidden node (display:none): does WaitReady return? does WaitVisible time out?
	wrRet, wrMs, wrErr := runOne(ctx, to, chromedp.WaitReady("#hidden-target", chromedp.ByQuery))
	wvRet, wvMs, wvErr := runOne(ctx, to, chromedp.WaitVisible("#hidden-target", chromedp.ByQuery))

	// selector semantics on the VISIBLE node: default query vs ByID vs ByQuery.
	defRet, defMs, defErr := runOne(ctx, to, chromedp.WaitVisible("#visible-target"))
	idRet, idMs, idErr := runOne(ctx, to, chromedp.WaitVisible("visible-target", chromedp.ByID))
	qRet, qMs, qErr := runOne(ctx, to, chromedp.WaitVisible("#visible-target", chromedp.ByQuery))

	emit(map[string]any{
		"timeout_ms": to.Milliseconds(),
		"hidden_node": map[string]any{
			"waitready_returned":   wrRet, "waitready_ms": wrMs, "waitready_err": wrErr,
			"waitvisible_returned": wvRet, "waitvisible_ms": wvMs, "waitvisible_err": wvErr,
		},
		"selector_semantics_visible_node": map[string]any{
			"default_query_returned": defRet, "default_query_ms": defMs, "default_query_err": defErr,
			"byid_returned": idRet, "byid_ms": idMs, "byid_err": idErr,
			"byquery_returned": qRet, "byquery_ms": qMs, "byquery_err": qErr,
		},
	})
}

// ---------------------------------------------------------------------------
// lifecycle: start Chrome, count browser procs on our user-data-dir, cancel, and
// measure whether/when the process is reaped (process-truth).
// ---------------------------------------------------------------------------
func cmdLifecycle(args []string) {
	fs := flag.NewFlagSet("lifecycle", flag.ExitOnError)
	url := fs.String("url", "", "page URL to navigate")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "UNIQUE user data dir (pgrep key)")
	_ = fs.Parse(args)
	if *userDataDir == "" {
		fail("user-data-dir required", errors.New("empty"))
	}

	opts := allocOpts(*chrome, *userDataDir)
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
	ctx, cancel := chromedp.NewContext(allocCtx)
	if err := chromedp.Run(ctx, chromedp.Navigate(*url), chromedp.WaitReady("body", chromedp.ByQuery)); err != nil {
		cancel()
		cancelAlloc()
		fail("navigate failed", err)
	}
	before := countBrowserProcs(*userDataDir)

	// cancel context + allocator (the documented cleanup path) and time the reap.
	cancel()
	cancelAlloc()
	reapStart := time.Now()
	after := before
	reapMs := int64(-1)
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		after = countBrowserProcs(*userDataDir)
		if after == 0 {
			reapMs = time.Since(reapStart).Milliseconds()
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	emit(map[string]any{
		"chrome_browser_procs_before_cancel": before,
		"chrome_browser_procs_after_cancel":  after,
		"reaped":                             after == 0,
		"reap_ms":                            reapMs,
	})
}

// ---------------------------------------------------------------------------
// startnocancel: start Chrome and EXIT WITHOUT cancelling (simulate a program that
// forgets defer cancel). The Python runner checks, after this process exits,
// whether the Chrome process orphaned on macOS — then cleans it up.
// ---------------------------------------------------------------------------
func cmdStartNoCancel(args []string) {
	fs := flag.NewFlagSet("startnocancel", flag.ExitOnError)
	url := fs.String("url", "", "page URL to navigate")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "UNIQUE user data dir (pgrep key)")
	_ = fs.Parse(args)

	opts := allocOpts(*chrome, *userDataDir)
	allocCtx, _ := chromedp.NewExecAllocator(context.Background(), opts...) // intentionally NOT cancelled
	ctx, _ := chromedp.NewContext(allocCtx)                                 // intentionally NOT cancelled
	if err := chromedp.Run(ctx, chromedp.Navigate(*url), chromedp.WaitReady("body", chromedp.ByQuery)); err != nil {
		fail("navigate failed", err)
	}
	emit(map[string]any{"started": true, "note": "exiting without cancel on purpose"})
	os.Exit(0) // leave scope without cancelling; Chrome fate is what we measure
}

// ---------------------------------------------------------------------------
// coldstart: one full cold cycle (allocator -> context -> navigate -> first eval).
// Invoked fresh per process so each measurement is genuinely cold.
// ---------------------------------------------------------------------------
func cmdColdstart(args []string) {
	fs := flag.NewFlagSet("coldstart", flag.ExitOnError)
	url := fs.String("url", "", "page URL")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	_ = fs.Parse(args)

	started := time.Now()
	opts := allocOpts(*chrome, *userDataDir)
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
	defer cancelAlloc()
	ctx, cancel := chromedp.NewContext(allocCtx)
	defer cancel()
	ctx, cancelT := context.WithTimeout(ctx, 30*time.Second)
	defer cancelT()

	var title string
	if err := chromedp.Run(ctx,
		chromedp.Navigate(*url),
		chromedp.Evaluate(`document.title`, &title),
	); err != nil {
		fail("run failed", err)
	}
	emit(map[string]any{"elapsed_ms": time.Since(started).Milliseconds(), "title": title})
}

// ---------------------------------------------------------------------------
// concurrency: N navigations either sharing one browser (child contexts) or across
// N separate browsers. Reports wall time + peak browser-process count.
// ---------------------------------------------------------------------------
func cmdConcurrency(args []string) {
	fs := flag.NewFlagSet("concurrency", flag.ExitOnError)
	url := fs.String("url", "", "page URL")
	chrome := fs.String("chrome", "", "chrome exec path")
	mode := fs.String("mode", "shared", "shared|separate")
	n := fs.Int("n", 4, "number of concurrent navigations")
	dirKey := fs.String("dir-key", "", "UNIQUE user-data-dir key/prefix (pgrep key)")
	_ = fs.Parse(args)
	if *dirKey == "" {
		fail("dir-key required", errors.New("empty"))
	}

	var peak int
	var mu sync.Mutex
	recordPeak := func() {
		c := countBrowserProcs(*dirKey)
		mu.Lock()
		if c > peak {
			peak = c
		}
		mu.Unlock()
	}

	started := time.Now()
	var wg sync.WaitGroup
	errCh := make(chan error, *n)

	if *mode == "shared" {
		// One browser; N child contexts (tabs) share it.
		opts := allocOpts(*chrome, *dirKey) // single shared user-data-dir
		allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
		defer cancelAlloc()
		// establish the browser once
		root, cancelRoot := chromedp.NewContext(allocCtx)
		if err := chromedp.Run(root, chromedp.Navigate(*url)); err != nil {
			cancelRoot()
			fail("root nav failed", err)
		}
		for i := 0; i < *n; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				ctx, cancel := chromedp.NewContext(root) // child tab of the same browser
				defer cancel()
				var title string
				if err := chromedp.Run(ctx, chromedp.Navigate(*url), chromedp.Evaluate(`document.title`, &title)); err != nil {
					errCh <- err
					return
				}
				recordPeak()
			}()
		}
		wg.Wait()
		recordPeak()
		cancelRoot()
	} else {
		// N separate browsers, each its own user-data-dir (Chrome can't share one).
		for i := 0; i < *n; i++ {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				dir := fmt.Sprintf("%s-%d", *dirKey, i)
				opts := allocOpts(*chrome, dir)
				allocCtx, cancelAlloc := chromedp.NewExecAllocator(context.Background(), opts...)
				defer cancelAlloc()
				ctx, cancel := chromedp.NewContext(allocCtx)
				defer cancel()
				var title string
				if err := chromedp.Run(ctx, chromedp.Navigate(*url), chromedp.Evaluate(`document.title`, &title)); err != nil {
					errCh <- err
					return
				}
				recordPeak()
			}(i)
		}
		wg.Wait()
		recordPeak()
	}
	close(errCh)
	var firstErr string
	for e := range errCh {
		if firstErr == "" {
			firstErr = redact(e.Error())
		}
	}
	emit(map[string]any{
		"mode":              *mode,
		"n":                 *n,
		"wall_ms":           time.Since(started).Milliseconds(),
		"chrome_procs_peak": peak,
		"first_error":       firstErr,
	})
}

func main() {
	if len(os.Args) < 2 {
		fail("usage: chromedp_probe <recall|waitsem|lifecycle|startnocancel|coldstart|concurrency> [flags]", errors.New("no subcommand"))
	}
	sub, rest := os.Args[1], os.Args[2:]
	switch sub {
	case "recall":
		cmdRecall(rest)
	case "waitsem":
		cmdWaitsem(rest)
	case "lifecycle":
		cmdLifecycle(rest)
	case "startnocancel":
		cmdStartNoCancel(rest)
	case "coldstart":
		cmdColdstart(rest)
	case "concurrency":
		cmdConcurrency(rest)
	default:
		fail("unknown subcommand", errors.New(sub))
	}
}
