#!/usr/bin/env python3
"""run_tika.py — the extraction arm. Drives the Apache Tika CLI fat jar (tika-app) over
every fixture and dumps ONLY raw observations (extracted text, the metadata dict, the
detected content type, exit codes, timings). NO recall/accuracy is computed here — the
anti-hardcoding split means metrics.py owns every derived number (gate 3).

Tika invocations used (all offline, local fixtures):
  --text <file>        flattened plain-text extraction  (H2 content recall)
  --json <file>        metadata as a JSON dict           (H3 metadata behavior)
  --detect <file>      content-type detection WITH filename glob   (H1)
  cat <file> | --detect content-type detection from a filename-less stream (magic only, H1)

The jar is located via env TIKA_JAR (default vendor/tika-app-<v>.jar); java via JAVA_HOME
or PATH. The jar is NOT committed (see .gitignore + metadata-snapshot.md for the download
link) — reproduce by dropping it in vendor/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX = HERE / "fixtures"
RAW = PROJECT / "artifacts" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

HOME = str(Path.home())
TMP = (os.environ.get("TMPDIR", "") or "").rstrip("/")


def redact(o):
    if isinstance(o, str):
        s = o.replace(HOME, "~")
        if TMP:
            s = s.replace(TMP, "<TMP>")
        s = s.replace("/private/var/folders", "<TMP>").replace("/var/folders", "<TMP>")
        return s
    if isinstance(o, list):
        return [redact(x) for x in o]
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items()}
    return o


def _default_jar() -> str:
    cand = sorted((PROJECT / "vendor").glob("tika-app-*.jar"))
    return str(cand[-1]) if cand else str(PROJECT / "vendor" / "tika-app.jar")


JAR = os.environ.get("TIKA_JAR", _default_jar())
JAVA = os.environ.get("JAVA", "java")


def tika(args: list[str], stdin_path: Path | None = None) -> tuple[int, str, str, float]:
    """Run `java -jar tika <args>`. If stdin_path is given, feed that file on stdin and pass
    NO filename argument (so detection is content/magic only)."""
    cmd = [JAVA, "-jar", JAR] + args
    t0 = time.perf_counter()
    if stdin_path is not None:
        with open(stdin_path, "rb") as fh:
            p = subprocess.run(cmd, stdin=fh, capture_output=True)
    else:
        p = subprocess.run(cmd, capture_output=True)
    dt = (time.perf_counter() - t0) * 1000
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), dt


def get_text(path: Path) -> tuple[str, int]:
    rc, out, _, _ = tika(["--text", str(path)])
    return out, rc


def get_metadata(path: Path) -> tuple[dict, int]:
    rc, out, _, _ = tika(["--json", str(path)])
    try:
        return json.loads(out), rc
    except Exception:
        return {"_parse_error": True, "_raw": out[:500]}, rc


def detect_with_filename(path: Path) -> tuple[str, int]:
    rc, out, _, _ = tika(["--detect", str(path)])
    return out.strip(), rc


def detect_from_stream(path: Path) -> tuple[str, int]:
    rc, out, _, _ = tika(["--detect"], stdin_path=path)
    return out.strip(), rc


def versions() -> dict:
    rc, out, _, _ = tika(["--version"])
    jv = subprocess.run([JAVA, "-version"], capture_output=True)
    java_line = (jv.stderr.decode("utf-8", "replace").splitlines() or [""])[0]
    return {"tika": out.strip(), "java": java_line.strip(), "python": sys.version.split()[0],
            "jar": Path(JAR).name}


def run_content() -> dict:
    gt = json.loads((FIX / "ground_truth.json").read_text(encoding="utf-8"))
    out = {}
    for name, spec in gt.items():
        rec = {}
        for fmt in spec["formats"]:
            path = FIX / f"{name}.{fmt}"
            if not path.exists():
                rec[fmt] = {"error": "fixture-missing"}
                continue
            text, rc_t = get_text(path)
            meta, rc_m = get_metadata(path)
            # determinism: 3 reps of --text, compare exact bytes
            reps = [get_text(path)[0] for _ in range(3)]
            rec[fmt] = {
                "text": text,
                "text_exit": rc_t,
                "metadata": meta,
                "metadata_exit": rc_m,
                "determinism_text_identical": all(r == reps[0] for r in reps),
            }
        out[name] = rec
    return out


def run_mime() -> dict:
    mt = json.loads((FIX / "mime_truth.json").read_text(encoding="utf-8"))
    mdir = FIX / "mime"
    out = {"entries": []}
    for e in mt["entries"]:
        row = {"tag": e["tag"], "true_media_type": e["true_media_type"],
               "has_magic": e["has_magic"], "lying_ext_is": e["lying_ext_is"], "detect": {}}
        for cond, fname in e["variants"].items():
            path = mdir / fname
            with_fn, rc1 = detect_with_filename(path)
            stream, rc2 = detect_from_stream(path)
            row["detect"][cond] = {
                "with_filename": with_fn, "with_filename_exit": rc1,
                "from_stream": stream, "from_stream_exit": rc2,
            }
        out["entries"].append(row)
    return out


def _exception_line(stderr: str) -> str | None:
    for ln in stderr.splitlines():
        s = ln.strip()
        if s.startswith("Exception in thread") or "Exception:" in s or s.startswith("FATAL"):
            return s
    return None


def run_robustness() -> dict:
    rt = json.loads((FIX / "robustness_truth.json").read_text(encoding="utf-8"))
    rdir = FIX / "robust"
    out = {"entries": []}
    for e in rt["entries"]:
        path = rdir / e["name"]
        rc_t, text, err_t, _ = tika(["--text", str(path)])
        meta, rc_m = get_metadata(path)
        det_fn, rc_d1 = detect_with_filename(path)
        det_st, rc_d2 = detect_from_stream(path)
        out["entries"].append({
            "name": e["name"], "case": e["case"], "spec": e,
            "text": text, "text_exit": rc_t,
            "text_exception": _exception_line(err_t),
            "metadata": meta, "metadata_exit": rc_m,
            "detect_with_filename": det_fn, "detect_with_filename_exit": rc_d1,
            "detect_from_stream": det_st, "detect_from_stream_exit": rc_d2,
            "detected_content_type_meta": meta.get("Content-Type") if isinstance(meta, dict) else None,
            "detected_encoding_meta": (meta.get("Content-Encoding") or meta.get("X-TIKA:detectedEncoding"))
                                      if isinstance(meta, dict) else None,
        })
    return out


def main() -> int:
    if not Path(JAR).exists():
        print(f"ERROR: tika jar not found at {JAR}. Set TIKA_JAR or drop it in vendor/ "
              f"(see metadata-snapshot.md).", file=sys.stderr)
        return 2
    vers = versions()
    out = {
        "tool": "apache-tika",
        "versions": vers,
        "run_started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "content": run_content(),
        "mime": run_mime(),
        "robustness": run_robustness(),
    }
    out["run_completed_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    (RAW / "tika_raw.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n_carriers = sum(len(v) for v in out["content"].values())
    print(f"run_tika done: {n_carriers} carrier extractions, {len(out['mime']['entries'])} mime entries, "
          f"{len(out['robustness']['entries'])} robustness cases -> artifacts/raw/tika_raw.json")
    print(f"versions: {vers['tika']} | {vers['java']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
