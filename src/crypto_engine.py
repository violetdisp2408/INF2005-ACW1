import json
import hashlib
import time
import secrets
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.padding import PSS, MGF1

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
    # Convert dict to deterministic JSON string bytes
    payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    
    # Generate RSA Signature
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Format package: [4 bytes payload len][payload bytes][signature bytes]
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
    """Re-computes current stego file hash and checks against embedded hash."""
    current_hash = compute_file_hash(stego_file_path)
    return current_hash == expected_hash

if __name__ == "__main__":
    # 1. Generate keys
    private_key, public_key = generate_key_pair()
    
    # 2. Mock payload setup
    dummy_payload = {
        "media_id": "PNG_TEST_001",
        "timestamp": 1700000000,
        "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "nonce": "a1b2c3d4",
        "metadata": "INF2005 Assignment"
    }
    
    # 3. Sign
    signed_bytes = sign_payload(dummy_payload, private_key)
    print(f"Total Signed Package Size: {len(signed_bytes)} bytes")
    
    # 4. Unpack & Verify
    extracted_dict, sig = unpack_payload_package(signed_bytes)
    is_valid = verify_signature(extracted_dict, sig, public_key)
    
    print(f"Extraction Successful: {extracted_dict['media_id']}")
    print(f"Signature Verification Result: {'AUTHENTIC' if is_valid else 'TAMPERED/INVALID'}")