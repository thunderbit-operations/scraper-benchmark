#!/usr/bin/env python3
"""Shared helpers for the Browserless evidence pack.

Pure stdlib (no venv). Everything a runner needs to manage a Browserless container
lifecycle, drive its REST endpoints, and read tool-independent truth:

  * container run / wait-ready / stop with explicit env (concurrent/queued/timeout/
    preboot/token)
  * /pressure, /config, /sessions readers
  * container memory (operator-visible `docker stats`) + process/zombie enumeration
    via /proc inside the container
  * redaction: $HOME->~, $TMPDIR|/var/folders->/<TMP>, and the local TOKEN-><TOKEN>

The token used here is a LOCAL, self-assigned container password (not an external
secret), but it is redacted out of every artifact anyway so no pack file ever
contains a token-shaped literal.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

# Local, self-assigned container token. Not an external credential. Redacted from
# all artifacts (see redact()).
TOKEN = "local-bench-token"
IMAGE = "ghcr.io/browserless/chromium:latest"
PORT = 3000
BASE = f"http://127.0.0.1:{PORT}"

_HOME = os.path.expanduser("~")
_TMP = os.environ.get("TMPDIR", "").rstrip("/")


def redact(obj: Any) -> Any:
    """Recursively redact home paths, temp paths, and the local token."""
    if isinstance(obj, str):
        s = obj
        if _HOME:
            s = s.replace(_HOME, "~")
        if _TMP:
            s = s.replace(_TMP, "<TMP>")
        s = re.sub(r"/var/folders/[^\s\"']*", "<TMP>", s)
        s = s.replace(TOKEN, "<TOKEN>")
        return s
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def write_artifact(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(redact(data), f, indent=2, sort_keys=True)
    print(f"  wrote {os.path.relpath(path)}")


# --------------------------------------------------------------------------- #
# container lifecycle
# --------------------------------------------------------------------------- #
def docker_run(name: str, *, concurrent: int | None = None,
               queued: int | None = None, timeout_ms: int | None = None,
               preboot: bool = False, extra_env: dict[str, str] | None = None,
               port: int = PORT) -> list[str]:
    """Start a Browserless container detached. Returns the exact argv (for the
    metadata record; token is redacted by the caller before writing)."""
    subprocess.run(["docker", "rm", "-f", name],
                   capture_output=True, text=True)
    argv = ["docker", "run", "-d", "--name", name, "--shm-size=2g",
            "--add-host", "host.docker.internal:host-gateway",
            "-p", f"{port}:3000", "-e", f"TOKEN={TOKEN}"]
    if concurrent is not None:
        argv += ["-e", f"CONCURRENT={concurrent}"]
    if queued is not None:
        argv += ["-e", f"QUEUED={queued}"]
    if timeout_ms is not None:
        argv += ["-e", f"TIMEOUT={timeout_ms}"]
    if preboot:
        argv += ["-e", "PREBOOT=true"]
    for k, v in (extra_env or {}).items():
        argv += ["-e", f"{k}={v}"]
    argv += [IMAGE]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"docker run failed: {r.stderr.strip()}")
    return argv


def wait_ready(timeout_s: float = 60.0, port: int = PORT) -> float:
    """Poll /pressure until it answers 200. Returns seconds waited."""
    t0 = time.monotonic()
    url = f"http://127.0.0.1:{port}/pressure?token={TOKEN}"
    while time.monotonic() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return time.monotonic() - t0
        except Exception:
            time.sleep(0.05)
    raise TimeoutError(f"container not ready after {timeout_s}s")


def docker_stop(name: str) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)


# --------------------------------------------------------------------------- #
# HTTP helpers (token-authenticated)
# --------------------------------------------------------------------------- #
def get_json(path: str, timeout: float = 10.0, port: int = PORT) -> Any:
    url = f"http://127.0.0.1:{port}{path}"
    url += ("&" if "?" in url else "?") + f"token={TOKEN}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_content(url: str, endpoint: str = "/content", body_extra: dict | None = None,
                 timeout: float = 60.0, port: int = PORT) -> tuple[int, bytes, float]:
    """POST to a Browserless REST endpoint. Returns (status, body_bytes, elapsed_s).
    Status 0 on transport error / timeout."""
    api = f"http://127.0.0.1:{port}{endpoint}?token={TOKEN}"
    payload = {"url": url}
    if body_extra:
        payload.update(body_extra)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), time.monotonic() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.monotonic() - t0
    except Exception:
        return 0, b"", time.monotonic() - t0


def pressure(port: int = PORT) -> dict:
    return get_json("/pressure", port=port)["pressure"]


# --------------------------------------------------------------------------- #
# container introspection (tool-independent truth)
# --------------------------------------------------------------------------- #
def container_mem_bytes(name: str) -> int | None:
    """Operator-visible container memory via `docker stats --no-stream`. Parses the
    used side of 'MemUsage' (e.g. '123.4MiB / 2GiB') to bytes."""
    r = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name],
        capture_output=True, text=True)
    if r.returncode != 0 or "/" not in r.stdout:
        return None
    used = r.stdout.split("/")[0].strip()
    m = re.match(r"([\d.]+)\s*([KMGT]?i?B)", used)
    if not m:
        return None
    val, unit = float(m.group(1)), m.group(2)
    mult = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4,
            "kB": 1000, "MB": 1000**2, "GB": 1000**3}.get(unit, 1)
    return int(val * mult)


def container_procs(name: str) -> dict[str, Any]:
    """Enumerate processes inside the container via /proc/*/comm + /proc/*/stat
    state. Counts chrome-family procs and zombies. Tool-independent."""
    script = (
        'for d in /proc/[0-9]*; do '
        '  c=$(cat "$d/comm" 2>/dev/null); '
        '  st=$(awk "{print \\$3}" "$d/stat" 2>/dev/null); '
        '  echo "$st $c"; '
        'done')
    r = subprocess.run(["docker", "exec", name, "sh", "-c", script],
                       capture_output=True, text=True)
    chrome = 0
    zombies = 0
    comm_counts: dict[str, int] = {}
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        state, comm = parts
        comm_counts[comm] = comm_counts.get(comm, 0) + 1
        if state == "Z":
            zombies += 1
        if re.search(r"chrom|headless", comm, re.I):
            chrome += 1
    return {"chrome_procs": chrome, "zombies": zombies,
            "comm_counts": comm_counts}
