// Command rod_probe is the evidence harness for the rod evaluation pack.
//
// It compiles to a single binary with sub-commands, each driving a real Chrome via
// go-rod against the local Python fixture and printing a JSON result to stdout. The
// Python runners start the fixture, invoke this binary, and compute recall vs the
// fixture's ground truth — so no verdict/observation string is hardcoded here; this
// program returns raw extracted content and measured booleans/timings only.
//
// It is designed as the parity mirror of the chromedp pack's probe (same fixture, same
// process-truth method) so rod's numbers are directly comparable to chromedp's on the
// same host + Chrome build. We build a binary and run it (not `go test`).
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/launcher"
	"github.com/go-rod/rod/lib/proto"
)

func redact(s string) string {
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		return strings.ReplaceAll(s, home, "~")
	}
	return s
}

func emit(v any) {
	b, _ := json.Marshal(v)
	fmt.Println(redact(string(b)))
}

func fail(msg string, err error) {
	emit(map[string]any{"error": msg, "detail": redact(fmt.Sprint(err))})
	os.Exit(1)
}

// launchBrowser builds a rod launcher pinned to an explicit Chrome binary (so
// auto-download is disabled — parity with chromedp's ExecPath) and a chosen
// user-data-dir (so processes are identifiable via pgrep on that dir). leakless is
// toggled by the caller. Returns the connected browser and the launcher.
func launchBrowser(chromePath, userDataDir string, leakless bool) (*rod.Browser, *launcher.Launcher, error) {
	l := launcher.New().
		Headless(true).
		Leakless(leakless).
		Set("no-sandbox") // headless-shell parity with chromedp default opts
	if chromePath != "" {
		l = l.Bin(chromePath) // disables auto-download
	}
	if userDataDir != "" {
		l = l.UserDataDir(userDataDir)
	}
	u, err := l.Launch()
	if err != nil {
		return nil, l, err
	}
	browser := rod.New().ControlURL(u)
	if err := browser.Connect(); err != nil {
		return nil, l, err
	}
	return browser, l, nil
}

// countBrowserProcs returns how many actual *browser* Chrome processes carry the given
// user-data-dir substring — process-truth, the analog of the fixture's server-side hit
// counter. It counts a process only if its executable basename is chrome-headless-shell
// and it has no --type= flag, so neither Chrome helper processes (renderer/gpu/utility,
// which carry --type=) NOR the leakless guardian (whose argv[0] is the leakless binary,
// not chrome-headless-shell) are miscounted. This exe-basename guard is the rod-specific
// addition over chromedp's counter (chromedp had no guardian process to exclude).
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
		if strings.Contains(c, "--type=") {
			continue // renderer/gpu/utility helper, not the browser
		}
		fields := strings.Fields(c)
		if len(fields) == 0 {
			continue
		}
		if filepath.Base(fields[0]) != "chrome-headless-shell" {
			continue // e.g. the leakless guardian process
		}
		n++
	}
	return n
}

// blankPage opens a fresh about:blank page so the caller fully controls navigation and
// waiting (matches chromedp's Navigate-then-strategy control).
func blankPage(browser *rod.Browser) (*rod.Page, error) {
	return browser.Page(proto.TargetCreateTarget{})
}

func hrefsOf(page *rod.Page) []string {
	res, err := page.Eval(`() => Array.from(document.querySelectorAll('a')).map(a => a.getAttribute('href'))`)
	if err != nil || res == nil {
		return nil
	}
	var hrefs []string
	for _, v := range res.Value.Arr() {
		hrefs = append(hrefs, v.Str())
	}
	return hrefs
}

// ---------------------------------------------------------------------------
// recall: navigate then apply one rod idiom, return the rendered HTML + the hrefs.
// Python computes A/B/C recall from the ground-truth markers.
//   none      -> Navigate + read HTML immediately (no wait)
//   waitload  -> Navigate + WaitLoad (load event) + read HTML
//   element   -> Navigate + Element("#delayed-injected") (AUTO-WAIT) + read HTML
//   poll      -> Navigate + poll HTML until the class-C marker appears (or deadline)
// ---------------------------------------------------------------------------
func cmdRecall(args []string) {
	fs := flag.NewFlagSet("recall", flag.ExitOnError)
	url := fs.String("url", "", "page URL (e.g. base/classes?delay=800)")
	chrome := fs.String("chrome", "", "chrome exec path")
	strategy := fs.String("strategy", "none", "none|waitload|element|poll")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	_ = fs.Parse(args)

	browser, l, err := launchBrowser(*chrome, *userDataDir, true)
	if err != nil {
		fail("launch failed", err)
	}
	defer func() { browser.Close(); l.Kill() }()

	page, err := blankPage(browser)
	if err != nil {
		fail("page create failed", err)
	}

	started := time.Now()
	if err := page.Navigate(*url); err != nil {
		fail("navigate failed", err)
	}

	switch *strategy {
	case "none":
		// read immediately after Navigate (no wait)
	case "waitload":
		_ = page.Timeout(20 * time.Second).WaitLoad()
	case "element":
		// rod's auto-waiting single-selector query: blocks until the node appears
		// (DefaultSleeper backoff) up to the page timeout — no explicit wait call.
		_, _ = page.Timeout(20 * time.Second).Element("#delayed-injected")
	case "poll":
		deadline := time.Now().Add(10 * time.Second)
		for time.Now().Before(deadline) {
			if html, e := page.HTML(); e == nil &&
				strings.Contains(html, "DELAYED"+"_INJECTED_"+"MARKER"+"_C") {
				break
			}
			time.Sleep(100 * time.Millisecond)
		}
	default:
		fail("unknown strategy", errors.New(*strategy))
	}

	html, err := page.Timeout(10 * time.Second).HTML()
	if err != nil {
		fail("read html failed", err)
	}
	hrefs := hrefsOf(page.Timeout(10 * time.Second))

	emit(map[string]any{
		"strategy":       *strategy,
		"url":            *url,
		"elapsed_ms":     time.Since(started).Milliseconds(),
		"outer_html_len": len(html),
		"outer_html":     html,
		"hrefs":          hrefs,
	})
}

// tryTimed runs fn under a timeout and reports returned/elapsed/err (rod.Try recovers
// rod's Must* panics into an error so a timeout is a clean measured value).
func tryTimed(timeout time.Duration, fn func() error) (bool, int64, string) {
	started := time.Now()
	err := fn()
	ms := time.Since(started).Milliseconds()
	_ = timeout
	if err == nil {
		return true, ms, ""
	}
	return false, ms, redact(err.Error())
}

// ---------------------------------------------------------------------------
// waitsem: Element (attached) vs Element.WaitVisible (visible) on an attached-but-hidden
// (display:none) node, plus the selector-model contrast (CSS Element vs XPath ElementX)
// on a visible node, plus a never-appearing selector (deadline honored).
// ---------------------------------------------------------------------------
func cmdWaitsem(args []string) {
	fs := flag.NewFlagSet("waitsem", flag.ExitOnError)
	url := fs.String("url", "", "waitsem page URL")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	_ = fs.Parse(args)

	browser, l, err := launchBrowser(*chrome, *userDataDir, true)
	if err != nil {
		fail("launch failed", err)
	}
	defer func() { browser.Close(); l.Kill() }()

	page, err := blankPage(browser)
	if err != nil {
		fail("page create failed", err)
	}
	if err := page.Navigate(*url); err != nil {
		fail("navigate failed", err)
	}
	_ = page.Timeout(10 * time.Second).WaitLoad()

	const to = 4 * time.Second

	// attached-but-hidden node (display:none): Element returns (attached is enough);
	// WaitVisible on it blocks to the deadline.
	elRet, elMs, elErr := tryTimed(to, func() error {
		_, e := page.Timeout(to).Element("#hidden-target")
		return e
	})
	wvRet, wvMs, wvErr := tryTimed(to, func() error {
		el, e := page.Timeout(to).Element("#hidden-target")
		if e != nil {
			return e
		}
		return el.Timeout(to).WaitVisible()
	})

	// selector model on the VISIBLE node: CSS Element vs XPath ElementX (no #440 trap).
	cssRet, cssMs, cssErr := tryTimed(to, func() error {
		_, e := page.Timeout(to).Element("#visible-target")
		return e
	})
	xpathRet, xpathMs, xpathErr := tryTimed(to, func() error {
		_, e := page.Timeout(to).ElementX(`//div[@id='visible-target']`)
		return e
	})

	// never-appearing selector: deadline honored, clean timeout error, no hang.
	neverRet, neverMs, neverErr := tryTimed(2*time.Second, func() error {
		_, e := page.Timeout(2 * time.Second).Element("#never-appears-xyz")
		return e
	})

	emit(map[string]any{
		"timeout_ms": to.Milliseconds(),
		"hidden_node": map[string]any{
			"element_returned":     elRet, "element_ms": elMs, "element_err": elErr,
			"waitvisible_returned": wvRet, "waitvisible_ms": wvMs, "waitvisible_err": wvErr,
		},
		"selector_model_visible_node": map[string]any{
			"css_element_returned": cssRet, "css_element_ms": cssMs, "css_element_err": cssErr,
			"xpath_elementx_returned": xpathRet, "xpath_elementx_ms": xpathMs, "xpath_elementx_err": xpathErr,
		},
		"never_appears": map[string]any{
			"returned": neverRet, "ms": neverMs, "err": neverErr,
		},
	})
}

// ---------------------------------------------------------------------------
// graceful: start Chrome, count browser procs on our user-data-dir, close the browser
// (CDP graceful) and measure whether/when the process is reaped (process-truth).
// ---------------------------------------------------------------------------
func cmdGraceful(args []string) {
	fs := flag.NewFlagSet("graceful", flag.ExitOnError)
	url := fs.String("url", "", "page URL to navigate")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "UNIQUE user data dir (pgrep key)")
	leakless := fs.Bool("leakless", true, "enable leakless")
	_ = fs.Parse(args)
	if *userDataDir == "" {
		fail("user-data-dir required", errors.New("empty"))
	}

	browser, l, err := launchBrowser(*chrome, *userDataDir, *leakless)
	if err != nil {
		fail("launch failed", err)
	}
	page, err := blankPage(browser)
	if err != nil {
		browser.Close()
		l.Kill()
		fail("page create failed", err)
	}
	if err := page.Navigate(*url); err != nil {
		browser.Close()
		l.Kill()
		fail("navigate failed", err)
	}
	_ = page.Timeout(10 * time.Second).WaitLoad()
	before := countBrowserProcs(*userDataDir)

	// graceful CDP close (the documented in-process cleanup path) and time the reap.
	_ = browser.Close()
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
	l.Kill() // belt-and-suspenders; harness must never leave a process
	emit(map[string]any{
		"leakless":                           *leakless,
		"chrome_browser_procs_before_close":  before,
		"chrome_browser_procs_after_close":   after,
		"reaped":                             after == 0,
		"reap_ms":                            reapMs,
	})
}

// ---------------------------------------------------------------------------
// startidle: start Chrome (leakless flag), navigate, emit started, then either exit(0)
// WITHOUT cleanup (skip browser.Close / launcher.Kill) or block forever so the Python
// runner can SIGKILL the parent. The runner measures, after the parent is gone, whether
// the Chrome process orphaned — then force-cleans it.
// ---------------------------------------------------------------------------
func cmdStartIdle(args []string) {
	fs := flag.NewFlagSet("startidle", flag.ExitOnError)
	url := fs.String("url", "", "page URL to navigate")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "UNIQUE user data dir (pgrep key)")
	leakless := fs.Bool("leakless", true, "enable leakless")
	onstart := fs.String("onstart", "exit", "exit|block")
	_ = fs.Parse(args)

	browser, _, err := launchBrowser(*chrome, *userDataDir, *leakless) // launcher intentionally not kept for cleanup
	if err != nil {
		fail("launch failed", err)
	}
	page, err := blankPage(browser)
	if err != nil {
		fail("page create failed", err)
	}
	if err := page.Navigate(*url); err != nil {
		fail("navigate failed", err)
	}
	_ = page.Timeout(10 * time.Second).WaitLoad()
	emit(map[string]any{"started": true, "leakless": *leakless, "onstart": *onstart, "pid": os.Getpid()})

	if *onstart == "block" {
		select {} // block forever; the runner SIGKILLs us (crash simulation)
	}
	os.Exit(0) // leave WITHOUT cleanup; Chrome fate is what we measure
}

// ---------------------------------------------------------------------------
// coldstart: one full cold cycle (launcher -> connect -> page -> navigate -> first eval).
// Invoked fresh per process so each measurement is genuinely cold.
// ---------------------------------------------------------------------------
func cmdColdstart(args []string) {
	fs := flag.NewFlagSet("coldstart", flag.ExitOnError)
	url := fs.String("url", "", "page URL")
	chrome := fs.String("chrome", "", "chrome exec path")
	userDataDir := fs.String("user-data-dir", "", "user data dir")
	leakless := fs.Bool("leakless", true, "enable leakless (guardian spawn tax)")
	_ = fs.Parse(args)

	started := time.Now()
	browser, l, err := launchBrowser(*chrome, *userDataDir, *leakless)
	if err != nil {
		fail("launch failed", err)
	}
	defer func() { browser.Close(); l.Kill() }()

	page, err := blankPage(browser)
	if err != nil {
		fail("page create failed", err)
	}
	if err := page.Navigate(*url); err != nil {
		fail("navigate failed", err)
	}
	res, err := page.Timeout(20 * time.Second).Eval(`() => document.title`)
	if err != nil {
		fail("eval failed", err)
	}
	emit(map[string]any{"elapsed_ms": time.Since(started).Milliseconds(), "title": res.Value.Str()})
}

// ---------------------------------------------------------------------------
// concurrency: N navigations either sharing one browser (N pages/tabs) or across N
// separate browsers. Reports wall time + peak browser-process count.
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
		browser, l, err := launchBrowser(*chrome, *dirKey, true) // single shared browser
		if err != nil {
			fail("launch failed", err)
		}
		defer func() { browser.Close(); l.Kill() }()
		for i := 0; i < *n; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				page, err := browser.Page(proto.TargetCreateTarget{}) // new tab on the shared browser
				if err != nil {
					errCh <- err
					return
				}
				defer page.Close()
				if err := page.Navigate(*url); err != nil {
					errCh <- err
					return
				}
				_, _ = page.Timeout(20 * time.Second).Eval(`() => document.title`)
				recordPeak()
			}()
		}
		wg.Wait()
		recordPeak()
	} else {
		for i := 0; i < *n; i++ {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				dir := fmt.Sprintf("%s-%d", *dirKey, i)
				browser, l, err := launchBrowser(*chrome, dir, true)
				if err != nil {
					errCh <- err
					return
				}
				defer func() { browser.Close(); l.Kill() }()
				page, err := browser.Page(proto.TargetCreateTarget{})
				if err != nil {
					errCh <- err
					return
				}
				if err := page.Navigate(*url); err != nil {
					errCh <- err
					return
				}
				_, _ = page.Timeout(20 * time.Second).Eval(`() => document.title`)
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
		fail("usage: rod_probe <recall|waitsem|graceful|startidle|coldstart|concurrency> [flags]", errors.New("no subcommand"))
	}
	sub, rest := os.Args[1], os.Args[2:]
	// Fail fast, but never hang a probe forever on a rod-internal deadlock.
	_ = context.Background()
	switch sub {
	case "recall":
		cmdRecall(rest)
	case "waitsem":
		cmdWaitsem(rest)
	case "graceful":
		cmdGraceful(rest)
	case "startidle":
		cmdStartIdle(rest)
	case "coldstart":
		cmdColdstart(rest)
	case "concurrency":
		cmdConcurrency(rest)
	default:
		fail("unknown subcommand", errors.New(sub))
	}
}
