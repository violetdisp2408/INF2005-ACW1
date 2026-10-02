"""Loads or creates the RSA key pair used by the GUI."""

import hashlib
import os

from cryptography.hazmat.primitives import serialization

from src.crypto_engine import (
    deserialize_public_key,
    generate_key_pair,
    load_public_key_from_file,
    save_public_key_to_file,
    serialize_public_key,
)

# kept in instance/ so the repo's keys/public_key.pem is never overwritten
KEY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "keys")
PRIVATE_PATH = os.path.join(KEY_DIR, "private_key.pem")
PUBLIC_PATH = os.path.join(KEY_DIR, "public_key.pem")


def fingerprint(public_key) -> str:
    """Returns a short ID for checking a public key."""
    digest = hashlib.sha256(serialize_public_key(public_key)).hexdigest()[:16]
    return " ".join(digest[i:i + 4] for i in range(0, 16, 4))


def new_pair():
    """Creates and saves a new key pair."""
    os.makedirs(KEY_DIR, exist_ok=True)
    private_key, public_key = generate_key_pair()
    with open(PRIVATE_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    try:
        os.chmod(PRIVATE_PATH, 0o600)
    except OSError:
        pass
    save_public_key_to_file(public_key, PUBLIC_PATH)
    return private_key, public_key


def load_pair():
    """Loads the saved key pair, or creates one."""
    if not (os.path.exists(PRIVATE_PATH) and os.path.exists(PUBLIC_PATH)):
        return new_pair()
    with open(PRIVATE_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    return private_key, load_public_key_from_file(PUBLIC_PATH)


def public_from_upload(pem_bytes: bytes):
    """Reads an uploaded public key."""
    try:
        return deserialize_public_key(pem_bytes)
    except Exception as exc:
        raise ValueError("That file isn't a valid public key (.pem).") from exc
