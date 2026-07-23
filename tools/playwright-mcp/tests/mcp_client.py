#!/usr/bin/env python3
"""Minimal MCP stdio client for driving @playwright/mcp (JSON-RPC 2.0 over stdio).

The whole point is to talk to the Playwright MCP server exactly as an LLM agent
host would — spawn the process, `initialize`, enumerate tools with `tools/list`
(names are READ, never hardcoded), then `tools/call`. Tool result content is
returned verbatim so the harness can measure the snapshot's real bytes/tokens.

No third-party deps: raw subprocess + json over stdin/stdout. Line-delimited JSON
is what @playwright/mcp's stdio transport speaks.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


def _redact(obj: Any) -> Any:
    """Fold $HOME -> ~ so committed artifacts carry no absolute user path and a
    re-run reproduces the exact published bytes (katana habit)."""
    home = str(Path.home())
    if isinstance(obj, str):
        return obj.replace(home, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


class MCPClient:
    """One @playwright/mcp server subprocess spoken to over line-delimited JSON-RPC."""

    def __init__(self, npx_args: list[str], startup_timeout: float = 90.0) -> None:
        # `npx -y @playwright/mcp@latest <flags>` — stdio transport by default.
        self.cmd = ["npx", "-y", "@playwright/mcp@latest"] + npx_args
        self.proc: subprocess.Popen | None = None
        self._id = 0
        self._lock = threading.Lock()
        self.startup_timeout = startup_timeout
        self.server_info: dict[str, Any] = {}
        self.stderr_lines: list[str] = []
        self._stderr_thread: threading.Thread | None = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "MCPClient":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()
        # MCP handshake: initialize -> notifications/initialized.
        init = self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wave-d-harness", "version": "1.0"},
            },
            timeout=self.startup_timeout,
        )
        self.server_info = init.get("result", {})
        self._notify("notifications/initialized", {})

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            self.proc.stdin.close()  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    # -- transport ---------------------------------------------------------
    def _drain_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def _next_id(self) -> int:
        with self._lock:
            self._id += 1
            return self._id

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        assert self.proc is not None and self.proc.stdout is not None
        rid = self._next_id()
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        # Read line-delimited responses until we see our id (skip notifications /
        # unrelated ids). @playwright/mcp answers requests in order but we match by id.
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if line == "":
                raise RuntimeError(
                    f"server closed stdout before answering {method}; "
                    f"stderr tail: {self.stderr_lines[-5:]}"
                )
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # non-JSON log line on stdout — ignore
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(f"{method} error: {msg['error']}")
                return msg
        raise TimeoutError(f"timeout waiting for {method} (>{timeout}s)")

    # -- MCP surface -------------------------------------------------------
    def list_tools(self) -> list[dict[str, Any]]:
        resp = self._request("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None,
                  timeout: float = 60.0) -> dict[str, Any]:
        resp = self._request("tools/call",
                             {"name": name, "arguments": arguments or {}},
                             timeout=timeout)
        return resp.get("result", {})


def result_text(result: dict[str, Any]) -> str:
    """Concatenate all text content blocks of a tools/call result verbatim."""
    parts = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def result_image_bytes(result: dict[str, Any]) -> int:
    """Total decoded byte size of any image content blocks (base64 data)."""
    import base64
    total = 0
    for block in result.get("content", []):
        if block.get("type") == "image":
            data = block.get("data", "")
            try:
                total += len(base64.b64decode(data))
            except Exception:
                total += len(data)
    return total


def result_image_b64_len(result: dict[str, Any]) -> int:
    """Total base64 string length of image blocks (what actually travels to the
    model as text if image is inlined as a data payload)."""
    total = 0
    for block in result.get("content", []):
        if block.get("type") == "image":
            total += len(block.get("data", ""))
    return total
