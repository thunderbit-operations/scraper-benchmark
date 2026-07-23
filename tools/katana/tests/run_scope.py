#!/usr/bin/env python3
"""Katana scope-discipline test with a real out-of-scope host.

Primary fixture is reached as http://127.0.0.1:<A>; a secondary fixture is reached
as http://localhost:<B> (same process, different hostname => different scope
field). The primary's /scope-seed links to http://localhost:<B>/page/out. Because
/page/out is served only by the secondary, a hit on it is proof the out-of-scope
host was actually FETCHED (server-side truth), not merely discovered.

Configs:
  default        -> default field scope (rdn): localhost is out of scope
  fs_fqdn        -> -fs fqdn: strict same-hostname scope
  cs_localhost   -> -cs 'localhost': a crawl-scope (inScope) URL regex. Per katana
                    source the DNS field-scope check runs FIRST and short-circuits,
                    so -cs can only narrow WITHIN the field scope, not add a new
                    host -> expected NOT to include the secondary. (honesty control)
  fs_custom_both -> -fs '(127.0.0.1|localhost)': a custom field-scope regex that
                    matches both hosts. The custom-regex branch of validateDNS does
                    not use the root hostname, so this is the correct way to opt a
                    second host into scope -> expected to fetch the secondary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
KATANA = os.path.expanduser("~/go/bin/katana")


def _redact(obj: Any) -> Any:
    # Fold the $HOME prefix back to ~ so committed artifacts carry no absolute
    # user path and a re-run reproduces the exact bytes we published.
    home = str(Path.home())
    if isinstance(obj, str):
        return obj.replace(home, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_cfg(seed: str, secondary_base: str, extra: list[str], label: str) -> dict[str, Any]:
    fx.reset_hits()
    cmd = [KATANA, "-u", seed, "-silent", "-nc", "-duc", "-d", "3"] + extra
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    hits = fx.snapshot_hits()
    emitted = sorted({ln.strip() for ln in p.stdout.splitlines() if ln.strip().startswith("http")})
    secondary_fetched = hits.get("/page/out", 0) > 0
    secondary_discovered = any(secondary_base in u for u in emitted)
    return {
        "label": label, "cmd_extra": extra, "returncode": p.returncode,
        "secondary_host_fetched": secondary_fetched,
        "secondary_host_discovered_in_output": secondary_discovered,
        "page_out_hits": hits.get("/page/out", 0),
        "emitted_urls": emitted,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(KATANA):
        print("katana missing", file=sys.stderr)
        return 2

    primary = fx.start_fixture_server()
    secondary = fx.start_fixture_server()
    # Reach the secondary under a DIFFERENT hostname so scope fields differ.
    secondary_base = f"http://localhost:{secondary.base_url.rsplit(':', 1)[1]}"
    os.environ["SCOPE_SECONDARY_URL"] = secondary_base
    seed = f"{primary.base_url}/scope-seed"

    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "katana",
        "primary": primary.base_url, "secondary": secondary_base, "seed": seed,
        "configs": {},
    }
    try:
        for label, extra in [("default", []), ("fs_fqdn", ["-fs", "fqdn"]),
                             ("cs_localhost", ["-cs", "localhost"]),
                             ("fs_custom_both", ["-fs", "(127.0.0.1|localhost)"])]:
            result["configs"][label] = run_cfg(seed, secondary_base, extra, label)
        # Interpretation (computed, not assumed): default/fqdn must NOT fetch the
        # secondary host; -cs alone must NOT (field-scope gates it); a custom -fs
        # regex matching both hosts MUST fetch it. This separates "scope discipline
        # holds by default" from "how you correctly widen it".
        c = result["configs"]
        result["analysis"] = {
            "default_excludes_out_of_scope_host": not c["default"]["secondary_host_fetched"],
            "fqdn_excludes_out_of_scope_host": not c["fs_fqdn"]["secondary_host_fetched"],
            "cs_regex_alone_includes_it": c["cs_localhost"]["secondary_host_fetched"],
            "custom_field_scope_includes_it": c["fs_custom_both"]["secondary_host_fetched"],
        }
        write_json(RAW_DIR / "scope-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        primary.stop()
        secondary.stop()


if __name__ == "__main__":
    raise SystemExit(main())
