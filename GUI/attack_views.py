"""Builds the "See what happened" details for each attack on the Attack Tests page."""

import math
import os

import numpy as np
from PIL import Image, ImageDraw

from . import media as M

VIEW_W = 480
PEEK_BYTES = 48

WHY = {
    "edit": "The note and its signature weren't touched, so the note still reads and the signature still checks out. "
            "But the file's hash now differs from the one sealed inside the note, so the hash check fails.",
    "lsb": "Only one bit changed, which you can't see or hear. SHA-256 still changes completely when a single "
           "bit changes, so the hash check fails.",
    "sigbit": "The note still reads, but one bit of the signature is different. RSA-PSS verification fails if even "
              "one bit of the signature or the note is wrong, so the signature check fails.",
    "wrongkey": "Nothing in the file changed. The signature was made with A's private key, and it only checks out "
                "with A's public key. With anyone else's key, the signature check fails, which is what a forged "
                "file from an impostor would look like.",
    "wrongstart": "The first 32 bits read from the wrong place are just ordinary pixel/sample bits, so the "
                  "'length' they give is nonsense (usually bigger than the whole file). No note can be read.",
    "wronglsb": "The right place is read, but the bits are grouped the wrong way, so the 'length' and every byte "
                "after it come out scrambled. No note can be read.",
    "scramble": "The length at the start is still sensible, so something is read, but its first characters are "
                "damaged and it no longer parses as a note. Something is there, but it can't be checked.",
    "plain": "This is the original file from before protecting. Nothing was ever hidden in it, so the reader "
             "only finds ordinary bits.",
}


def read_bits(units: np.ndarray, first: int, nbits: int, n_bytes: int) -> bytes:
    """Reads n_bytes from the lowest nbits of each value, highest of those bits first (as the team's code does)."""
    need = math.ceil(n_bytes * 8 / nbits)
    vals = units[first:first + need].astype(np.uint8) & np.uint8((1 << nbits) - 1)
    bits = ((vals[:, None] >> np.arange(nbits - 1, -1, -1, dtype=np.uint8)) & 1).ravel()[: n_bytes * 8]
    bits = np.pad(bits, (0, n_bytes * 8 - bits.size))
    return np.packbits(bits).tobytes()


def _printable(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "·" for b in data)


def peek(media: M.Media, start: int, nbits: int) -> dict:
    """What a reader finds at these settings: the 32-bit length, then the first bytes."""
    first = start * media.units_per_step
    capacity = max(0, (media.unit_count - first) * nbits // 8 - 4)
    if first >= media.unit_count:
        return {"length": None, "capacity": 0, "fits": False, "text": "", "hex": ""}
    raw = read_bits(media.units, first, nbits, 4 + PEEK_BYTES)
    length = int.from_bytes(raw[:4], "big")
    body = raw[4:4 + min(PEEK_BYTES, length)] if length else b""
    return {"length": length, "capacity": capacity, "fits": 0 < length <= capacity,
            "text": _printable(body[4:]), "hex": body[:12].hex(" ")}


def _where(media: M.Media, u: int) -> str:
    if media.kind == "image":
        px = u // 3
        return f"pixel ({px % media.meta['width']}, {px // media.meta['width']}) {'RGB'[u % 3]}"
    sw, ch = media.meta["sampwidth"], media.meta["channels"]
    t = (u // (sw * ch)) / media.meta["rate"]
    part = "low byte" if u % sw == 0 else "high byte"
    return f"sample {u // (sw * ch):,} ({t:.3f} s) {part}"


def _part(u: int, first: int, nbits: int, json_len: int, in_note: bool) -> str:
    """Which part of the hidden note a changed value holds."""
    if not in_note:
        return "outside the note"
    byte = (u - first) * nbits // 8
    if byte < 4:
        return "note: length header"
    p = byte - 4
    if p < 4:
        return "note: note length"
    if p < 4 + json_len:
        return f"note: text, character {p - 4 + 1}"
    return f"note: signature, byte {p - 4 - json_len + 1} of 256"


def _image_pictures(before: M.Media, after: M.Media, changed_idx: np.ndarray, out_dir: str, key: str) -> dict:
    w, h = after.meta["width"], after.meta["height"]
    a = before.units.reshape(h, w, 3)
    b = after.units.reshape(h, w, 3)
    changed = (a != b).any(axis=2)
    scale = min(1.0, VIEW_W / w)
    view = Image.fromarray(b).resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    px = changed_idx // 3
    ys, xs = px // w, px % w
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    pad = 6
    ImageDraw.Draw(view).rectangle(
        [max(0, x0 * scale - pad), max(0, y0 * scale - pad),
         min(view.width - 1, (x1 + 1) * scale + pad), min(view.height - 1, (y1 + 1) * scale + pad)],
        outline=(230, 40, 40), width=3)
    view.save(os.path.join(out_dir, f"{key}-view.png"))

    # before | after | changed, magnified where the change starts
    cw, ch = min(w, 40), min(h, 24)
    fx, fy = int(px[0] % w), int(px[0] // w)  # first changed pixel
    cx0 = min(max(0, fx - 6), w - cw)
    cy0 = min(max(0, fy - 6), h - ch)
    crop_a, crop_b = a[cy0:cy0 + ch, cx0:cx0 + cw], b[cy0:cy0 + ch, cx0:cx0 + cw]
    diff = np.zeros_like(crop_a)
    diff[changed[cy0:cy0 + ch, cx0:cx0 + cw]] = (255, 70, 70)
    z = 6
    strip = Image.new("RGB", (cw * z * 3 + 16, ch * z), (128, 128, 128))
    for i, arr in enumerate((crop_a, crop_b, diff)):
        strip.paste(Image.fromarray(arr).resize((cw * z, ch * z), Image.NEAREST), (i * (cw * z + 8), 0))
    strip.save(os.path.join(out_dir, f"{key}-zoom.png"))
    return {"view": f"{key}-view.png", "zoom": f"{key}-zoom.png", "zoom_at": [cx0, cy0],
            "box": [x0, y0, x1, y1]}


def _audio_picture(before: M.Media, after: M.Media, changed_idx: np.ndarray, out_dir: str, key: str) -> dict:
    ch, sw = after.meta["channels"], after.meta["sampwidth"]
    a = np.frombuffer(before.units.tobytes(), dtype="<i2")[::ch].astype(np.float32) / 32768
    b = np.frombuffer(after.units.tobytes(), dtype="<i2")[::ch].astype(np.float32) / 32768
    s0, s1 = int(changed_idx.min()) // (sw * ch), int(changed_idx.max()) // (sw * ch)
    span = max(400, int((s1 - s0 + 1) * 1.6))
    lo = max(0, (s0 + s1) // 2 - span // 2)
    hi = min(a.size, lo + span)
    W, H = 900, 220
    img = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(img)
    peak = max(1e-3, float(np.abs(np.concatenate([a[lo:hi], b[lo:hi]])).max()))
    x_of = lambda i: (i - lo) * (W - 1) / max(1, hi - lo - 1)  # noqa: E731
    y_of = lambda v: H / 2 - v / peak * (H / 2 - 8)  # noqa: E731
    d.rectangle([x_of(s0), 0, max(x_of(s0) + 2, x_of(s1)), H], fill=(255, 228, 228))
    d.line([(0, H / 2), (W, H / 2)], fill=(210, 210, 210))
    for arr, colour, width in ((a, (31, 95, 168), 3), (b, (194, 65, 12), 1)):
        if hi - lo <= W * 2:
            pts = [(x_of(i), y_of(float(arr[i]))) for i in range(lo, hi)]
            d.line(pts, fill=colour, width=width)
        else:  # min/max per pixel column
            edges = np.linspace(lo, hi, W + 1).astype(int)
            for x in range(W):
                seg = arr[edges[x]:max(edges[x] + 1, edges[x + 1])]
                d.line([(x, y_of(float(seg.max()))), (x, y_of(float(seg.min())))], fill=colour, width=1)
    img.save(os.path.join(out_dir, f"{key}-wave.png"))
    rate = after.meta["rate"]
    return {"wave": f"{key}-wave.png", "from_s": lo / rate, "to_s": hi / rate,
            "changed_from_s": s0 / rate, "changed_to_s": s1 / rate}


def changes(key: str, protected: M.Media, attacked: M.Media, r: dict, json_len: int, out_dir: str) -> dict | None:
    """What differs between the protected file and the attacked copy."""
    if protected.units.shape != attacked.units.shape:
        return None
    idx = np.flatnonzero(protected.units != attacked.units)
    if idx.size == 0:
        return {"count": 0}
    first = r["start"] * protected.units_per_step
    end = first + M.units_for(r["package_len"], r["nbits"])
    in_note = (idx >= first) & (idx < end)
    rows = []
    for u in idx[:6]:
        a, b = int(protected.units[u]), int(attacked.units[u])
        rows.append({"where": _where(protected, int(u)),
                     "part": _part(int(u), first, r["nbits"], json_len, bool(first <= u < end)),
                     "before": a, "after": b, "before_bits": f"{a:08b}", "after_bits": f"{b:08b}",
                     "flipped": f"{a ^ b:08b}"})
    pictures = (_image_pictures if protected.kind == "image" else _audio_picture)(protected, attacked, idx, out_dir, key)
    return {"count": int(idx.size), "in_note": int(in_note.sum()), "outside": int((~in_note).sum()),
            "rows": rows, "more": int(max(0, idx.size - 6)), **pictures}


def settings(r: dict, nbits: int, start: int, key_id: str, right_key_id: str, step_name: str) -> list[dict]:
    return [
        {"what": "Public key (ID)", "used": key_id, "right": right_key_id, "wrong": key_id != right_key_id},
        {"what": "LSB count", "used": nbits, "right": r["nbits"], "wrong": nbits != r["nbits"]},
        {"what": f"Start ({step_name})", "used": f"{start:,}", "right": f"{r['start']:,}", "wrong": start != r["start"]},
    ]
