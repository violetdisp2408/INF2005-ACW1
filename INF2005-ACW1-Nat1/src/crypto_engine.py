import json
import hashlib
import time
import secrets
import os
import numpy as np
from PIL import Image
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

# ==========================================
# 1. KEY MANAGEMENT (RSA 2048)
# ==========================================

def generate_key_pair():
    """Generates an RSA Private and Public Key Pair."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()
    return private_key, public_key

def serialize_public_key(public_key) -> bytes:
    """Converts a Public Key object to PEM byte format for saving/sharing."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

def deserialize_public_key(pem_bytes: bytes):
    """Loads a Public Key object from PEM bytes."""
    return serialization.load_pem_public_key(pem_bytes)

def save_public_key_to_file(public_key, file_path: str = "keys/public_key.pem"):
    """Saves a Public Key to a .pem file on disk."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    pem_bytes = serialize_public_key(public_key)
    with open(file_path, "wb") as f:
        f.write(pem_bytes)

def load_public_key_from_file(file_path: str = "keys/public_key.pem"):
    """Loads a Public Key from a .pem file on disk."""
    with open(file_path, "rb") as f:
        pem_bytes = f.read()
    return deserialize_public_key(pem_bytes)


# ==========================================
# 2. HASHING (FILE INTEGRITY)
# ==========================================

def compute_file_hash(file_path: str) -> str:
    """Computes SHA-256 hash of any input file (PNG or WAV)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_image_pixel_hash(file_path: str) -> str | None:
    """SHA-256 of the RGB pixels. None when the file is not an image."""
    try:
        img = Image.open(file_path).convert("RGB")
        pixels = np.array(img, dtype=np.uint8)
    except Exception:
        return None
    return hashlib.sha256(pixels.tobytes()).hexdigest()


# ==========================================
# 3. PAYLOAD CREATION & SIGNING
# ==========================================

def create_payload_dict(media_id: str, file_path: str, custom_metadata: str = "") -> dict:
    """
    Creates a standardized verification payload dictionary containing:
    Media ID, Timestamp, File SHA-256 Hash, Nonce, and Metadata.
    """
    return {
        "media_id": media_id,
        "timestamp": int(time.time()),
        "file_hash": compute_file_hash(file_path),
        "nonce": secrets.token_hex(8),  # Random hex to prevent replay attacks
        "metadata": custom_metadata
    }

def sign_payload(payload_dict: dict, private_key) -> bytes:
    """
    Converts payload dictionary to JSON bytes, signs it using RSA Private Key,
    and returns a combined byte package ready for steganographic embedding.
    """
    payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    payload_len = len(payload_bytes).to_bytes(4, byteorder='big')
    return payload_len + payload_bytes + signature


# ==========================================
# 4. EXTRACTION & VERIFICATION LOGIC
# ==========================================

def unpack_payload_package(raw_bytes: bytes) -> tuple[dict, bytes]:
    """Separates raw extracted bytes back into payload dictionary and signature."""
    payload_len = int.from_bytes(raw_bytes[:4], byteorder='big')
    payload_bytes = raw_bytes[4 : 4 + payload_len]
    signature_bytes = raw_bytes[4 + payload_len :]
    
    payload_dict = json.loads(payload_bytes.decode('utf-8'))
    return payload_dict, signature_bytes

def verify_signature(payload_dict: dict, signature: bytes, public_key) -> bool:
    """Verifies that the payload was signed by the legitimate Private Key owner."""
    try:
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        public_key.verify(
            signature,
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False

def verify_media_integrity(stego_file_path: str, expected_hash: str) -> bool:
    """Checks the embedded hash against the file, or against the photo pixels.

    A note hidden in the least significant bits changes the file, so that hash
    does not match. A photo that was left unedited stores a hash of the pixels
    instead, and that still matches because the picture itself did not change.
    """
    if compute_file_hash(stego_file_path) == expected_hash:
        return True
    pixel_hash = compute_image_pixel_hash(stego_file_path)
    return pixel_hash is not None and pixel_hash == expected_hash