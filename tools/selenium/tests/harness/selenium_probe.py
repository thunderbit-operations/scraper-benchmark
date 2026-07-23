#!/usr/bin/env python3
"""selenium_probe — the evidence harness for the selenium evaluation pack.

One script with sub-commands, each driving a real Chrome via **chromedriver over the W3C
WebDriver protocol** (not CDP) against the local Python fixture, printing a JSON result to
stdout. The `run_*.py` orchestrators start the fixture, invoke this probe as a FRESH
subprocess, and compute recall vs the fixture's ground truth — so no verdict/observation
string is hardcoded here; this program returns raw extracted content and measured
booleans/timings/pids only.

It is the parity mirror of the chromedp/rod probes (same fixture, same process-truth
method) so selenium's numbers are directly comparable on the same host + Chrome build.
The key structural difference it exposes: Selenium's chain is THREE processes —
python -> chromedriver -> chrome (+ chrome helpers) — where the CDP drivers are two
(go -> chrome). chromedriver is a separate long-lived child process; this probe reports
its pid so the orchestrator can measure BOTH driver and browser lifecycle by process-truth.

Chrome binary: full **Chrome for Testing 151.0.7922.10 (build 1232)** driven with
`--headless=new`, the same Chrome *version/build* the chromedp/rod packs used (they pointed
CDP at the headless-shell binary of the same build). Full Chrome is used here because
chromedriver + a client-supplied `--user-data-dir` on chrome-headless-shell trips
"unable to discover open pages"; full Chrome accepts the client profile dir, which is what
the pgrep-by-unique-user-data-dir process-truth method (parity with chromedp/rod) needs.
The DOM/JS execution timing that class A/B/C recall measures is identical across the two
headless variants (same Blink/V8 build), so cross-tool recall comparison stays valid.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

HOME = str(Path.home())
# argv[0] basename of the *browser* process (helpers carry "... Helper" + --type=).
BROWSER_EXE_BASENAME = "Google Chrome for Testing"


def redact(s: str) -> str:
    return s.replace(HOME, "~") if isinstance(s, str) else s


def _redact(obj):
    if isinstance(obj, str):
        return obj.replace(HOME, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def emit(v) -> None:
    print(json.dumps(_redact(v)))


def fail(msg: str, err: Exception) -> None:
    emit({"error": msg, "detail": redact(str(err))})
    sys.exit(1)


# --- process-truth helpers (mirror of the Go probe's countBrowserProcs) ---------------
def browser_procs(udd_key: str) -> int:
    """Count *browser* Chrome procs carrying udd_key: argv[0] basename must be the
    Chrome-for-Testing browser exe and the command must have no --type= flag — so Chrome
    helper procs (renderer/gpu/utility, which carry --type=) are excluded. Process-truth."""
    try:
        out = subprocess.run(["pgrep", "-f", udd_key], capture_output=True, text=True).stdout.split()
    except Exception:
        return 0
    n = 0
    for pid in out:
        cmd = subprocess.run(["ps", "-p", pid, "-o", "command="], capture_output=True, text=True).stdout
        if udd_key not in cmd or "--type=" in cmd:
            continue
        # argv[0] is the .app bundle path; test its basename against the browser exe.
        argv0 = cmd.strip().split(" --", 1)[0]
        if os.path.basename(argv0.strip()) == BROWSER_EXE_BASENAME:
            n += 1
    return n


def proc_alive(pid: int, needle: str = "chromedriver") -> bool:
    """PID-precise liveness with a command-name guard against PID reuse."""
    c = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return bool(c.strip()) and needle in c


CHROME = os.environ.get(
    "SEL_CHROME",
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-1232/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    ),
)


SHELL = os.path.expanduser(
    "~/Library/Caches/ms-playwright/chromium_headless_shell-1232/"
    "chrome-headless-shell-mac-arm64/chrome-headless-shell"
)


def build_options(udd: str | None, chrome_override: str | None = None,
                  headless_mode: str = "new") -> Options:
    opts = Options()
    opts.binary_location = chrome_override or CHROME
    if headless_mode == "new":
        opts.add_argument("--headless=new")
    # headless_mode == "none": binary is inherently headless (chrome-headless-shell)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    if udd:
        opts.add_argument(f"--user-data-dir={udd}")
    return opts


def make_service(driver_path: str | None) -> Service:
    # driver_path set  -> explicit Service, SKIPS Selenium Manager.
    # driver_path None -> Service() with no path -> Selenium Manager resolves (per-call).
    return Service(executable_path=driver_path) if driver_path else Service()


def hrefs_of(driver) -> list[str]:
    try:
        res = driver.execute_script(
            "return Array.from(document.querySelectorAll('a')).map(a => a.getAttribute('href'))"
        )
        return [str(x) for x in res] if res else []
    except WebDriverException:
        return []


def parse_common(args: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            val = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else "true"
            out[key] = val
            i += 2 if val != "true" or (i + 1 < len(args) and not args[i + 1].startswith("--")) else 1
        else:
            i += 1
    return out


# --- recall: navigate then apply one selenium idiom, return rendered source + hrefs ----
#   pagesource -> get() (blocks to load event) + read page_source immediately  [default]
#   implicit   -> implicitly_wait(N) + get() + find_element(#delayed) + page_source
#   explicit   -> get() + WebDriverWait(N).until(presence_of #delayed) + page_source
#   poll       -> get() + poll page_source until class-C marker appears (or deadline)
def cmd_recall(a: dict[str, str]) -> None:
    url = a["url"]; strategy = a.get("strategy", "pagesource"); udd = a.get("user-data-dir")
    driver_path = a.get("driver-path") or None
    try:
        driver = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
    except WebDriverException as e:
        fail("driver start failed", e)
        return
    try:
        started = time.time()
        if strategy == "implicit":
            driver.implicitly_wait(20)
        driver.get(url)  # pageLoadStrategy=normal: blocks until the load event
        if strategy == "explicit":
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "delayed-injected")))
            except TimeoutException:
                pass
        elif strategy == "implicit":
            try:
                driver.find_element(By.ID, "delayed-injected")  # implicit wait polls
            except WebDriverException:
                pass
        elif strategy == "poll":
            deadline = time.time() + 10
            while time.time() < deadline:
                if ("DELAYED" + "_INJECTED_" + "MARKER" + "_C") in driver.page_source:
                    break
                time.sleep(0.1)
        # 'pagesource': no extra wait beyond get()'s load-event block
        html = driver.page_source
        hrefs = hrefs_of(driver)
        emit({
            "strategy": strategy, "url": url,
            "elapsed_ms": int((time.time() - started) * 1000),
            "outer_html_len": len(html), "outer_html": html, "hrefs": hrefs,
        })
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --- waitsem: presence (attached) vs visibility on a display:none node, + selector model
def cmd_waitsem(a: dict[str, str]) -> None:
    url = a["url"]; udd = a.get("user-data-dir"); driver_path = a.get("driver-path") or None
    try:
        driver = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
    except WebDriverException as e:
        fail("driver start failed", e)
        return

    def timed(fn):
        t0 = time.time()
        try:
            fn()
            return True, int((time.time() - t0) * 1000), ""
        except Exception as e:
            return False, int((time.time() - t0) * 1000), redact(type(e).__name__)

    try:
        driver.get(url)
        TO = 4
        # attached-but-hidden (display:none): find_element (presence) returns; explicit
        # visibility wait blocks to the deadline.
        el_ret, el_ms, el_err = timed(lambda: driver.find_element(By.ID, "hidden-target"))
        vis_ret, vis_ms, vis_err = timed(
            lambda: WebDriverWait(driver, TO).until(
                EC.visibility_of_element_located((By.ID, "hidden-target"))))
        # selector model on the VISIBLE node: CSS vs XPath both resolve.
        css_ret, css_ms, css_err = timed(lambda: driver.find_element(By.CSS_SELECTOR, "#visible-target"))
        xp_ret, xp_ms, xp_err = timed(lambda: driver.find_element(By.XPATH, "//div[@id='visible-target']"))
        # never-appearing selector: deadline honored, clean timeout, no hang.
        nv_ret, nv_ms, nv_err = timed(
            lambda: WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.ID, "never-appears-xyz"))))
        emit({
            "timeout_ms": TO * 1000,
            "hidden_node": {
                "presence_returned": el_ret, "presence_ms": el_ms, "presence_err": el_err,
                "visibility_returned": vis_ret, "visibility_ms": vis_ms, "visibility_err": vis_err,
            },
            "selector_model_visible_node": {
                "css_returned": css_ret, "css_ms": css_ms, "css_err": css_err,
                "xpath_returned": xp_ret, "xpath_ms": xp_ms, "xpath_err": xp_err,
            },
            "never_appears": {"returned": nv_ret, "ms": nv_ms, "err": nv_err},
        })
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --- graceful: start, count driver+browser procs, quit(), time the reap of BOTH --------
def cmd_graceful(a: dict[str, str]) -> None:
    url = a["url"]; udd = a["user-data-dir"]; driver_path = a.get("driver-path") or None
    udd_key = os.path.basename(udd)
    try:
        driver = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
    except WebDriverException as e:
        fail("driver start failed", e)
        return
    cd_pid = driver.service.process.pid
    driver.get(url)
    before_browser = browser_procs(udd_key)
    before_driver_alive = proc_alive(cd_pid)

    t0 = time.time()
    try:
        driver.quit()  # W3C DELETE session + terminates the chromedriver process
    except Exception:
        pass
    reap_ms = -1
    after_browser = before_browser
    after_driver_alive = before_driver_alive
    deadline = time.time() + 5
    while time.time() < deadline:
        after_browser = browser_procs(udd_key)
        after_driver_alive = proc_alive(cd_pid)
        if after_browser == 0 and not after_driver_alive:
            reap_ms = int((time.time() - t0) * 1000)
            break
        time.sleep(0.05)
    # belt-and-suspenders cleanup (the harness must never leave a process)
    subprocess.run(["pkill", "-f", udd_key], capture_output=True)
    emit({
        "chromedriver_pid": cd_pid,
        "browser_procs_before_quit": before_browser,
        "chromedriver_alive_before_quit": before_driver_alive,
        "browser_procs_after_quit": after_browser,
        "chromedriver_alive_after_quit": after_driver_alive,
        "reaped_both": (after_browser == 0 and not after_driver_alive),
        "reap_ms": reap_ms,
    })


# --- startidle: start, emit pids, then exit(0) WITHOUT quit, or block for a SIGKILL -----
def cmd_startidle(a: dict[str, str]) -> None:
    url = a["url"]; udd = a["user-data-dir"]; onstart = a.get("onstart", "exit")
    driver_path = a.get("driver-path") or None
    udd_key = os.path.basename(udd)
    try:
        driver = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
    except WebDriverException as e:
        fail("driver start failed", e)
        return
    driver.get(url)
    emit({
        "started": True, "onstart": onstart, "pid": os.getpid(),
        "chromedriver_pid": driver.service.process.pid, "udd_key": udd_key,
        "browser_procs_up": browser_procs(udd_key),
    })
    sys.stdout.flush()
    if onstart == "block":
        while True:
            time.sleep(1)  # the runner SIGKILLs us (crash simulation)
    os._exit(0)  # leave WITHOUT quit(): no session teardown, no atexit — orphan is measured


# --- coldstart: one full cold cycle (instantiate -> navigate -> first script) -----------
def cmd_coldstart(a: dict[str, str]) -> None:
    url = a["url"]; udd = a.get("user-data-dir"); driver_path = a.get("driver-path") or None
    # variant "shell" drives chrome-headless-shell (no --headless flag, no custom udd) for a
    # binary-matched comparison to chromedp/rod; default drives full Chrome + --headless=new.
    variant = a.get("variant", "full")
    if variant == "shell":
        chrome_override, headless_mode, udd = SHELL, "none", None
    else:
        chrome_override, headless_mode = None, "new"
    started = time.time()
    try:
        driver = webdriver.Chrome(
            service=make_service(driver_path),
            options=build_options(udd, chrome_override, headless_mode))
    except WebDriverException as e:
        fail("driver start failed", e)
        return
    try:
        driver.get(url)
        title = driver.execute_script("return document.title")
        emit({
            "elapsed_ms": int((time.time() - started) * 1000),
            "title": title,
            "variant": variant,
            "used_selenium_manager": driver_path is None,
        })
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --- concurrency: shared driver (N tabs, one session) vs separate drivers (N sessions) ---
# A single WebDriver session is NOT thread-safe and serializes commands over one HTTP
# connection to chromedriver, so "shared" runs the N navigations SEQUENTIALLY on one
# driver (the only correct single-session idiom). "separate" runs N drivers CONCURRENTLY.
# This asymmetry is the point: Selenium cannot reproduce chromedp/rod's "one browser, N
# CONCURRENT pages" model — concurrency requires N sessions => N driver + N browser procs.
# Peak process counts are taken DETERMINISTICALLY at a barrier after the timed work, with
# every session still alive (pre-quit), so the expensive pgrep/ps is OUTSIDE the wall clock.
def cmd_concurrency(a: dict[str, str]) -> None:
    import threading
    url = a["url"]; mode = a.get("mode", "shared"); n = int(a.get("n", "4"))
    dir_key = a["dir-key"]; driver_path = a.get("driver-path") or None
    key_base = os.path.basename(dir_key)

    first_error = ""
    driver_pids: list[int] = []
    keys: list[str] = []
    drivers = []

    started = time.time()
    if mode == "shared":
        udd = dir_key
        try:
            driver = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
        except WebDriverException as e:
            fail("driver start failed", e)
            return
        drivers.append(driver); driver_pids.append(driver.service.process.pid); keys.append(udd)
        try:
            for _ in range(n):
                driver.switch_to.new_window("tab")  # one session serializes these
                driver.get(url)
                driver.execute_script("return document.title")
        except WebDriverException as e:
            first_error = redact(str(e)[:200])
    else:  # separate: N drivers, concurrent
        lock = threading.Lock()
        threads = []

        def worker(i: int):
            nonlocal first_error
            udd = f"{dir_key}-{i}"
            try:
                drv = webdriver.Chrome(service=make_service(driver_path), options=build_options(udd))
            except WebDriverException as e:
                if not first_error:
                    first_error = redact(str(e)[:200])
                return
            with lock:
                drivers.append(drv); driver_pids.append(drv.service.process.pid); keys.append(udd)
            try:
                drv.get(url)
                drv.execute_script("return document.title")
            except WebDriverException as e:
                if not first_error:
                    first_error = redact(str(e)[:200])

        for i in range(n):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t); t.start()
        for t in threads:
            t.join()

    wall_ms = int((time.time() - started) * 1000)
    # Deterministic peak: every session is still alive here (nothing quit yet).
    peak_browser = sum(browser_procs(os.path.basename(k)) for k in keys)
    peak_driver = sum(1 for p in driver_pids if proc_alive(p))

    for drv in drivers:
        try:
            drv.quit()
        except Exception:
            pass
    subprocess.run(["pkill", "-f", key_base], capture_output=True)
    for i in range(n):
        subprocess.run(["pkill", "-f", os.path.basename(f"{dir_key}-{i}")], capture_output=True)

    emit({
        "mode": mode, "n": n,
        "wall_ms": wall_ms,
        "chrome_browser_procs_peak": peak_browser,
        "chromedriver_procs_peak": peak_driver,
        "first_error": first_error,
    })


def main() -> None:
    if len(sys.argv) < 2:
        fail("usage: selenium_probe <recall|waitsem|graceful|startidle|coldstart|concurrency> [flags]",
             RuntimeError("no subcommand"))
    sub = sys.argv[1]
    a = parse_common(sys.argv[2:])
    dispatch = {
        "recall": cmd_recall, "waitsem": cmd_waitsem, "graceful": cmd_graceful,
        "startidle": cmd_startidle, "coldstart": cmd_coldstart, "concurrency": cmd_concurrency,
    }
    fn = dispatch.get(sub)
    if not fn:
        fail("unknown subcommand", RuntimeError(sub))
    fn(a)


if __name__ == "__main__":
    main()
