"""Optional password on the message, so a custom message stays confidential.

The signature and hash only protect integrity: anyone who finds the note can read it. With a
password, the message is encrypted before it goes into the note (AES-256-GCM, key from the
password with PBKDF2-HMAC-SHA256), so only someone with the password can read it. The
encrypted text is what gets signed, so tampering with it still shows as Signature Invalid.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PREFIX = "ENC1:"
ITERATIONS = 200_000


def _key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode("utf-8"))


def is_locked(text) -> bool:
    return isinstance(text, str) and text.startswith(PREFIX)


def lock(text: str, password: str) -> str:
    """Returns "ENC1:" + base64(salt | nonce | ciphertext)."""
    salt, nonce = os.urandom(16), os.urandom(12)
    sealed = AESGCM(_key(password, salt)).encrypt(nonce, text.encode("utf-8"), None)
    return PREFIX + base64.b64encode(salt + nonce + sealed).decode("ascii")


def unlock(locked: str, password: str) -> str:
    """Decrypts a locked message. Raises ValueError for a wrong password or damaged text."""
    try:
        raw = base64.b64decode(locked[len(PREFIX):], validate=True)
        salt, nonce, sealed = raw[:16], raw[16:28], raw[28:]
        return AESGCM(_key(password, salt)).decrypt(nonce, sealed, None).decode("utf-8")
    except (InvalidTag, ValueError) as exc:
        raise ValueError("Wrong password (or the message is damaged).") from exc


def locked_len(n_bytes: int) -> int:
    """Length of the locked text for a message of n_bytes (UTF-8)."""
    return len(PREFIX) + 4 * -(-(16 + 12 + n_bytes + 16) // 3)
