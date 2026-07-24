#!/usr/bin/env python3
"""run_easyocr.py — RAW EasyOCR recognition + timing + resource stats. NO error rate is
computed here; metrics.py computes CER/WER/recall from these raw boxes vs ground_truth.json
(anti-hardcoding gate 3).

Per single-line fixture: default readtext (detail=1 -> bbox+text+conf). For contrast
fixtures also an `adjust_contrast` variant and a pre-brightened variant (H3). For rotation
fixtures also a `rotation_info=[90,180,270]` variant (H4). The screenshot gets a default
read. Resource block: model footprint, warm latency distribution (>=15), cold-vs-warm,
detail=0/1, determinism (3 reps), and peak RSS measured in a FRESH subprocess (instrument
isolation — Part-6 #3).

All OCR is CPU (gpu=False) for a reproducible number; MPS is available on this host but
EasyOCR uses CPU on non-CUDA by default, so gpu=False is the honest CPU measurement.
"""
from __future__ import annotations

import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

import easyocr

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FIX_DIR = HERE / "fixtures"
RAW_DIR = PROJECT / "artifacts" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HOME = str(Path.home())
TMP = os.environ.get("TMPDIR", "").rstrip("/")
MODEL_DIR = Path.home() / ".EasyOCR" / "model"
CANONICAL_IMG = "font_arial"  # clean high-contrast baseline for the resource timings
WARM_SAMPLES = 20


def redact(obj):
    if isinstance(obj, str):
        s = obj.replace(HOME, "~")
        if TMP:
            s = s.replace(TMP, "<TMP>")
        return s
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def load_img(name: str) -> np.ndarray:
    return np.array(Image.open(FIX_DIR / f"{name}.png").convert("RGB"))


def read_boxes(reader, arr, **kw) -> list:
    res = reader.readtext(arr, **kw)  # detail=1 -> [(bbox, text, conf), ...]
    out = []
    for bbox, text, conf in res:
        pts = [[float(p[0]), float(p[1])] for p in bbox]
        out.append({"bbox": pts, "text": text, "conf": round(float(conf), 4)})
    return out


def timed_read(reader, arr, **kw):
    t0 = time.perf_counter()
    boxes = read_boxes(reader, arr, **kw)
    return boxes, round(time.perf_counter() - t0, 4)


# ----- fresh-process peak-RSS probe (instrument isolation) ------------------
def rss_probe_mode() -> int:
    r = easyocr.Reader(["en"], gpu=False, verbose=False)
    arr = load_img(CANONICAL_IMG)
    r.readtext(arr)
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"RSS_MAXRSS_RAW={ru}")
    return 0


def model_footprint() -> dict:
    files, total = {}, 0
    if MODEL_DIR.exists():
        for p in sorted(MODEL_DIR.glob("*.pth")):
            sz = p.stat().st_size
            files[p.name] = sz
            total += sz
    return {"model_dir": redact(str(MODEL_DIR)), "files_bytes": files, "total_bytes": total}


def main() -> int:
    if "--rss-probe" in sys.argv:
        return rss_probe_mode()

    import torch
    import torchvision
    import cv2

    gt = json.loads((FIX_DIR / "ground_truth.json").read_text(encoding="utf-8"))

    out = {
        "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": "easyocr",
        "meta": {
            "easyocr_version": easyocr.__version__,
            "torch_version": torch.__version__,
            "torchvision_version": torchvision.__version__,
            "opencv_version": cv2.__version__,
            "numpy_version": np.__version__,
            "pillow_version": Image.__version__,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "gpu": False,
            "cuda_available": bool(torch.cuda.is_available()),
            "mps_available": bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()),
            "recog_network": "standard (english_g2)",
            "detector": "CRAFT",
            "torch_num_threads": torch.get_num_threads(),
            "readtext_defaults_used": "detail=1, decoder=greedy, contrast_ths=0.1, adjust_contrast=0.5, min_size=10, text_threshold=0.7, mag_ratio=1",
        },
        "single_line": {},
        "screenshot": {},
        "resource": {},
    }

    # ---- reader init (cold model load into RAM; models already on disk) ----
    t0 = time.perf_counter()
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    out["meta"]["reader_init_s"] = round(time.perf_counter() - t0, 4)

    # ---- single-line fixtures ----
    for fid, spec in gt["single_line"].items():
        arr = load_img(fid)
        boxes, lat = timed_read(reader, arr)
        entry = {"default": {"boxes": boxes, "n_boxes": len(boxes), "latency_s": lat}}
        kind = spec["kind"]
        if kind == "contrast":
            # H3: documented adjust_contrast double-pass tuned up, + a pre-brighten control
            b2, l2 = timed_read(reader, arr, contrast_ths=0.5, adjust_contrast=1.0)
            entry["adjust_contrast_hi"] = {"boxes": b2, "n_boxes": len(b2), "latency_s": l2,
                                           "params": "contrast_ths=0.5, adjust_contrast=1.0"}
            pil = Image.open(FIX_DIR / f"{fid}.png").convert("RGB")
            bright = np.array(ImageEnhance.Contrast(pil).enhance(2.2))
            b3, l3 = timed_read(reader, bright)
            entry["prebrighten"] = {"boxes": b3, "n_boxes": len(b3), "latency_s": l3,
                                    "params": "PIL Contrast x2.2 before readtext"}
        if kind in ("rotation", "rotation_ortho"):
            # H4: documented rotation_info workaround (#168)
            b2, l2 = timed_read(reader, arr, rotation_info=[90, 180, 270])
            entry["rotation_info"] = {"boxes": b2, "n_boxes": len(b2), "latency_s": l2,
                                      "params": "rotation_info=[90,180,270]"}
        out["single_line"][fid] = entry

    # ---- screenshot ----
    sarr = load_img("screenshot")
    sboxes, slat = timed_read(reader, sarr)
    out["screenshot"] = {"default": {"boxes": sboxes, "n_boxes": len(sboxes), "latency_s": slat}}

    # ---- resource block ----
    carr = load_img(CANONICAL_IMG)
    # cold = the very first readtext after init was already spent above on the first
    # single-line fixture; measure an explicit first-call on a fresh canonical read here
    # as the warm baseline, and capture the reader_init_s (model load) as the cold cost.
    warm = []
    for _ in range(WARM_SAMPLES):
        _, l = timed_read(reader, carr)
        warm.append(l)
    # detail=0 vs detail=1 (3 reps each, keep medians in metrics)
    d1 = [timed_read(reader, carr, detail=1)[1] for _ in range(3)]
    d0 = []
    for _ in range(3):
        t0 = time.perf_counter()
        reader.readtext(carr, detail=0)
        d0.append(round(time.perf_counter() - t0, 4))
    # determinism: 3 reps of the canonical read, compare recognized text lists
    reps = []
    for _ in range(3):
        b = read_boxes(reader, carr)
        reps.append([x["text"] for x in b])
    all_identical = all(r == reps[0] for r in reps)

    # peak RSS in a fresh subprocess (isolation)
    rss_bytes = None
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / "run_easyocr.py"), "--rss-probe"],
            capture_output=True, text=True, timeout=300,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("RSS_MAXRSS_RAW="):
                raw = int(line.split("=", 1)[1])
                # macOS ru_maxrss is bytes; Linux is kilobytes
                rss_bytes = raw if sys.platform == "darwin" else raw * 1024
    except Exception as e:  # noqa: BLE001
        out["resource"]["rss_probe_error"] = redact(str(e))

    out["resource"] = {
        **out["resource"],
        "model_footprint": model_footprint(),
        "reader_init_s_cold_model_load": out["meta"]["reader_init_s"],
        "warm_latency_s_samples": warm,
        "warm_samples_n": len(warm),
        "detail1_latency_s_reps": d1,
        "detail0_latency_s_reps": d0,
        "peak_rss_bytes_fresh_process": rss_bytes,
        "determinism": {
            "canonical_image": CANONICAL_IMG,
            "text_reps": reps,
            "all_identical": all_identical,
        },
        "timing_caveat": (
            "CPU (gpu=False), torch default threads; measured under possible concurrent "
            "worker load (parallel packs). Report p50 + IQR, not a universal number."
        ),
    }
    out["run_completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    (RAW_DIR / "easyocr_raw.json").write_text(
        json.dumps(redact(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"easyocr raw done: {len(out['single_line'])} single-line + screenshot; "
        f"warm p50~{sorted(warm)[len(warm)//2]}s; det_identical={all_identical}; "
        f"model={model_footprint()['total_bytes']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
