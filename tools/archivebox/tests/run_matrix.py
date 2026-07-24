#!/usr/bin/env python3
"""ArchiveBox redundant-output coverage matrix harness.

Drives the official archivebox Docker image over a local fixture (two pages:
/static and /dynamic) and measures, for EACH preservation output, whether it
captured each of four planted ground-truth tokens:

  STATIC  — visible article text in initial HTML (baseline; every output should get it)
  RUNTIME — text injected into the DOM by JS at runtime (never a contiguous byte in
            anything served; a contiguous match PROVES the output captured the
            JS-materialised DOM)
  JSLIT   — a literal inside app.js (byte-level; separates "saved the bytes" from
            "extracted the reading text")
  BOILER  — nav/aside/footer chrome (separates "whole page" from "just the article")

Everything measured is deterministic pass/fail of token capture + ArchiveBox's own
per-extractor status from index.json + output byte sizes + server-side fetch counts.
No timing claim is treated as a headline (timing is recorded observationally only).

Configs:
  FULL      all content extractors on; run on /static AND /dynamic
  NOCHROME  dom/singlefile/pdf/screenshot OFF (chrome disabled); run on /dynamic
            -> shows readability/htmltotext INHERIT runtime coverage from chrome
  MERCURY   attribute server fetches: mercury-only vs wget-only on /dynamic

Outputs: artifacts/raw/*.json (host paths redacted). Requires Docker with the
archivebox image and (optional) pypdf in the venv for PDF text-layer verification.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture_server as F  # noqa: E402

IMG = os.environ.get("ABOX_IMAGE", "archivebox/archivebox:latest")
HERE = Path(__file__).resolve().parent
PACK = HERE.parent
DATA_ROOT = HERE / "data"          # gitignored
RAW = PACK / "artifacts" / "raw"

TOKENS = {
    "STATIC": F.STATIC_TOKEN,
    "RUNTIME": F.RUNTIME_TOKEN,
    "JSLIT": F.JSLIT_TOKEN,
    "BOILER": F.BOILER_TOKEN,
}

# Content extractors we score. Their canonical files inside a snapshot dir:
#   wget      -> <host+port>/ mirror dir  + warc/*.warc.gz
#   singlefile-> singlefile.html
#   dom       -> output.html
#   readability-> readability/content.txt
#   mercury   -> mercury/content.txt
#   htmltotext-> htmltotext.txt
#   pdf       -> output.pdf  (text layer via pypdf)
#   screenshot-> screenshot.png (binary; visual-only, not text-greppable)

_HOME = os.path.expanduser("~")
_TMP = os.environ.get("TMPDIR", "/tmp").rstrip("/")


def _redact(obj):
    """Scrub host-specific absolute paths from anything we write to disk."""
    if isinstance(obj, str):
        s = obj.replace(_TMP, "<TMP>")
        s = re.sub(r"/private/var/folders/[^\s\"']*", "<TMP>", s)
        s = re.sub(r"/var/folders/[^\s\"']*", "<TMP>", s)
        s = s.replace(_HOME, "~")
        return s
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _write(name: str, payload: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / name, "w") as f:
        json.dump(_redact(payload), f, indent=2, sort_keys=True)
    print(f"  wrote artifacts/raw/{name}")


def _rb(p: str) -> bytes:
    try:
        return open(p, "rb").read()
    except OSError:
        return b""


def _pdf_text(path: str) -> tuple[str, str]:
    """Return (text, method). Uses pypdf if available; else empty + 'no-pypdf'."""
    if not os.path.exists(path):
        return "", "absent"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "no-pypdf"
    try:
        txt = "".join(p.extract_text() or "" for p in PdfReader(path).pages)
        return txt, "pypdf"
    except Exception as e:  # noqa: BLE001
        return "", f"pypdf-error:{type(e).__name__}"


def _grep_tokens(data: bytes) -> dict[str, bool]:
    return {k: (v.encode() in data) for k, v in TOKENS.items()}


class Box:
    """One archivebox data dir."""

    def __init__(self, data_dir: Path):
        self.data = data_dir
        shutil.rmtree(self.data, ignore_errors=True)
        self.data.mkdir(parents=True)
        os.chmod(self.data, 0o777)

    def _run(self, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "run", "--rm", "-v", f"{self.data}:/data", IMG, *args],
            capture_output=True, text=True, timeout=timeout,
        )

    def init(self) -> None:
        self._run("init", "--setup", timeout=180)

    def config(self, **kv: object) -> None:
        for k, v in kv.items():
            self._run("config", "--set", f"{k}={v}")

    def get_config(self, key: str) -> str:
        out = self._run("config", "--get", key).stdout.strip()
        return out.split("=", 1)[-1] if "=" in out else out

    def add(self, url: str, timeout: int = 300) -> float:
        t0 = time.time()
        self._run("add", url, timeout=timeout)
        return time.time() - t0

    def snapshots(self) -> list[str]:
        return sorted(glob.glob(str(self.data / "archive" / "*")))


def analyse_snapshot(snap: str) -> dict:
    """Per-extractor status (from index.json) + token capture + sizes."""
    idx = json.load(open(os.path.join(snap, "index.json")))
    url = idx.get("base_url") or idx.get("url", "")
    hist = idx.get("history", {})

    def status(name: str) -> str:
        runs = hist.get(name) or []
        return runs[-1].get("status") if runs else "not-run"

    # wget: whole mirror + warc
    wget_dirs = glob.glob(os.path.join(snap, "*+*"))
    wget_files = [p for d in wget_dirs
                  for p in glob.glob(os.path.join(d, "**", "*"), recursive=True)
                  if os.path.isfile(p)]
    wget_bytes = b"".join(_rb(p) for p in wget_files)
    wget_size = sum(os.path.getsize(p) for p in wget_files)
    warcs = glob.glob(os.path.join(snap, "warc", "*.warc.gz"))
    warc_raw = b"".join(gzip.decompress(_rb(w)) for w in warcs)
    warc_size = sum(os.path.getsize(w) for w in warcs)

    pdf_path = os.path.join(snap, "output.pdf")
    pdf_txt, pdf_method = _pdf_text(pdf_path)
    shot = os.path.join(snap, "screenshot.png")

    def sz(rel: str) -> int:
        p = os.path.join(snap, rel)
        return os.path.getsize(p) if os.path.exists(p) else 0

    outputs = {
        "wget": {
            "status": status("wget"),
            "tokens": _grep_tokens(wget_bytes + warc_raw),
            "bytes": wget_size + warc_size,
            "kind": "byte-mirror",
        },
        "singlefile": {
            "status": status("singlefile"),
            "tokens": _grep_tokens(_rb(os.path.join(snap, "singlefile.html"))),
            "bytes": sz("singlefile.html"),
            "kind": "rendered-html",
        },
        "dom": {
            "status": status("dom"),
            "tokens": _grep_tokens(_rb(os.path.join(snap, "output.html"))),
            "bytes": sz("output.html"),
            "kind": "rendered-html",
        },
        "readability": {
            "status": status("readability"),
            "tokens": _grep_tokens(_rb(os.path.join(snap, "readability", "content.txt"))),
            "bytes": sz("readability/content.txt"),
            "kind": "article-text",
        },
        "mercury": {
            "status": status("mercury"),
            "tokens": _grep_tokens(_rb(os.path.join(snap, "mercury", "content.txt"))),
            "bytes": sz("mercury/content.txt"),
            "kind": "article-text",
        },
        "htmltotext": {
            "status": status("htmltotext"),
            "tokens": _grep_tokens(_rb(os.path.join(snap, "htmltotext.txt"))),
            "bytes": sz("htmltotext.txt"),
            "kind": "page-text",
        },
        "pdf": {
            "status": status("pdf"),
            "tokens": _grep_tokens(pdf_txt.encode()),
            "text_method": pdf_method,
            "bytes": sz("output.pdf"),
            "kind": "visual+textlayer",
        },
        "screenshot": {
            "status": status("screenshot"),
            "tokens": {k: False for k in TOKENS},  # pixels; not text-greppable
            "note": "binary image; visual-only, OCR out of scope",
            "bytes": sz("screenshot.png"),
            "kind": "visual-pixels",
        },
    }
    return {"url": url, "snapshot": snap, "outputs": outputs}


FULL_ON = dict(
    SAVE_TITLE=True, SAVE_FAVICON=True, SAVE_HEADERS=True, SAVE_WGET=True,
    SAVE_SINGLEFILE=True, SAVE_DOM=True, SAVE_PDF=True, SAVE_SCREENSHOT=True,
    SAVE_READABILITY=True, SAVE_MERCURY=True, SAVE_HTMLTOTEXT=True,
    SAVE_GIT=False, SAVE_MEDIA=False, SAVE_ARCHIVE_DOTORG=False,
    CHROME_SANDBOX=False,
)
NOCHROME = dict(FULL_ON, SAVE_SINGLEFILE=False, SAVE_DOM=False,
                SAVE_PDF=False, SAVE_SCREENSHOT=False)


def run_full(srv, repeat: int) -> dict:
    port = srv.base_url.split(":")[-1]
    box = Box(DATA_ROOT / "full")
    box.init()
    box.config(**FULL_ON)
    result = {"config": "FULL", "image": IMG, "pages": {}, "stability": {}}
    for page in ("static", "dynamic"):
        url = f"http://host.docker.internal:{port}/{page}"
        F.reset_hits()
        elapsed = box.add(url)
        hits = F.snapshot_hits()
        snap = [s for s in box.snapshots() if page in json.load(open(os.path.join(s, "index.json"))).get("base_url", "")][-1]
        result["pages"][page] = {
            "analysis": analyse_snapshot(snap),
            "server_hits": hits,
            "elapsed_s_observational": round(elapsed, 2),
        }
    # stability: re-add /dynamic `repeat` times into fresh dirs, compare token matrix
    dyn_matrices = []
    for i in range(max(0, repeat)):
        b = Box(DATA_ROOT / f"full_rep{i}")
        b.init()
        b.config(**FULL_ON)
        b.add(f"http://host.docker.internal:{port}/dynamic")
        snap = b.snapshots()[-1]
        a = analyse_snapshot(snap)
        dyn_matrices.append({k: v["tokens"] for k, v in a["outputs"].items()})
        shutil.rmtree(b.data, ignore_errors=True)
    base = {k: v["tokens"] for k, v in result["pages"]["dynamic"]["analysis"]["outputs"].items()}
    result["stability"] = {
        "runs": repeat,
        "token_matrix_identical_across_runs": all(m == base for m in dyn_matrices),
        "repeat_matrices": dyn_matrices,
    }
    return result


def run_nochrome(srv) -> dict:
    port = srv.base_url.split(":")[-1]
    box = Box(DATA_ROOT / "nochrome")
    box.init()
    box.config(**NOCHROME)
    F.reset_hits()
    box.add(f"http://host.docker.internal:{port}/dynamic")
    hits = F.snapshot_hits()
    snap = box.snapshots()[-1]
    return {"config": "NOCHROME", "server_hits": hits,
            "analysis": analyse_snapshot(snap)}


def run_mercury_isolation(srv) -> dict:
    """Attribute server fetches: mercury-only vs wget-only on /dynamic."""
    port = srv.base_url.split(":")[-1]
    url = f"http://host.docker.internal:{port}/dynamic"
    out = {}
    only = dict.fromkeys(FULL_ON, False)
    only["CHROME_SANDBOX"] = False

    for label, extra in (("wget_only", {"SAVE_WGET": True}),
                         ("mercury_only", {"SAVE_MERCURY": True}),
                         ("readability_only", {"SAVE_READABILITY": True, "SAVE_WGET": True})):
        cfg = dict(only, **extra)
        box = Box(DATA_ROOT / f"iso_{label}")
        box.init()
        box.config(**cfg)
        F.reset_hits()
        box.add(url)
        out[label] = F.snapshot_hits()
        shutil.rmtree(box.data, ignore_errors=True)
    return {"config": "MERCURY_ISOLATION",
            "dynamic_page_fetches_by_config": out,
            "interpretation": "server-side hit count on /dynamic per single-extractor config"}


def run_robustness(srv) -> dict:
    """Archive the intentional HTTP 500 route: does ArchiveBox record failure
    cleanly (snapshot created, extractors marked failed) without aborting?"""
    port = srv.base_url.split(":")[-1]
    box = Box(DATA_ROOT / "robust")
    box.init()
    box.config(**FULL_ON)
    t0 = time.time()
    proc = box._run("add", f"http://host.docker.internal:{port}/failure/500", timeout=300)
    elapsed = time.time() - t0
    snaps = box.snapshots()
    statuses = {}
    if snaps:
        idx = json.load(open(os.path.join(snaps[-1], "index.json")))
        for k, runs in (idx.get("history") or {}).items():
            statuses[k] = runs[-1].get("status") if runs else "not-run"
    return {"config": "ROBUSTNESS_500",
            "add_returncode": proc.returncode,
            "clean_exit": proc.returncode == 0,
            "snapshot_created": bool(snaps),
            "extractor_statuses": statuses,
            "elapsed_s_observational": round(elapsed, 2)}


def dump_defaults() -> dict:
    """Report which SAVE_* extractors are ON by default (no overrides)."""
    box = Box(DATA_ROOT / "defaults")
    box.init()
    keys = ["SAVE_TITLE", "SAVE_FAVICON", "SAVE_HEADERS", "SAVE_WGET",
            "SAVE_SINGLEFILE", "SAVE_DOM", "SAVE_PDF", "SAVE_SCREENSHOT",
            "SAVE_READABILITY", "SAVE_MERCURY", "SAVE_HTMLTOTEXT",
            "SAVE_GIT", "SAVE_MEDIA", "SAVE_ARCHIVE_DOTORG"]
    defaults = {k: box.get_config(k) for k in keys}
    shutil.rmtree(box.data, ignore_errors=True)
    return {"image": IMG, "defaults": defaults}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=2, help="stability re-runs of /dynamic")
    ap.add_argument("--skip", nargs="*", default=[], help="phases to skip")
    args = ap.parse_args()

    srv = F.start_fixture_server()
    print(f"fixture at {srv.base_url}")
    try:
        if "defaults" not in args.skip:
            print("[defaults] extractor default-on/off ...")
            _write("defaults.json", dump_defaults())
        if "full" not in args.skip:
            print("[full] static + dynamic matrix ...")
            _write("full-matrix.json", run_full(srv, args.repeat))
        if "nochrome" not in args.skip:
            print("[nochrome] inheritance test ...")
            _write("nochrome.json", run_nochrome(srv))
        if "mercury" not in args.skip:
            print("[mercury] fetch attribution ...")
            _write("mercury-isolation.json", run_mercury_isolation(srv))
        if "robust" not in args.skip:
            print("[robust] 500-page handling ...")
            _write("robustness.json", run_robustness(srv))
    finally:
        srv.stop()
    print("done.")


if __name__ == "__main__":
    main()
