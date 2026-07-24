#!/usr/bin/env python3
"""H4 -- deployment cost of a first successful Nutch local crawl, relative to a
modern single-binary crawler (katana).

Four measured facets, all computed from the run / filesystem, nothing hardcoded:

  1. JDK COMPATIBILITY MATRIX (the headline). Run the first real Hadoop job
     (`inject`) under each available JDK and record whether it runs. Nutch 1.22
     bundles Hadoop 3.4.2, whose UserGroupInformation.getCurrentUser() calls
     Subject.getSubject(), removed in JDK 24 (JEP 486). We capture the exact error
     on JDK 24+ and the success on an LTS.
  2. ON-DISK FOOTPRINT: unpacked size, bundled jar count + size, plugin count,
     conf-file count -- vs a single Go binary.
  3. CONFIG STEPS to first fetch: the shipped nutch-site.xml is empty and
     http.agent.name defaults to "" -- Nutch refuses to fetch until it is set. We
     prove the refusal, then the minimal working config.
  4. PER-PHASE WALL TIME (>=3 runs, distribution): inject/generate/fetch/parse/
     updatedb each pay a fresh-JVM + plugin-load tax; measured against the bare
     `bin/nutch` JVM-start floor.
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx
import nutch_driver as nd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "artifacts" / "raw"
LOGS = PROJECT / "artifacts" / "logs"
TIMING_RUNS = 3

# JDKs to probe. Defaults match the eval host; override via env for reproduction.
JDK_NEW = os.environ.get("JDK_NEW_HOME", "/opt/homebrew/opt/openjdk")      # 24+ (JEP 486)
JDK_LTS = os.environ.get("JDK_LTS_HOME", "/opt/homebrew/opt/openjdk@17")   # LTS that works


def java_version(java_home: str) -> str:
    try:
        p = subprocess.run([str(Path(java_home) / "bin" / "java"), "-version"],
                           capture_output=True, text=True, timeout=30)
        return (p.stderr + p.stdout).strip().splitlines()[0] if (p.stderr or p.stdout) else "unknown"
    except Exception as e:  # noqa: BLE001
        return f"error: {e!r}"


def probe_jdk(java_home: str, base_url: str, workroot: Path, tag: str,
              extra_opts: str = "") -> dict:
    """Run `bin/nutch inject` under a specific JDK and capture whether the Hadoop
    job initialises. Returns rc + a compact error signature (not the whole trace)."""
    crawldb = workroot / f"crawldb_{tag}"
    seeds = workroot / f"seeds_{tag}"
    seeds.mkdir(parents=True, exist_ok=True)
    (seeds / "urls.txt").write_text(base_url + "/\n", encoding="utf-8")
    conf = nd.make_conf(workroot / f"conf_{tag}",
                        {"http.agent.name": "nutch-eval-fixture"},
                        ["+."])
    env = dict(os.environ)
    env["NUTCH_JAVA_HOME"] = java_home
    env["JAVA_HOME"] = java_home
    env["NUTCH_CONF_DIR"] = str(conf)
    if extra_opts:
        env["NUTCH_OPTS"] = extra_opts
    cmd = [str(nd.NUTCH_HOME / "bin" / "nutch"), "inject", str(crawldb), str(seeds)]
    started = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    elapsed = round(time.monotonic() - started, 3)
    combined = (p.stdout or "") + "\n" + (p.stderr or "")
    (LOGS / f"jdk_probe_{tag}.log").write_text(combined, encoding="utf-8")
    # Extract compact signatures rather than dumping the whole trace.
    sigs = []
    for needle in ("getSubject is not supported",
                   "Enabling a Security Manager is not supported",
                   "UnsupportedOperationException",
                   "Total new urls injected"):
        if needle in combined:
            sigs.append(needle)
    injected = "Total new urls injected" in combined
    exc_line = ""
    for ln in combined.splitlines():
        if "Exception" in ln and ("getSubject" in ln or "Security Manager" in ln or "Unsupported" in ln):
            exc_line = ln.strip(); break
    return {"tag": tag, "java_home": nd.redact(java_home), "java_version": java_version(java_home),
            "extra_opts": extra_opts or None, "returncode": p.returncode,
            "elapsed_seconds": elapsed, "inject_succeeded": injected,
            "error_signatures": sigs, "first_exception_line": nd.redact(exc_line)}


def footprint() -> dict:
    home = nd.NUTCH_HOME
    def dir_bytes(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    lib = home / "lib"
    plugins = home / "plugins"
    conf = home / "conf"
    jars = list(lib.glob("*.jar")) if lib.exists() else []
    plugin_jars = list(plugins.rglob("*.jar")) if plugins.exists() else []
    hadoop_jars = [j.name for j in jars if j.name.startswith("hadoop-")]
    return {
        "unpacked_bytes": dir_bytes(home),
        "unpacked_mb": round(dir_bytes(home) / 1e6, 1),
        "lib_jar_count": len(jars),
        "lib_bytes": dir_bytes(lib) if lib.exists() else 0,
        "lib_mb": round((dir_bytes(lib) if lib.exists() else 0) / 1e6, 1),
        "bundled_hadoop_jars": sorted(hadoop_jars),
        "plugin_dir_count": len([p for p in plugins.iterdir() if p.is_dir()]) if plugins.exists() else 0,
        "plugin_jar_count": len(plugin_jars),
        "conf_file_count": len([f for f in conf.iterdir() if f.is_file()]) if conf.exists() else 0,
        "bin_scripts": sorted(p.name for p in (home / "bin").iterdir()) if (home / "bin").exists() else [],
        "comparator_note": "katana ships as a single Go binary (~50 MB, 0 external jars, "
                           "no JVM); numbers here are the JVM/Hadoop-crawler baseline",
    }


def config_steps(base_url: str, workroot: Path) -> dict:
    """Prove the out-of-the-box refusal: empty http.agent.name -> Nutch will not
    fetch. Then show the minimal working delta."""
    # (a) Empty agent name -> attempt a one-round fetch and see if anything is fetched.
    seeds = ["/"]
    empty_conf = nd.make_conf(workroot / "cfg_empty",
                              {"plugin.includes":
                               "protocol-http|urlfilter-regex|parse-(html|tika)|"
                               "scoring-opic|urlnormalizer-(pass|regex|basic)",
                               "fetcher.server.delay": "0.0"},
                              ["+."])
    fx.reset_hits()
    r_empty = nd.crawl(base_url, seeds, empty_conf, workroot / "cfg_empty", LOGS,
                       rounds=1, tag="cfg_empty", topN=100)
    empty_hits = fx.snapshot_hits()
    # look for the tell-tale refusal in the fetch log
    fetch_log = ""
    fl = LOGS / "cfg_empty_fetch_1.log"
    if fl.exists():
        txt = fl.read_text(encoding="utf-8", errors="replace")
        for ln in txt.splitlines():
            if "agent name" in ln.lower() or "http.agent.name" in ln:
                fetch_log = ln.strip(); break

    # (b) Minimal working: add http.agent.name.
    ok_conf = nd.make_conf(workroot / "cfg_ok",
                           {"http.agent.name": "nutch-eval-fixture",
                            "plugin.includes":
                            "protocol-http|urlfilter-regex|parse-(html|tika)|"
                            "scoring-opic|urlnormalizer-(pass|regex|basic)",
                            "fetcher.server.delay": "0.0"},
                           ["+."])
    fx.reset_hits()
    r_ok = nd.crawl(base_url, seeds, ok_conf, workroot / "cfg_ok", LOGS,
                    rounds=1, tag="cfg_ok", topN=100)
    ok_hits = fx.snapshot_hits()
    return {
        "empty_agent_name_fetched_home": "/" in empty_hits or "/page/a" in empty_hits,
        "empty_agent_name_hit_count": len(empty_hits),
        "empty_agent_name_refusal_log": nd.redact(fetch_log),
        "with_agent_name_fetched_home": "/" in ok_hits or "/page/a" in ok_hits,
        "with_agent_name_hit_count": len(ok_hits),
        "minimal_working_config": {
            "files_touched": ["conf/nutch-site.xml (http.agent.name + plugin.includes + scope)",
                              "conf/regex-urlfilter.txt (host scope rules)",
                              "seed url list file"],
            "mandatory_property": "http.agent.name (ships empty; fetch refused until set)",
        },
    }


def per_phase_timing(base_url: str, workroot: Path) -> dict:
    # bin/nutch with no command prints usage from the BASH script and never starts
    # the JVM -- so this measures shell dispatch only, NOT JVM+Hadoop init. The real
    # per-command JVM+plugin-load+LocalJobRunner floor is derived below as the min
    # over the trivial-work phases (inject/parse/updatedb each touch ~1 URL).
    dispatch = []
    for _ in range(TIMING_RUNS):
        env = nd._env(); env["NUTCH_CONF_DIR"] = str(nd.NUTCH_HOME / "conf")
        t0 = time.monotonic()
        subprocess.run([str(nd.NUTCH_HOME / "bin" / "nutch")], capture_output=True, text=True,
                       timeout=60, env=env)
        dispatch.append(round(time.monotonic() - t0, 3))

    conf = nd.make_conf(workroot / "cfg_timing",
                        {"http.agent.name": "nutch-eval-fixture",
                         "plugin.includes": "protocol-http|urlfilter-regex|parse-(html|tika)|"
                         "scoring-opic|urlnormalizer-(pass|regex|basic)",
                         "fetcher.server.delay": "0.0"}, ["+."])
    # Time each phase across TIMING_RUNS full 1-round crawls.
    phase_times: dict[str, list[float]] = {}
    totals = []
    for i in range(TIMING_RUNS):
        fx.reset_hits()
        res = nd.crawl(base_url, ["/"], conf, workroot / f"cfg_timing_{i}", LOGS,
                       rounds=1, tag=f"timing_{i}", topN=100)
        totals.append(res["total_crawl_seconds"])
        for p in res["phases"]:
            phase_times.setdefault(p["phase"], []).append(p["elapsed"])

    def dist(xs):
        xs = sorted(xs)
        return {"n": len(xs), "min": xs[0], "p50": xs[len(xs) // 2], "max": xs[-1]}
    per_phase = {k: dist(v) for k, v in phase_times.items()}
    # Effective per-JVM-job floor: the cheapest trivial-work phase (inject/parse/
    # updatedb do near-zero real work on 1 URL, so their time is ~all JVM+init).
    trivial = [per_phase[p]["min"] for p in ("inject", "parse", "updatedb") if p in per_phase]
    return {
        "bin_nutch_bash_dispatch_seconds": dist(dispatch),
        "bash_dispatch_note": "bare `bin/nutch` prints usage from the shell script; no JVM "
                              "starts -- this is NOT the JVM floor",
        "effective_per_job_jvm_floor_seconds": round(min(trivial), 3) if trivial else None,
        "per_phase_seconds": per_phase,
        "one_round_total_seconds": dist(totals),
        "note": "one crawl 'round' = a fresh JVM per command (generate,fetch,parse,"
                "updatedb, after an initial inject); each pays the per-job JVM+Hadoop-"
                "init floor (~effective_per_job_jvm_floor_seconds), so most of a round's "
                "wall time is process/JVM startup, not fetching",
    }


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
    if not (nd.NUTCH_HOME / "bin" / "nutch").exists():
        print(f"NUTCH_HOME invalid: {nd.NUTCH_HOME}", file=sys.stderr); return 2
    workroot = Path(nd.tempfile.mkdtemp(prefix="nutch-deploy-"))
    srv = fx.start_fixture_server()
    base = srv.base_url
    summary: dict = {"run_started_at": datetime.now(timezone.utc).isoformat(),
                     "tool": "apache-nutch", "nutch_home": nd.redact(str(nd.NUTCH_HOME)),
                     "base_url": base}
    try:
        summary["jdk_matrix"] = {
            "jdk_new_plain": probe_jdk(JDK_NEW, base, workroot, "jdk_new_plain"),
            "jdk_new_secmgr_allow": probe_jdk(JDK_NEW, base, workroot, "jdk_new_secmgr",
                                              extra_opts="-Djava.security.manager=allow"),
            "jdk_lts_plain": probe_jdk(JDK_LTS, base, workroot, "jdk_lts_plain"),
        }
        summary["footprint"] = footprint()
        summary["config_steps"] = config_steps(base, workroot)
        summary["per_phase_timing"] = per_phase_timing(base, workroot)
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        (RAW / "deployment-cost-summary.json").write_text(
            json.dumps(nd.redact(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(nd.redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        srv.stop()
        nd.shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
