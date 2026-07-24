#!/usr/bin/env python3
"""build_fixtures.py — single source of truth for the EasyOCR evidence pack.

Renders every fixture PNG with Pillow AND writes tests/fixtures/ground_truth.json in the
SAME pass, so an image and its ground-truth label can never drift. Because we RENDER the
images from strings we define, the ground truth *is* those strings — exact, not
human-annotated.

Fixture families:
  font_*         one canonical string, 7 system fonts, fixed readable size (H1 floor)
  size_*         one font, px height {8,10,12,16,20,28,40,64}          (H2 size collapse)
  contrast_*     one font/size, fg gray {0,64,110,150,180,200,220}/255 (H2 contrast floor + H3)
  rot_*          one font/size, rotation {0,5,10,15,20,30,45} deg      (H2 rotation collapse + H4)
  rot_ortho_*    orthogonal rotation {90,180,270} deg                  (H4 rotation_info)
  bg_*           colored / gradient / photo-noise backgrounds          (H2/H5 background)
  screenshot     one multi-element "app window", per-element GT bbox   (H5 per-element)

No CER is computed here. run_easyocr.py produces raw recognition; metrics.py computes all
error rates from raw text vs these labels (anti-hardcoding gate 3).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"
FIX_DIR.mkdir(parents=True, exist_ok=True)

HOME = str(Path.home())
TMP = os.environ.get("TMPDIR", "").rstrip("/")


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


# ----- canonical ground-truth strings ---------------------------------------
CANONICAL = "Sphinx of black quartz, judge my vow. 1234567890"

FONTS = {
    "arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "times": "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "courier": "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "georgia": "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "verdana": "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "comicsans": "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "impact": "/System/Library/Fonts/Supplemental/Impact.ttf",
}
BASE_FONT = FONTS["arial"]  # the sweep font (H2/H3/H4)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def render_line(
    text: str,
    font_path: str,
    size: int,
    fg=(0, 0, 0),
    bg=(255, 255, 255),
    pad: int = 16,
    angle: float = 0.0,
) -> Image.Image:
    """Render a single line, auto-sizing the canvas to the text bbox + pad. If angle!=0,
    render on a transparent layer, rotate with expand, and composite onto the bg."""
    fnt = _font(font_path, size)
    tmp = Image.new("RGB", (10, 10), bg)
    l, t, r, b = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=fnt)
    w, h = (r - l) + 2 * pad, (b - t) + 2 * pad
    if angle == 0.0:
        img = Image.new("RGB", (w, h), bg)
        ImageDraw.Draw(img).text((pad - l, pad - t), text, font=fnt, fill=fg)
        return img
    # rotated: draw on RGBA, rotate expand, paste on a bg canvas big enough
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - l, pad - t), text, font=fnt, fill=fg + (255,))
    rot = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas = Image.new("RGB", rot.size, bg)
    canvas.paste(rot, (0, 0), rot)
    return canvas


def weber(fg_gray: int, bg_gray: int = 255) -> float:
    # dark text on light bg: (L_bg - L_text) / L_bg
    return round((bg_gray - fg_gray) / bg_gray, 4)


def michelson(fg_gray: int, bg_gray: int = 255) -> float:
    return round((bg_gray - fg_gray) / (bg_gray + fg_gray), 4)


def main() -> int:
    gt = {
        "canonical_text": CANONICAL,
        "render_notes": (
            "Pillow truetype render; canvas auto-sized to text bbox + 16px pad; rotation "
            "via RGBA layer rotate(expand=True) composited on bg. GT string is exact "
            "(rendered, not annotated)."
        ),
        "single_line": {},
        "screenshot": {},
    }
    sl = gt["single_line"]

    # H1 — font floor (fixed readable size 32)
    for name, path in FONTS.items():
        if not Path(path).exists():
            continue
        fid = f"font_{name}"
        render_line(CANONICAL, path, 32).save(FIX_DIR / f"{fid}.png")
        sl[fid] = {
            "gt_text": CANONICAL,
            "kind": "font",
            "params": {"font": name, "font_size": 32, "fg_gray": 0, "bg_gray": 255},
            "image": f"fixtures/{fid}.png",
        }

    # H2 — font-size sweep (Arial)
    for px in [8, 10, 12, 16, 20, 28, 40, 64]:
        fid = f"size_{px:02d}"
        render_line(CANONICAL, BASE_FONT, px).save(FIX_DIR / f"{fid}.png")
        sl[fid] = {
            "gt_text": CANONICAL,
            "kind": "size",
            "params": {"font": "arial", "font_size": px, "fg_gray": 0, "bg_gray": 255},
            "image": f"fixtures/{fid}.png",
        }

    # H2/H3 — contrast sweep (fg gray -> white bg), fixed size 32
    for g in [0, 64, 110, 150, 180, 200, 220]:
        fid = f"contrast_{g:03d}"
        render_line(CANONICAL, BASE_FONT, 32, fg=(g, g, g)).save(FIX_DIR / f"{fid}.png")
        sl[fid] = {
            "gt_text": CANONICAL,
            "kind": "contrast",
            "params": {
                "font": "arial",
                "font_size": 32,
                "fg_gray": g,
                "bg_gray": 255,
                "weber": weber(g),
                "michelson": michelson(g),
            },
            "image": f"fixtures/{fid}.png",
        }

    # H2/H4 — small-angle rotation sweep (Arial 32, black on white)
    for a in [0, 5, 10, 15, 20, 30, 45]:
        fid = f"rot_{a:02d}"
        render_line(CANONICAL, BASE_FONT, 32, angle=float(a)).save(FIX_DIR / f"{fid}.png")
        sl[fid] = {
            "gt_text": CANONICAL,
            "kind": "rotation",
            "params": {"font": "arial", "font_size": 32, "angle_deg": a},
            "image": f"fixtures/{fid}.png",
        }

    # H4 — orthogonal rotations
    for a in [90, 180, 270]:
        fid = f"rot_ortho_{a}"
        render_line(CANONICAL, BASE_FONT, 32, angle=float(a)).save(FIX_DIR / f"{fid}.png")
        sl[fid] = {
            "gt_text": CANONICAL,
            "kind": "rotation_ortho",
            "params": {"font": "arial", "font_size": 32, "angle_deg": a},
            "image": f"fixtures/{fid}.png",
        }

    # H2/H5 — backgrounds (black text, size 32)
    # (a) solid color panel
    fid = "bg_solid"
    render_line(CANONICAL, BASE_FONT, 32, fg=(0, 0, 0), bg=(210, 224, 240)).save(
        FIX_DIR / f"{fid}.png"
    )
    sl[fid] = {
        "gt_text": CANONICAL,
        "kind": "background",
        "params": {"font": "arial", "font_size": 32, "bg_kind": "solid_color_lightblue"},
        "image": f"fixtures/{fid}.png",
    }
    # (b) vertical gradient
    fid = "bg_gradient"
    base = render_line(CANONICAL, BASE_FONT, 32)  # to get size
    w, h = base.size
    grad = Image.new("RGB", (w, h))
    for y in range(h):
        v = int(255 - (y / max(h - 1, 1)) * 110)  # 255 -> 145
        for x in range(w):
            grad.putpixel((x, y), (v, v, v))
    fnt = _font(BASE_FONT, 32)
    l, t, r, b = ImageDraw.Draw(grad).textbbox((0, 0), CANONICAL, font=fnt)
    ImageDraw.Draw(grad).text((16 - l, 16 - t), CANONICAL, font=fnt, fill=(0, 0, 0))
    grad.save(FIX_DIR / f"{fid}.png")
    sl[fid] = {
        "gt_text": CANONICAL,
        "kind": "background",
        "params": {"font": "arial", "font_size": 32, "bg_kind": "vertical_gradient_255_145"},
        "image": f"fixtures/{fid}.png",
    }
    # (c) photo-like gaussian-noise background (deterministic seed)
    fid = "bg_noise"
    rng = np.random.default_rng(20260724)
    noise = rng.normal(200, 22, (h, w, 3)).clip(0, 255).astype(np.uint8)
    nimg = Image.fromarray(noise, "RGB")
    ImageDraw.Draw(nimg).text((16 - l, 16 - t), CANONICAL, font=fnt, fill=(0, 0, 0))
    nimg.save(FIX_DIR / f"{fid}.png")
    sl[fid] = {
        "gt_text": CANONICAL,
        "kind": "background",
        "params": {"font": "arial", "font_size": 32, "bg_kind": "gaussian_noise_mu200_sd22"},
        "image": f"fixtures/{fid}.png",
    }

    # H5 — one "app screenshot" with per-element ground truth
    elements = build_screenshot()
    gt["screenshot"] = {
        "image": "fixtures/screenshot.png",
        "note": (
            "Rendered app-window mock; each element has exact GT text + pixel bbox "
            "[x0,y0,x1,y1]. metrics.py matches recognized boxes to elements by IoU."
        ),
        "elements": elements,
    }

    (FIX_DIR / "ground_truth.json").write_text(
        json.dumps(redact(gt), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    n_sl = len(sl)
    n_el = len(elements)
    print(f"built {n_sl} single-line fixtures + 1 screenshot ({n_el} elements) -> ground_truth.json")
    return 0


def _draw_el(draw, xy, text, font, fill=(0, 0, 0)):
    """Draw text at top-left xy; return exact pixel bbox [x0,y0,x1,y1]."""
    l, t, r, b = draw.textbbox(xy, text, font=font)
    draw.text(xy, text, font=font, fill=fill)
    return [int(l), int(t), int(r), int(b)]


def build_screenshot() -> list:
    """A 920x560 'dashboard' window: dark header + title, KPI labels/values, three buttons,
    a small 2x3 table, and a single-letter badge. Mixed sizes + panel colors — the issue
    #460 'screenshot text' scenario with exact per-element ground truth."""
    W, Hh = 920, 560
    img = Image.new("RGB", (W, Hh), (245, 247, 250))
    d = ImageDraw.Draw(img)
    els = []

    def add(el_id, xy, text, size, fill=(0, 0, 0), note=""):
        bbox = _draw_el(d, xy, text, _font(BASE_FONT, size), fill=fill)
        els.append(
            {"id": el_id, "gt_text": text, "bbox": bbox, "font_size": size, "note": note}
        )

    # header bar (dark) + white title
    d.rectangle([0, 0, W, 64], fill=(33, 43, 61))
    add("title", (28, 18), "Sales Dashboard", 30, fill=(255, 255, 255), note="white on dark header")
    add("badge", (860, 18), "A", 30, fill=(255, 255, 255), note="single-letter badge (issue #460)")

    # KPI panels
    d.rectangle([28, 96, 300, 216], fill=(255, 255, 255), outline=(210, 214, 220))
    add("kpi1_label", (48, 116), "Revenue", 20, fill=(110, 116, 128))
    add("kpi1_value", (48, 150), "$57,912", 34, fill=(20, 24, 32))

    d.rectangle([324, 96, 596, 216], fill=(255, 255, 255), outline=(210, 214, 220))
    add("kpi2_label", (344, 116), "Active Users", 20, fill=(110, 116, 128))
    add("kpi2_value", (344, 150), "1,284", 34, fill=(20, 24, 32))

    d.rectangle([620, 96, 892, 216], fill=(46, 132, 92), outline=(46, 132, 92))
    add("kpi3_label", (640, 116), "Status", 20, fill=(220, 240, 228))
    add("kpi3_value", (640, 150), "OK", 34, fill=(255, 255, 255), note="short token on colored panel")

    # buttons
    d.rectangle([28, 250, 150, 292], fill=(37, 99, 235))
    add("btn_save", (58, 258), "Save", 22, fill=(255, 255, 255), note="button, blue")
    d.rectangle([166, 250, 300, 292], fill=(229, 231, 235))
    add("btn_cancel", (188, 258), "Cancel", 22, fill=(31, 41, 55), note="button, gray")
    d.rectangle([316, 250, 470, 292], fill=(16, 185, 129))
    add("btn_export", (334, 258), "Export CSV", 22, fill=(255, 255, 255), note="button, green")

    # small data table (2 header + 2x3 cells)
    tx, ty = 28, 330
    add("th_q", (tx + 12, ty + 8), "Quarter", 18, fill=(90, 96, 108))
    add("th_amt", (tx + 200, ty + 8), "Amount", 18, fill=(90, 96, 108))
    rows = [("Q1", "$12,004"), ("Q2", "$18,330"), ("Q3", "$25,178")]
    for i, (q, amt) in enumerate(rows):
        yy = ty + 44 + i * 40
        add(f"cell_q{i+1}", (tx + 12, yy), q, 20, note="short cell token")
        add(f"cell_amt{i+1}", (tx + 200, yy), amt, 20)

    img.save(FIX_DIR / "screenshot.png")
    return els


if __name__ == "__main__":
    raise SystemExit(main())
