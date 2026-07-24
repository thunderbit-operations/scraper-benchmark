#!/usr/bin/env python3
"""H3 — REST endpoint fidelity on controlled ground truth.

Browserless exposes rendering as stateless REST (no browser-lifecycle code on the
client). This runner checks each endpoint against the SAME fixture and pre-registered
ground-truth markers — measuring presence/absence, never guessing:

  /content     -> full HTML after render. MUST contain the RUNTIME-INJECTED marker
                  (assembled from fragments; no literal in served bytes) + the static
                  markers. This is the class a STATIC crawler (katana standard mode)
                  misses -> the cross-series data point (katana misses / playwright-mcp
                  catches / browserless /content catches with zero client code).
  /scrape      -> structured selector extraction. Query #scrape-me (a runtime-injected
                  node) and confirm the returned value == SCRAPE_TARGET_VALUE_CC.
  /screenshot  -> PNG bytes: validate PNG magic + non-trivial size.
  /pdf         -> PDF bytes: validate %PDF magic + non-trivial size.

Also: token gate (each endpoint 401 without token) and endpoint enumeration.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import bl_common as bl
from fixture_server import GT, start_fixture_server

ART = os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw",
                   "endpoints.json")


def raw_post(endpoint: str, payload: dict, with_token: bool,
             timeout: float = 60.0) -> tuple[int, bytes]:
    url = f"{bl.BASE}{endpoint}"
    if with_token:
        url += f"?token={bl.TOKEN}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def main() -> None:
    srv = start_fixture_server()
    render_url = f"http://host.docker.internal:{srv.port}/render"
    name = "bl_endpoints"
    bl.docker_run(name)
    bl.wait_ready(timeout_s=90)
    try:
        out: dict = {"hypothesis": "H3 REST endpoint fidelity on ground truth",
                     "image": bl.IMAGE, "fixture_render_url":
                     bl.redact(render_url), "endpoints": {}}

        # /content — runtime-injected + static markers
        st, body = raw_post("/content", {"url": render_url}, True)
        text = body.decode("utf-8", "replace")
        out["endpoints"]["/content"] = {
            "status": st,
            "has_runtime_injected": GT["runtime_injected_marker"] in text,
            "has_static_heading": GT["static_heading"] in text,
            "has_static_paragraph": GT["static_paragraph"] in text,
            "bytes": len(body),
        }

        # /scrape — selector extraction of a runtime-injected node
        st, body = raw_post("/scrape",
                            {"url": render_url,
                             "elements": [{"selector": "#scrape-me"}]}, True)
        scraped_text = body.decode("utf-8", "replace")
        out["endpoints"]["/scrape"] = {
            "status": st,
            "returned_scrape_target": GT["scrape_target_text"] in scraped_text,
            "bytes": len(body),
            "sample": bl.redact(scraped_text[:400]),
        }

        # /screenshot — PNG validity
        st, body = raw_post("/screenshot", {"url": render_url}, True)
        out["endpoints"]["/screenshot"] = {
            "status": st,
            "png_magic": body[:8] == b"\x89PNG\r\n\x1a\n",
            "bytes": len(body),
        }

        # /pdf — PDF validity
        st, body = raw_post("/pdf", {"url": render_url}, True)
        out["endpoints"]["/pdf"] = {
            "status": st,
            "pdf_magic": body[:5] == b"%PDF-",
            "bytes": len(body),
        }

        # token gate: each endpoint 401 without token
        gate = {}
        for ep, pl in [("/content", {"url": render_url}),
                       ("/screenshot", {"url": render_url}),
                       ("/pdf", {"url": render_url}),
                       ("/scrape", {"url": render_url,
                                    "elements": [{"selector": "#scrape-me"}]})]:
            st_no, _ = raw_post(ep, pl, with_token=False, timeout=15)
            gate[ep] = {"no_token_status": st_no, "gated": st_no in (401, 403)}
        out["token_gate"] = gate

        # observability endpoints present
        obs = {}
        for path in ["/pressure", "/config", "/sessions"]:
            try:
                bl.get_json(path, timeout=8)
                obs[path] = "200"
            except Exception as e:
                obs[path] = f"err:{type(e).__name__}"
        out["observability_endpoints"] = obs

        bl.write_artifact(ART, out)
        c = out["endpoints"]
        print(f"/content runtime-injected: {c['/content']['has_runtime_injected']}  "
              f"({c['/content']['bytes']} B)")
        print(f"/scrape target returned: {c['/scrape']['returned_scrape_target']}")
        print(f"/screenshot PNG: {c['/screenshot']['png_magic']} "
              f"({c['/screenshot']['bytes']} B)")
        print(f"/pdf valid: {c['/pdf']['pdf_magic']} ({c['/pdf']['bytes']} B)")
        print(f"token gate: {[ (k,v['gated']) for k,v in out['token_gate'].items()]}")
    finally:
        bl.docker_stop(name)
        srv.stop()


if __name__ == "__main__":
    main()
