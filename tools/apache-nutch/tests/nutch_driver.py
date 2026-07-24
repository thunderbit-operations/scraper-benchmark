#!/usr/bin/env python3
"""Shared driver for running Apache Nutch local-mode crawls against the fixture.

Nothing here hardcodes a result. Each helper runs a real Nutch command against a
scenario-specific NUTCH_CONF_DIR and returns what the run produced: the crawldb
URL set (from `readdb -dump`), server-side hit truth (from the fixture), and
per-phase wall time. Recall / scope / status are computed by the callers from
these outputs.

Nutch install location is taken from $NUTCH_HOME (must point at an unpacked
apache-nutch-1.x-bin). The Java runtime is taken from $NUTCH_JAVA_HOME (Nutch 1.22
+ bundled Hadoop 3.4.2 needs a JDK where Subject.getSubject still works -- i.e. an
LTS <= 21; JDK 24+ hard-fails, see run_deployment_cost.py). All absolute paths are
redacted ($HOME->~, $TMPDIR/var-folders-><TMP>) before anything is written to disk.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

NUTCH_HOME = Path(os.environ.get("NUTCH_HOME", "")).expanduser()
NUTCH_JAVA_HOME = os.environ.get("NUTCH_JAVA_HOME", os.environ.get("JAVA_HOME", ""))


def redact(obj: Any) -> Any:
    """Fold absolute local paths so committed artifacts carry no machine-specific
    prefix. $HOME->~, the OS temp root ($TMPDIR / /var/folders / /private/tmp)-><TMP>."""
    home = str(Path.home())
    tmp_roots = []
    for t in (os.environ.get("TMPDIR", ""), tempfile.gettempdir(), "/private/tmp", "/var/folders", "/tmp"):
        t = t.rstrip("/")
        if t:
            tmp_roots.append(t)
    if isinstance(obj, str):
        s = obj
        for t in sorted(set(tmp_roots), key=len, reverse=True):
            s = s.replace(t, "<TMP>")
        s = s.replace(home, "~")
        return s
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def _env() -> dict[str, str]:
    e = dict(os.environ)
    if NUTCH_JAVA_HOME:
        e["NUTCH_JAVA_HOME"] = NUTCH_JAVA_HOME
        e["JAVA_HOME"] = NUTCH_JAVA_HOME
    # Keep Nutch's own JVM heap modest and deterministic.
    e.setdefault("NUTCH_HEAPSIZE", "1000")
    return e


def make_conf(workdir: Path, props: dict[str, str], urlfilter_rules: list[str] | None = None) -> Path:
    """Copy the shipped conf/ into a scenario dir and overwrite nutch-site.xml (+
    optionally regex-urlfilter.txt). Returns the conf dir to pass as NUTCH_CONF_DIR."""
    conf = workdir / "conf"
    if conf.exists():
        shutil.rmtree(conf)
    shutil.copytree(NUTCH_HOME / "conf", conf)

    site = ['<?xml version="1.0"?>',
            '<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>',
            "<configuration>"]
    for k, v in props.items():
        site.append(f"  <property><name>{k}</name><value>{v}</value></property>")
    site.append("</configuration>\n")
    (conf / "nutch-site.xml").write_text("\n".join(site), encoding="utf-8")

    if urlfilter_rules is not None:
        # A urlfilter-regex file: rules applied top-to-bottom, first match wins;
        # trailing "+." accepts anything not already rejected.
        (conf / "regex-urlfilter.txt").write_text("\n".join(urlfilter_rules) + "\n", encoding="utf-8")
    return conf


def run_nutch(conf_dir: Path, args: list[str], log_path: Path, timeout: int = 240) -> dict[str, Any]:
    """Run one bin/nutch command. Returns rc, elapsed, and tail of combined output."""
    cmd = [str(NUTCH_HOME / "bin" / "nutch")] + args
    env = _env()
    env["NUTCH_CONF_DIR"] = str(conf_dir)
    started = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        rc, timed_out, out, err = p.returncode, False, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, timed_out, out, err = -1, True, (e.stdout or ""), (e.stderr or "")
    elapsed = round(time.monotonic() - started, 3)
    combined = (out or "") + "\n" + (err or "")
    log_path.write_text(combined, encoding="utf-8")
    return {"cmd_tail": args[0] if args else "", "rc": rc, "timed_out": timed_out,
            "elapsed": elapsed, "out": out or "", "err": err or ""}


def newest_segment(segments_dir: Path) -> str | None:
    if not segments_dir.exists():
        return None
    segs = sorted([p.name for p in segments_dir.iterdir() if p.is_dir()])
    return segs[-1] if segs else None


def crawldb_dump(conf_dir: Path, crawldb: Path, logs_dir: Path, tag: str) -> dict[str, dict[str, Any]]:
    """readdb -dump -> map of URL -> {status token, protocol code}. This is Nutch's
    own record of every URL it KNOWS about + outcome. The dump is a multi-line
    record per URL:
        http://host/path\tVersion: 7
        Status: 2 (db_fetched)
        ...
        \tnutch.protocol.code=200
    """
    dumpdir = crawldb.parent / f"dump_{tag}"
    if dumpdir.exists():
        shutil.rmtree(dumpdir)
    r = run_nutch(conf_dir, ["readdb", str(crawldb), "-dump", str(dumpdir)],
                  logs_dir / f"readdb_dump_{tag}.log")
    result: dict[str, dict[str, Any]] = {}
    if r["rc"] != 0:
        return result
    url_re = re.compile(r"^(https?://\S+)\s+Version:")
    status_re = re.compile(r"^Status:\s*\d+\s*\((\w+)\)")
    proto_re = re.compile(r"nutch\.protocol\.code=(\d+)")
    for part in dumpdir.glob("part-*"):
        cur = None
        for line in part.read_text(encoding="utf-8", errors="replace").splitlines():
            um = url_re.match(line)
            if um:
                cur = um.group(1)
                result[cur] = {"status": "unknown", "protocol_code": None}
                continue
            if cur is None:
                continue
            sm = status_re.match(line)
            if sm:
                result[cur]["status"] = sm.group(1)
                continue
            pm = proto_re.search(line)
            if pm:
                result[cur]["protocol_code"] = int(pm.group(1))
    return result


def crawl(base_url: str, seed_paths: list[str], conf_dir: Path, workdir: Path,
          logs_dir: Path, rounds: int, tag: str, topN: int = 100,
          extra_gen: list[str] | None = None) -> dict[str, Any]:
    """Full local crawl cycle: inject -> [generate,fetch,parse,updatedb] x rounds.
    Returns per-phase timings, the crawldb URL->status map, and (caller reads the
    fixture separately for) server-side hits. Segments/crawldb live under workdir,
    which is a temp dir OUTSIDE the committed pack."""
    from fixture_server import reset_hits  # local import to avoid cycle at module load

    crawldb = workdir / "crawldb"
    segments = workdir / "segments"
    seeds = workdir / "seeds"
    for d in (crawldb, segments):
        if d.exists():
            shutil.rmtree(d)
    seeds.mkdir(parents=True, exist_ok=True)
    (seeds / "urls.txt").write_text("\n".join(base_url + p for p in seed_paths) + "\n", encoding="utf-8")

    reset_hits()
    phases: list[dict[str, Any]] = []
    inj = run_nutch(conf_dir, ["inject", str(crawldb), str(seeds)], logs_dir / f"{tag}_inject.log")
    phases.append({"phase": "inject", "round": 0, "rc": inj["rc"], "elapsed": inj["elapsed"]})

    completed_rounds = 0
    for rnd in range(1, rounds + 1):
        gen = run_nutch(conf_dir,
                        ["generate", str(crawldb), str(segments), "-topN", str(topN)] + (extra_gen or []),
                        logs_dir / f"{tag}_generate_{rnd}.log")
        phases.append({"phase": "generate", "round": rnd, "rc": gen["rc"], "elapsed": gen["elapsed"]})
        # generate rc==1 means "no new segments" -> crawl frontier exhausted.
        if gen["rc"] != 0:
            phases[-1]["note"] = "no new segments (frontier exhausted)"
            break
        seg = newest_segment(segments)
        if not seg:
            phases[-1]["note"] = "generate ok but no segment dir found"
            break
        seg_path = str(segments / seg)
        for phase_name in ("fetch", "parse"):
            r = run_nutch(conf_dir, [phase_name, seg_path], logs_dir / f"{tag}_{phase_name}_{rnd}.log")
            phases.append({"phase": phase_name, "round": rnd, "rc": r["rc"], "elapsed": r["elapsed"]})
        upd = run_nutch(conf_dir, ["updatedb", str(crawldb), seg_path], logs_dir / f"{tag}_updatedb_{rnd}.log")
        phases.append({"phase": "updatedb", "round": rnd, "rc": upd["rc"], "elapsed": upd["elapsed"]})
        completed_rounds = rnd

    db = crawldb_dump(conf_dir, crawldb, logs_dir, tag)
    return {"tag": tag, "rounds_requested": rounds, "rounds_completed": completed_rounds,
            "phases": phases, "crawldb": db,
            "total_crawl_seconds": round(sum(p["elapsed"] for p in phases), 3)}


def paths_from_urls(urls: Any, base_url: str) -> list[str]:
    out = []
    for u in urls:
        if u.startswith(base_url):
            out.append(u[len(base_url):] or "/")
    return sorted(set(out))
