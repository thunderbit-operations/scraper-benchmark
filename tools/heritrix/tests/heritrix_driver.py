#!/usr/bin/env python3
"""Driver for running Heritrix crawl jobs headlessly against a local fixture.

Heritrix is an engine + Jetty Web UI + REST API. The Web UI is optional: every
job-lifecycle action (create -> PUT crawler-beans.cxml -> build -> launch ->
unpause -> poll -> terminate -> teardown) is a REST call, so a crawl can be driven
end-to-end without a browser. This module wraps that lifecycle so each test runner
imports it and drives one controlled job.

Design notes carried as evidence (see metadata-snapshot.md):

* HOST PROXY: the test host runs a system HTTP proxy (macOS `scutil --proxy` shows
  HTTPProxy 127.0.0.1:6152). Heritrix's Java HTTP client routes fetches through it
  and does NOT honor the OS proxy-exceptions list for 127.0.0.1, so every fixture
  fetch came back 503 from the proxy. The engine is therefore launched with
  `-Djava.net.useSystemProxies=false` and the *_PROXY env vars stripped. This is a
  host artifact, not Heritrix behavior; it is recorded, not hidden.
* REST auth is HTTP digest over a self-signed HTTPS cert; we shell out to `curl`
  (`-k --anyauth -u admin:admin`) rather than reimplement digest+TLS in stdlib.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

ADMIN = "admin:admin"


# --------------------------------------------------------------------------- #
# Redaction: fold $HOME->~ and the OS temp dir->'<TMP>' so committed artifacts
# carry no absolute local path and a re-run reproduces the same bytes.
# --------------------------------------------------------------------------- #
def _tmp_prefixes() -> list[str]:
    prefixes = []
    for p in (os.environ.get("TMPDIR", ""), "/var/folders", "/private/var/folders", "/tmp"):
        p = p.rstrip("/")
        if p:
            prefixes.append(p)
    # Longest first so the most specific prefix wins.
    return sorted(set(prefixes), key=len, reverse=True)


def redact(obj: Any) -> Any:
    home = str(Path.home())
    if isinstance(obj, str):
        s = obj
        for pref in _tmp_prefixes():
            s = s.replace(pref, "<TMP>")
        s = s.replace(home, "~")
        return s
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# curl-based REST helpers
# --------------------------------------------------------------------------- #
def _curl(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    base = ["curl", "-s", "-k", "-u", ADMIN, "--anyauth"]
    return subprocess.run(base + args, capture_output=True, text=True, timeout=timeout)


def engine_status(base_url: str) -> dict[str, Any] | None:
    try:
        p = _curl(["-H", "Accept: application/json", f"{base_url}/engine"], timeout=15)
    except subprocess.SubprocessError:
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Engine lifecycle
# --------------------------------------------------------------------------- #
@dataclass
class Engine:
    home: Path
    base_url: str
    pid: int
    version: str
    jobs: list[str] = field(default_factory=list)


def _wait_free_port(port: int) -> None:
    # Ensure nothing is already bound so we control (and can reap) the engine.
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError as exc:  # pragma: no cover
            raise RuntimeError(f"port {port} already in use; stop the stray engine first") from exc


def start_engine(home: Path, port: int = 8443, boot_timeout: int = 60) -> Engine:
    home = Path(home).resolve()
    hbin = home / "bin" / "heritrix"
    if not hbin.exists():
        raise FileNotFoundError(f"heritrix launcher not found at {hbin}")
    hbin.chmod(0o755)

    _wait_free_port(port)

    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    env["HERITRIX_HOME"] = str(home)
    env["JAVA_OPTS"] = (
        "-Xmx256m -Djava.net.useSystemProxies=false "
        "-Dhttp.proxyHost= -Dhttps.proxyHost= "
        "-Dhttp.nonProxyHosts=localhost|127.0.0.1|127.*"
    )
    logf = home / "engine-boot.log"
    # The launcher forks the JVM and returns; we discover the real JVM pid by the
    # process that ends up LISTENing on the REST port.
    subprocess.Popen(
        [str(hbin), "-a", ADMIN, "-b", "127.0.0.1"],
        cwd=str(home), env=env,
        stdout=open(logf, "w"), stderr=subprocess.STDOUT,
    )

    base_url = f"https://localhost:{port}"
    deadline = time.time() + boot_timeout
    status = None
    while time.time() < deadline:
        status = engine_status(base_url)
        if status is not None:
            break
        time.sleep(1)
    if status is None:
        raise RuntimeError(f"engine did not come up within {boot_timeout}s (see {logf})")

    pid = _listening_pid(port)
    return Engine(home=home, base_url=base_url, pid=pid or -1,
                  version=str(status.get("heritrixVersion", "?")))


def _listening_pid(port: int) -> int | None:
    try:
        out = subprocess.run(["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out.splitlines()[0]) if out else None
    except (subprocess.SubprocessError, ValueError):
        return None


def stop_engine(eng: Engine, port: int = 8443) -> None:
    # Best-effort job teardown, then kill the JVM we launched.
    for name in list(eng.jobs):
        try:
            teardown_job(eng, name)
        except Exception:
            pass
    pid = _listening_pid(port) or eng.pid
    if pid and pid > 0:
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            return
        for _ in range(20):
            if _listening_pid(port) is None:
                break
            time.sleep(0.5)
        if _listening_pid(port) is not None:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


@contextmanager
def managed_engine(home: Path, port: int = 8443) -> Iterator[Engine]:
    eng = start_engine(home, port=port)
    try:
        yield eng
    finally:
        stop_engine(eng, port=port)


# --------------------------------------------------------------------------- #
# Baseline config + templating
# --------------------------------------------------------------------------- #
def get_baseline_cxml(eng: Engine) -> str:
    """Obtain the stock default-profile crawler-beans.cxml WITHOUT committing any
    Heritrix file: create a throwaway job, read the generated config, tear it down."""
    tmp = "_tmpl_baseline"
    _curl(["-d", f"createpath={tmp}&action=create", f"{eng.base_url}/engine"]).check_returncode
    cxml_path = eng.home / "jobs" / tmp / "crawler-beans.cxml"
    for _ in range(20):
        if cxml_path.exists():
            break
        time.sleep(0.2)
    text = cxml_path.read_text(encoding="utf-8")
    # remove the throwaway job dir
    _curl(["-d", "action=teardown", f"{eng.base_url}/engine/job/{tmp}"])
    shutil.rmtree(eng.home / "jobs" / tmp, ignore_errors=True)
    return text


def template_cxml(base: str, *, seed: str, contact: str,
                  delay_factor: float | None = 0.0,
                  min_delay_ms: int | None = 0,
                  max_delay_ms: int | None = 0,
                  extra_props: dict[str, str] | None = None,
                  warc_props: dict[str, str] | None = None) -> str:
    """Return a crawler-beans.cxml with seed, contact, politeness and (optionally)
    WARC-writer / extra property overrides applied. All substitutions are simple,
    documented string swaps against the stock profile."""
    s = base
    s = s.replace(
        "metadata.operatorContactUrl=ENTER_AN_URL_WITH_YOUR_CONTACT_INFO_HERE_FOR_WEBMASTERS_AFFECTED_BY_YOUR_CRAWL",
        f"metadata.operatorContactUrl={contact}")
    s = s.replace("# URLS HERE\nhttp://example.example/example", f"# URLS HERE\n{seed}")
    if delay_factor is not None:
        s = s.replace('<!-- <property name="delayFactor" value="5.0" /> -->',
                      f'<property name="delayFactor" value="{delay_factor}" />')
    if min_delay_ms is not None:
        s = s.replace('<!-- <property name="minDelayMs" value="3000" /> -->',
                      f'<property name="minDelayMs" value="{min_delay_ms}" />')
    if max_delay_ms is not None:
        s = s.replace('<!-- <property name="maxDelayMs" value="30000" /> -->',
                      f'<property name="maxDelayMs" value="{max_delay_ms}" />')
    if warc_props:
        for key, val in warc_props.items():
            commented = f'<!-- <property name="{key}" value="false" /> -->'
            if commented in s:
                s = s.replace(commented, f'<property name="{key}" value="{val}" />')
            else:
                # inject just after the warcWriter bean opening tag
                anchor = '<bean id="warcWriter" class="org.archive.modules.writer.WARCWriterChainProcessor">'
                s = s.replace(anchor, anchor + f'\n  <property name="{key}" value="{val}" />')
    if extra_props:
        # append as raw <prop> entries inside the longerOverrides props block
        block = "".join(f'<prop key="{k}">{v}</prop>\n    ' for k, v in extra_props.items())
        s = s.replace('<prop key="seeds.textSource.value">',
                      block + '<prop key="seeds.textSource.value">')
    return s


# --------------------------------------------------------------------------- #
# Job run
# --------------------------------------------------------------------------- #
def run_crawl(eng: Engine, name: str, cxml_text: str, poll_timeout: int = 180,
              build_wait: int = 6) -> Path:
    """Create + configure + build + launch + unpause a job; poll to FINISHED;
    return the launch directory. Raises on any lifecycle failure."""
    E = f"{eng.base_url}/engine"
    J = f"{E}/job/{name}"
    _curl(["-d", f"createpath={name}&action=create", E])
    eng.jobs.append(name)
    cxml_path = eng.home / "jobs" / name / "crawler-beans.cxml"
    for _ in range(20):
        if cxml_path.exists():
            break
        time.sleep(0.2)
    cxml_path.write_text(cxml_text, encoding="utf-8")
    # PUT validates on the server side (200 == parsed OK)
    put = _curl(["-T", str(cxml_path), f"{J}/jobdir/crawler-beans.cxml",
                 "-o", "/dev/null", "-w", "%{http_code}"])
    if put.stdout.strip() != "200":
        raise RuntimeError(f"cxml PUT rejected for {name}: http={put.stdout.strip()}")

    _curl(["-d", "action=build", J])
    time.sleep(build_wait)
    _curl(["-d", "action=launch", J])
    time.sleep(3)
    _curl(["-d", "action=unpause", J])

    deadline = time.time() + poll_timeout
    state = "?"
    while time.time() < deadline:
        time.sleep(2)
        st = engine_status(eng.base_url)  # cheap; job state is on the job endpoint though
        js = _job_json(eng, name)
        state = (js or {}).get("crawlControllerState", "?")
        if state == "FINISHED":
            break
    if state != "FINISHED":
        raise RuntimeError(f"job {name} did not FINISH within {poll_timeout}s (state={state})")
    return latest_launch_dir(eng, name)


def _job_json(eng: Engine, name: str) -> dict[str, Any] | None:
    p = _curl(["-H", "Accept: application/json", f"{eng.base_url}/engine/job/{name}"], timeout=15)
    try:
        return json.loads(p.stdout)
    except (json.JSONDecodeError, TypeError):
        return None


def job_totals(eng: Engine, name: str) -> dict[str, Any]:
    js = _job_json(eng, name) or {}
    return js.get("uriTotalsReport", {}) or {}


def latest_launch_dir(eng: Engine, name: str) -> Path:
    jd = eng.home / "jobs" / name
    launches = sorted([p for p in jd.glob("*") if p.is_dir() and p.name.isdigit()],
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if not launches:
        raise FileNotFoundError(f"no launch dir under {jd}")
    return launches[0]


def teardown_job(eng: Engine, name: str) -> None:
    J = f"{eng.base_url}/engine/job/{name}"
    _curl(["-d", "action=terminate", J])
    time.sleep(0.5)
    _curl(["-d", "action=teardown", J])
    if name in eng.jobs:
        eng.jobs.remove(name)


# --------------------------------------------------------------------------- #
# Output parsers (crawl.log + WARC)
# --------------------------------------------------------------------------- #
def parse_crawl_log(launch_dir: Path) -> list[dict[str, Any]]:
    """Parse Heritrix crawl.log rows into dicts. Fields per Heritrix docs:
    timestamp status size uri discovery-path referrer mime thread req-ts+dur digest
    source annotations."""
    rows = []
    log = launch_dir / "logs" / "crawl.log"
    if not log.exists():
        return rows
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        rows.append({
            "timestamp": parts[0],
            "status": int(parts[1]) if parts[1].lstrip("-").isdigit() else parts[1],
            "size": int(parts[2]) if parts[2].isdigit() else parts[2],
            "uri": parts[3],
            "discovery_path": parts[4],
            "referrer": parts[5],
            "mime": parts[6],
            "thread": parts[7],
            "req_ts_dur": parts[8],
            "digest": parts[9],
            "annotations": " ".join(parts[11:]) if len(parts) > 11 else "",
        })
    return rows


def read_warc_bytes(launch_dir: Path) -> bytes:
    import gzip
    data = b""
    warc_dir = launch_dir / "warcs"
    for wf in sorted(warc_dir.glob("*.warc.gz")):
        data += gzip.decompress(wf.read_bytes())
    return data


def parse_warc_records(launch_dir: Path) -> list[dict[str, Any]]:
    """Minimal WARC 1.x parser: split on 'WARC/1.0' record boundaries, capture the
    WARC header block for each record. Sufficient to count record types, target
    URIs, digests, and concurrent-to linkage for fidelity/dedup measurement."""
    raw = read_warc_bytes(launch_dir).replace(b"\r\n", b"\n")
    records = []
    for chunk in raw.split(b"WARC/1.0\n"):
        chunk = chunk.strip(b"\n")
        if not chunk:
            continue
        header_block = chunk.split(b"\n\n", 1)[0]
        hdr: dict[str, str] = {}
        for hline in header_block.split(b"\n"):
            if b":" in hline:
                k, _, v = hline.partition(b":")
                hdr[k.decode("latin-1").strip()] = v.decode("latin-1").strip()
        if "WARC-Type" not in hdr:
            continue
        # first line of the payload for response/request records (the HTTP status line)
        body = chunk.split(b"\n\n", 1)[1] if b"\n\n" in chunk else b""
        first_http_line = body.split(b"\n", 1)[0].decode("latin-1") if body else ""
        records.append({
            "type": hdr.get("WARC-Type"),
            "target_uri": hdr.get("WARC-Target-URI", ""),
            "content_type": hdr.get("Content-Type", ""),
            "payload_digest": hdr.get("WARC-Payload-Digest", ""),
            "block_digest": hdr.get("WARC-Block-Digest", ""),
            "record_id": hdr.get("WARC-Record-ID", ""),
            "concurrent_to": hdr.get("WARC-Concurrent-To", ""),
            "refers_to": hdr.get("WARC-Refers-To", ""),
            "ip": hdr.get("WARC-IP-Address", ""),
            "profile": hdr.get("WARC-Profile", ""),
            "http_first_line": first_http_line,
        })
    return records
