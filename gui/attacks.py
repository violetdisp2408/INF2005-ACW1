"""Attack Tests: damages copies of a protected file and verifies each one."""

import json
import os
import shutil
from datetime import datetime

import numpy as np

from src.crypto_engine import generate_key_pair

from . import attack_views as V
from . import media as M
from .keys import fingerprint
from .verify import NOT_FOUND, verify


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
        M.save_units(media, units, out_path)
    elif key == "lsb":
        units = media.units.copy()
        unit = int(np.flatnonzero(~mask)[0])
        units[unit] ^= np.uint8(1)
        M.save_units(media, units, out_path)
        what = f"flipped the lowest bit of unit {unit} (outside the note)"
    elif key == "sigbit":
        units = media.units.copy()
        _flip_package_bit(units, first_unit, nbits, r["package_len"] - 100)
        M.save_units(media, units, out_path)
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
        M.save_units(media, units, out_path)
        what = "flipped a bit in 3 bytes at the start of the note's text"
    elif key == "plain":
        cover = M.load(os.path.join(job_dir, r["cover_file"]), allow_lossy=True)
        M.save_units(cover, cover.units, out_path)
        what = "verified a lossless copy of the original, unprotected file"

    result = verify(out_path, key_used, nbits, start)
    row = {"key": key, "name": name, "plain": plain, "expected": expected, "actual": result["verdict"],
           "ok": result["verdict"] == expected, "what": what, "file": os.path.relpath(out_path, job_dir)}
    row["show"] = _show(key, media, out_path, r, nbits, start, key_used, public_key, result, work)
    return row


def _show(key, protected, out_path, r, nbits, start, key_used, public_key, result, work) -> dict:
    """Details for the "See what happened" panel."""
    attacked = M.load(out_path, allow_lossy=True)
    first = r["start"] * protected.units_per_step
    package = V.read_bits(protected.units, first, r["nbits"], 4 + 8)[4:]
    json_len = int.from_bytes(package[:4], "big")
    return {
        "why": V.WHY[key],
        "settings": V.settings(r, nbits, start, fingerprint(key_used), fingerprint(public_key), protected.step_name),
        "changes": V.changes(key, protected, attacked, r, json_len, work),
        "peek": V.peek(attacked, start, nbits),
        "steps": result["steps"],
        "explanation": result["explanation"],
        "download": os.path.basename(out_path),
    }


def run_all(job_dir: str, public_key, evidence_dir: str) -> dict:
    with open(os.path.join(job_dir, "receipt.json")) as f:
        r = json.load(f)
    stego_path = os.path.join(job_dir, r["stego_file"])
    baseline = verify(stego_path, public_key, r["nbits"], r["start"])
    base_peek = V.peek(M.load(stego_path), r["start"], r["nbits"])
    rows = [run_one(k, job_dir, r, public_key) for k, *_ in ATTACKS]
    report = {
        "when": datetime.now().isoformat(timespec="seconds"),
        "media_id": r["media_id"], "kind": r["kind"], "nbits": r["nbits"], "start": r["start"],
        "baseline": baseline["verdict"], "rows": rows, "passed": sum(x["ok"] for x in rows),
        "baseline_steps": baseline["steps"], "baseline_peek": base_peek,
        "key_id": fingerprint(public_key), "package_len": r["package_len"],
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
        f.write("\n## What happened in each attack\n")
        for x in rows:
            sh = x["show"]
            f.write(f"\n### {x['name']}: {x['actual']}\n\n{x['what'][:1].upper()}{x['what'][1:]}.\n\n")
            wrong = [f"{s['what']} {s['used']} (right: {s['right']})" for s in sh["settings"] if s["wrong"]]
            f.write(f"- Settings used: {'; '.join(wrong) if wrong else 'the right key, LSB count and start'}\n")
            ch = sh["changes"]
            if ch and ch["count"]:
                f.write(f"- Values changed in the file: {ch['count']:,} ({ch['in_note']:,} inside the note, "
                        f"{ch['outside']:,} outside)\n")
                for c in ch["rows"][:3]:
                    f.write(f"  - {c['where']} ({c['part']}): {c['before_bits']} → {c['after_bits']}\n")
            else:
                f.write("- File contents: unchanged\n")
            pk = sh["peek"]
            f.write(f"- Length read from the first 32 bits: {pk['length']:,} bytes "
                    f"({'fits' if pk['fits'] else 'impossible, bigger than the space'})\n" if pk["length"] is not None else "")
            for st in sh["steps"]:
                f.write(f"- {st['title']}: {st['status']}{': ' + st['detail'] if st['detail'] else ''}\n")
            f.write(f"- Why: {sh['why']}\n")
    report["evidence"] = os.path.basename(base) + ".md"
    return report
