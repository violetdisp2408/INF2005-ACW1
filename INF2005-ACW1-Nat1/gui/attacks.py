"""Attack Tests: damages copies of a protected file and verifies each one."""

import json
import os
import shutil
import wave
from datetime import datetime

import numpy as np
from PIL import Image

from src.crypto_engine import generate_key_pair

from . import media as M
from .verify import NOT_FOUND, verify


def _save_units(media: M.Media, units: np.ndarray, out_path: str) -> str:
    """Saves modified values back as a PNG or WAV."""
    if media.kind == "image":
        arr = units.reshape(media.meta["height"], media.meta["width"], 3)
        Image.fromarray(arr, mode="RGB").save(out_path, format="PNG", compress_level=1)
    else:
        with wave.open(media.path, "rb") as src:
            params = src.getparams()
        with wave.open(out_path, "wb") as dst:
            dst.setparams(params)
            dst.writeframes(units.tobytes())
    return out_path


def _flip_package_bit(units: np.ndarray, start_unit: int, nbits: int, byte_index: int) -> None:
    """Flips one bit of the hidden package."""
    bit = (4 + byte_index) * 8
    units[start_unit + bit // nbits] ^= np.uint8(1 << (nbits - 1 - bit % nbits))


def _note_mask(media: M.Media, r: dict) -> np.ndarray:
    mask = np.zeros(media.unit_count, dtype=bool)
    first = r["start"] * media.units_per_step
    mask[first:first + M.units_for(r["package_len"], r["nbits"])] = True
    return mask


def _edit_content(media: M.Media, mask: np.ndarray) -> tuple[np.ndarray, str]:
    units = media.units.copy()
    if media.kind == "image":
        w, h = media.meta["width"], media.meta["height"]
        size = max(8, min(w, h) // 8)
        grid = units.reshape(h, w, 3)
        blocked = mask.reshape(h, w, 3).any(axis=2)
        for y, x in [(h // 10, w // 10), (h - size - h // 10, w // 10), (h // 10, w - size - w // 10), (h // 2, w // 2)]:
            if not blocked[y:y + size, x:x + size].any():
                grid[y:y + size, x:x + size] = (255, 0, 255)
                return units, f"painted a {size}×{size} magenta square at ({x}, {y})"
        grid[0:size, 0:size] ^= np.uint8(0x40)
        return units, f"changed a {size}×{size} block in the corner"
    bpf = media.meta["channels"] * media.meta["sampwidth"]
    run = int(0.2 * media.meta["rate"]) * bpf
    n = units.size
    first = next((c - c % bpf for c in (n // 10, n // 2, n // 4, 3 * n // 4, 0)
                  if c + run <= n and not mask[c - c % bpf:c - c % bpf + run].any()), 0)
    units[first:first + run] ^= np.uint8(0x40)
    return units, f"distorted 0.2 s of sound starting {first // bpf / media.meta['rate']:.2f} s in"


ATTACKS = [
    ("edit", "Edit the content", "Paint over part of the picture / distort part of the sound", "Tampered"),
    ("lsb", "Invisible edit", "Change one tiny bit somewhere else in the file", "Tampered"),
    ("sigbit", "Damage the signature", "Flip one bit inside the hidden signature", "Signature Invalid"),
    ("wrongkey", "Wrong key", "Verify with someone else's public key", "Signature Invalid"),
    ("wrongstart", "Wrong start position", "Verify from a different start position", NOT_FOUND),
    ("wronglsb", "Wrong LSB count", "Verify with a different number of LSBs", NOT_FOUND),
    ("scramble", "Scramble the note", "Corrupt the first bytes of the hidden note", "Cannot Verify"),
    ("plain", "Unprotected file", "Verify the original file, which has no note", NOT_FOUND),
]


def run_one(key: str, job_dir: str, r: dict, public_key) -> dict:
    name, plain, expected = next((n, p, e) for k, n, p, e in ATTACKS if k == key)
    stego_path = os.path.join(job_dir, r["stego_file"])
    media = M.load(stego_path)
    mask = _note_mask(media, r)
    work = os.path.join(job_dir, "attacks")
    os.makedirs(work, exist_ok=True)
    ext = os.path.splitext(stego_path)[1]
    out_path = os.path.join(work, f"{key}{ext}")
    key_used, nbits, start = public_key, r["nbits"], r["start"]
    first_unit = start * media.units_per_step

    if key == "edit":
        units, what = _edit_content(media, mask)
        _save_units(media, units, out_path)
    elif key == "lsb":
        units = media.units.copy()
        unit = int(np.flatnonzero(~mask)[0])
        units[unit] ^= np.uint8(1)
        _save_units(media, units, out_path)
        what = f"flipped the lowest bit of unit {unit} (outside the note)"
    elif key == "sigbit":
        units = media.units.copy()
        _flip_package_bit(units, first_unit, nbits, r["package_len"] - 100)
        _save_units(media, units, out_path)
        what = "flipped one bit 100 bytes from the end of the note (inside the signature)"
    elif key == "wrongkey":
        shutil.copy(stego_path, out_path)
        key_used = generate_key_pair()[1]
        what = "verified with a freshly generated public key"
    elif key == "wrongstart":
        shutil.copy(stego_path, out_path)
        # a start well away from the real note
        note_steps = -(-M.units_for(r["package_len"], r["nbits"]) // media.units_per_step)
        later = r["start"] + note_steps + 1000
        fits = later <= M.max_start(media, r["package_len"], r["nbits"])
        start = later if fits else max(1, r["start"] - note_steps - 1000)
        what = f"verified from {media.step_name} {start:,} instead of {r['start']:,}"
    elif key == "wronglsb":
        shutil.copy(stego_path, out_path)
        nbits = r["nbits"] % 8 + 1
        what = f"verified with {nbits} LSBs instead of {r['nbits']}"
    elif key == "scramble":
        units = media.units.copy()
        for i in (4, 5, 6):  # first bytes of the JSON
            _flip_package_bit(units, first_unit, nbits, i)
        _save_units(media, units, out_path)
        what = "flipped a bit in 3 bytes at the start of the note's text"
    elif key == "plain":
        cover = M.load(os.path.join(job_dir, r["cover_file"]), allow_lossy=True)
        _save_units(cover, cover.units, out_path)
        what = "verified a lossless copy of the original, unprotected file"

    result = verify(out_path, key_used, nbits, start)
    return {"key": key, "name": name, "plain": plain, "expected": expected, "actual": result["verdict"],
            "ok": result["verdict"] == expected, "what": what, "file": os.path.relpath(out_path, job_dir)}


def run_all(job_dir: str, public_key, evidence_dir: str) -> dict:
    with open(os.path.join(job_dir, "receipt.json")) as f:
        r = json.load(f)
    baseline = verify(os.path.join(job_dir, r["stego_file"]), public_key, r["nbits"], r["start"])
    rows = [run_one(k, job_dir, r, public_key) for k, *_ in ATTACKS]
    report = {
        "when": datetime.now().isoformat(timespec="seconds"),
        "media_id": r["media_id"], "kind": r["kind"], "nbits": r["nbits"], "start": r["start"],
        "baseline": baseline["verdict"], "rows": rows, "passed": sum(x["ok"] for x in rows),
    }
    os.makedirs(evidence_dir, exist_ok=True)
    base = os.path.join(evidence_dir, f"attack-tests-{r['kind']}-{datetime.now():%Y%m%d-%H%M%S}")
    with open(base + ".json", "w") as f:
        json.dump(report, f, indent=2)
    with open(base + ".md", "w") as f:
        f.write(f"# Attack tests: {r['media_id']} ({r['kind']}, {r['nbits']} LSB, start {r['start']})\n\n")
        f.write(f"Run {report['when']}. Untouched file verifies as **{baseline['verdict']}**. "
                f"{report['passed']}/{len(rows)} attacks gave the expected verdict.\n\n")
        f.write("| Attack | What was done | Expected | Actual | OK |\n|---|---|---|---|---|\n")
        for x in rows:
            f.write(f"| {x['name']} | {x['what']} | {x['expected']} | {x['actual']} | {'✅' if x['ok'] else '❌'} |\n")
    report["evidence"] = os.path.basename(base) + ".md"
    return report
