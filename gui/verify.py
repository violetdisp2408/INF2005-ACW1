"""Verify: runs the team's checks in order and maps the result to a verdict."""

import json

from src.crypto_engine import compute_file_hash, unpack_payload_package, verify_media_integrity, verify_signature

from . import media as M
from . import safe_run

NOT_FOUND = "Wrong Start Location / Payload Missing"
STEPS = [
    ("read", "Read the hidden note", NOT_FOUND + " (or Cannot Verify)"),
    ("signature", "Check the signature", "Signature Invalid"),
    ("hash", "Check the file wasn't edited", "Tampered"),
]
EXPLAIN = {
    "Authentic": "All checks passed. The key holder protected this file and it hasn't changed since.",
    "Tampered": "The note is genuine, but the file's hash doesn't match the hash stored in the note.",
    "Signature Invalid": "The note wasn't signed by the owner of this public key, or the note itself was altered.",
    "Cannot Verify": "Something is hidden here, but it's damaged or unreadable, so it can't be checked.",
    NOT_FOUND: "No note could be read with these settings. Either the start position or LSB count is wrong, "
               "or the file was never protected.",
}
REQUIRED_FIELDS = {"media_id", "timestamp", "file_hash", "nonce", "metadata"}


def verify(stego_path: str, public_key, nbits: int, start: int) -> dict:
    """Verifies a file and returns the steps, verdict and payload."""
    steps = [{"key": k, "title": t, "status": "skipped", "detail": ""} for k, t, _ in STEPS]
    out = {"steps": steps, "verdict": None, "explanation": "", "payload": None, "info": {}}

    def fail(i: int, verdict: str, detail: str) -> dict:
        steps[i].update(status="fail", detail=detail)
        out["verdict"], out["explanation"] = verdict, EXPLAIN[verdict]
        return out

    def ok(i: int, detail: str) -> None:
        steps[i].update(status="pass", detail=detail)

    try:
        media = M.load(stego_path)
    except M.MediaError as exc:
        out["verdict"], out["explanation"] = "Cannot Verify", str(exc)
        return out
    out["info"]["describe"] = media.describe()
    where = f"{media.step_name} {start:,}, {nbits} LSB{'s' if nbits > 1 else ''}"

    # 1. read the note
    try:
        raw = safe_run.extract(media.kind, stego_path, nbits, start)
    except (safe_run.ExtractTimeout, RuntimeError) as exc:
        return fail(0, NOT_FOUND, f"Nothing readable at {where} ({exc}).")
    if not raw:
        return fail(0, NOT_FOUND, f"Nothing hidden at {where} (length 0).")
    try:
        payload, signature = unpack_payload_package(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(0, "Cannot Verify", f"Found {len(raw)} bytes at {where}, but they don't unpack: {exc}.")
    if not isinstance(payload, dict) or not REQUIRED_FIELDS <= payload.keys():
        return fail(0, "Cannot Verify", "The note is missing fields (media ID, timestamp, hash, nonce, metadata).")
    out["payload"] = payload
    ok(0, f"Read {len(raw)} bytes at {where}: file ID {payload['media_id']}.")

    # 2. check the signature
    if not verify_signature(payload, signature, public_key):
        return fail(1, "Signature Invalid", "verify_signature() says no for this public key.")
    ok(1, "verify_signature() says yes for this public key.")

    # 3. check the file hash
    actual = compute_file_hash(stego_path)
    out["info"]["actual_hash"] = actual
    if not verify_media_integrity(stego_path, payload["file_hash"]):
        return fail(2, "Tampered", f"verify_media_integrity() says no: this file's hash is {actual[:12]}…, "
                                   f"the note has {payload['file_hash'][:12]}….")
    ok(2, f"verify_media_integrity() says yes: hash {actual[:12]}… matches.")

    out["verdict"], out["explanation"] = "Authentic", EXPLAIN["Authentic"]
    return out
