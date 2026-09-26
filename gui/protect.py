"""Protect: builds, signs and hides the payload with the team's functions."""

import json
import os
import zipfile
from datetime import datetime, timezone

from src.audio_stego import embed_payload_in_audio
from src.crypto_engine import create_payload_dict, sign_payload
from src.image_stego import embed_payload_in_image

from . import media as M


def protect(cover_upload: str, job_dir: str, media_id: str, text: str, nbits: int, start: int,
            private_key) -> dict:
    """Protects a file and saves a receipt."""
    if not 1 <= nbits <= 8:
        raise ValueError("Number of LSBs must be between 1 and 8.")
    if start < 0:
        raise ValueError("The start position can't be negative.")
    media_id = (media_id or "").strip() or "MEDIA_001"
    os.makedirs(job_dir, exist_ok=True)

    cover_path, notes = M.prepare_cover(cover_upload, job_dir)
    kind = M.kind_of(cover_path)

    payload = create_payload_dict(media_id=media_id, file_path=cover_path, custom_metadata=text)
    package = sign_payload(payload, private_key)

    stego_path = os.path.join(job_dir, "protected.png" if kind == "image" else "protected.wav")
    embed = embed_payload_in_image if kind == "image" else embed_payload_in_audio
    embed(cover_path, package, stego_path, nbits, start)

    stego = M.load(stego_path)
    receipt = {
        "media_id": media_id,
        "kind": kind,
        "describe": stego.describe(),
        "nbits": nbits,
        "start": start,
        "start_unit": stego.step_name,
        "package_len": len(package),
        "signature_len": private_key.key_size // 8,
        "needed_bits": M.units_for(len(package), nbits) * nbits,
        "available_bits": (stego.unit_count - start * stego.units_per_step) * nbits,
        "file_hash": payload["file_hash"],
        "timestamp": payload["timestamp"],
        "message_chars": len(text),
        "notes": notes,
        "cover_file": os.path.basename(cover_path),
        "stego_file": os.path.basename(stego_path),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(os.path.join(job_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)
    return receipt


def bundle(job_dir: str, public_key_path: str) -> str:
    """Zips the protected file and public key for person B."""
    with open(os.path.join(job_dir, "receipt.json")) as f:
        r = json.load(f)
    zip_path = os.path.join(job_dir, "send-to-B.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(job_dir, r["stego_file"]), r["stego_file"])
        z.write(public_key_path, "public_key.pem")
        z.writestr("README.txt", (
            f"File ID: {r['media_id']}\n"
            f"To check it: open the app's Verify page, upload {r['stego_file']} and public_key.pem,\n"
            "and enter the LSB count and start position (sent to you separately, not in this email).\n"
        ))
    return zip_path
