"""Builds the before/after comparison views for the result page."""

import math
import os

import numpy as np
from PIL import Image, ImageDraw

from . import media as M

PREVIEW_W = 900


def _psnr(a: np.ndarray, b: np.ndarray) -> float | None:
    mse = float(np.mean((a.astype(np.int32) - b.astype(np.int32)) ** 2))
    return None if mse == 0 else 10 * math.log10(255 ** 2 / mse)


def _note_units(r: dict, step: int) -> tuple[int, int]:
    first = r["start"] * step
    return first, first + M.units_for(r["package_len"], r["nbits"])


def bit_rows(cover: M.Media, stego: M.Media, first: int, nbits: int, count: int = 10) -> list[dict]:
    """Returns the first values the note was written into, before and after, in binary."""
    rows = []
    for u in range(first, min(first + count, cover.unit_count)):
        a, b = int(cover.units[u]), int(stego.units[u])
        if cover.kind == "image":
            px = u // 3
            where = f"pixel ({px % cover.meta['width']}, {px // cover.meta['width']}) {'RGB'[u % 3]}"
        else:
            sw = cover.meta["sampwidth"]
            part = "low byte" if u % sw == 0 else ("high byte" if u % sw == sw - 1 else f"byte {u % sw}")
            where = f"sample {u // (sw * cover.meta['channels']):,} {part}"
        rows.append({
            "where": where,
            "before": a, "after": b,
            "before_bits": f"{a:08b}", "after_bits": f"{b:08b}",
            "keep": 8 - nbits,
            "changed": a != b,
        })
    return rows


def _summary(a: np.ndarray, b: np.ndarray, nbits: int) -> dict:
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return {
        "values_changed": int(np.count_nonzero(diff)),
        "biggest_change": int(diff.max()) if diff.size else 0,
        "max_possible": (1 << nbits) - 1,
    }


def image_views(job_dir: str, r: dict) -> dict:
    cover = M.load(os.path.join(job_dir, r["cover_file"]), allow_lossy=True)
    stego = M.load(os.path.join(job_dir, r["stego_file"]))
    w, h = cover.meta["width"], cover.meta["height"]
    a = cover.units.reshape(h, w, 3)
    b = stego.units.reshape(h, w, 3)
    changed = (a != b).any(axis=2)

    scale = min(1.0, PREVIEW_W / w)
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    for name, arr in (("preview-cover.png", a), ("preview-stego.png", b)):
        Image.fromarray(arr).resize((pw, ph), Image.LANCZOS).save(os.path.join(job_dir, name))

    # changed-pixel map
    cell = max(1, math.ceil(1 / scale))
    gh, gw = math.ceil(h / cell), math.ceil(w / cell)
    pad = np.zeros((gh * cell, gw * cell), dtype=bool)
    pad[:h, :w] = changed
    pooled = pad.reshape(gh, cell, gw, cell).any(axis=(1, 3))
    diff = Image.fromarray(np.where(pooled, 255, 0).astype(np.uint8)).convert("RGB").resize((pw, ph), Image.NEAREST)
    first, end = _note_units(r, 3)
    r0, r1 = (first // 3) // w, ((end - 1) // 3) // w
    ImageDraw.Draw(diff).rectangle([1, max(0, int(r0 * scale) - 3), pw - 2, min(ph - 1, int((r1 + 1) * scale) + 2)],
                                   outline=(77, 155, 230), width=2)
    diff.save(os.path.join(job_dir, "preview-diff.png"))

    # close-up around the start position
    sx, sy = r["start"] % w, r["start"] // w
    cw, ch = min(w, 96), min(h, 24)
    x0, y0 = min(max(0, sx - 16), w - cw), min(max(0, sy - 8), h - ch)
    crop = (a[y0:y0 + ch, x0:x0 + cw] * 0.35).astype(np.uint8)
    crop[changed[y0:y0 + ch, x0:x0 + cw]] = (255, 70, 70)
    Image.fromarray(crop).resize((cw * 6, ch * 6), Image.NEAREST).save(os.path.join(job_dir, "preview-zoom.png"))

    return {
        "bits": bit_rows(cover, stego, r["start"] * 3, r["nbits"]),
        **_summary(cover.units, stego.units, r["nbits"]),
        "changed_pixels": int(changed.sum()),
        "changed_pct": 100 * float(changed.mean()),
        "psnr": _psnr(a, b),
        "start_xy": (sx, sy),
        "zoom_origin": (x0, y0),
        "size": (w, h),
    }


def _samples(media: M.Media) -> np.ndarray:
    """Returns the first audio channel as floats."""
    s = np.frombuffer(media.units.tobytes(), dtype="<i2").astype(np.float32) / 32768
    return s[:: media.meta["channels"]]


def audio_views(job_dir: str, r: dict) -> dict:
    cover = M.load(os.path.join(job_dir, r["cover_file"]))
    stego = M.load(os.path.join(job_dir, r["stego_file"]))
    a, b = _samples(cover), _samples(stego)
    bps = cover.meta["channels"] * cover.meta["sampwidth"]
    buckets = 600
    edges = np.linspace(0, a.size, buckets + 1).astype(int)
    env = [[float(a[edges[i]:edges[i + 1]].min()), float(a[edges[i]:edges[i + 1]].max())] for i in range(buckets)]
    first, end = _note_units(r, 1)
    zs = first // bps
    zoom = slice(zs, min(a.size, zs + 160))
    noise = float(np.sum((a.astype(np.float64) - b) ** 2))
    return {
        "bits": bit_rows(cover, stego, first, r["nbits"]),
        **_summary(cover.units, stego.units, r["nbits"]),
        "envelope": env,
        "regions": [[first // bps / a.size, end // bps / a.size]],
        "zoom_start_s": zs / cover.meta["rate"],
        "zoom_cover": [round(float(x), 5) for x in a[zoom]],
        "zoom_stego": [round(float(x), 5) for x in b[zoom]],
        "changed_samples": int(np.count_nonzero(a != b)),
        "snr": None if noise == 0 else 10 * math.log10(float(np.sum(a.astype(np.float64) ** 2)) / noise),
        "seconds": cover.meta["seconds"],
    }
