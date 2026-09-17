import sys
import os
import numpy as np
from PIL import Image

# Automatically add project root to python path to prevent "No module named 'src'"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crypto_engine import (
    generate_key_pair, 
    save_public_key_to_file,
    load_public_key_from_file,
    create_payload_dict, 
    sign_payload, 
    unpack_payload_package, 
    verify_signature
)


def bytes_to_bits(data_bytes: bytes) -> str:
    """Converts a byte string into a binary bit string ('0's and '1's)."""
    return ''.join(f'{b:08b}' for b in data_bytes)

def bits_to_bytes(bit_string: str) -> bytes:
    """Converts a binary bit string back into raw bytes."""
    length = (len(bit_string) // 8) * 8
    byte_list = [int(bit_string[i:i+8], 2) for i in range(0, length, 8)]
    return bytes(byte_list)


# ==========================================
# 1. IMAGE LSB EMBEDDING
# ==========================================

def embed_payload_in_image(
    cover_image_path: str,
    payload_bytes: bytes,
    output_stego_path: str,
    bits_per_channel: int = 1,
    start_pixel_offset: int = 0
) -> str:
    if not (1 <= bits_per_channel <= 8):
        raise ValueError("bits_per_channel must be between 1 and 8.")
    
    img = Image.open(cover_image_path).convert('RGB')
    img_array = np.array(img, dtype=np.uint8)
    shape = img_array.shape
    
    flat_pixels = img_array.flatten()
    
    # 32-bit payload length header + payload bit stream
    payload_len_bits = f"{len(payload_bytes):032b}"
    full_bit_stream = payload_len_bits + bytes_to_bits(payload_bytes)
    
    # Capacity Check
    start_channel_index = start_pixel_offset * 3
    available_capacity_bits = (len(flat_pixels) - start_channel_index) * bits_per_channel
    
    if len(full_bit_stream) > available_capacity_bits:
        raise ValueError(
            f"Payload size ({len(full_bit_stream)} bits) exceeds "
            f"cover image capacity ({available_capacity_bits} bits)!"
        )
    
    bit_index = 0
    total_bits = len(full_bit_stream)
    channel_index = start_channel_index
    
    mask = ~((1 << bits_per_channel) - 1) & 0xFF
    
    while bit_index < total_bits:
        chunk = full_bit_stream[bit_index : bit_index + bits_per_channel]
        # Pad final chunk if remaining bits < bits_per_channel
        if len(chunk) < bits_per_channel:
            chunk = chunk.ljust(bits_per_channel, '0')
            
        chunk_val = int(chunk, 2)
        flat_pixels[channel_index] = (flat_pixels[channel_index] & mask) | chunk_val
        
        bit_index += bits_per_channel
        channel_index += 1
    
    stego_array = flat_pixels.reshape(shape)
    stego_img = Image.fromarray(stego_array, mode='RGB')
    stego_img.save(output_stego_path, format='PNG')
    
    return output_stego_path


# ==========================================
# 2. IMAGE LSB EXTRACTION
# ==========================================

def extract_payload_from_image(
    stego_image_path: str,
    bits_per_channel: int = 1,
    start_pixel_offset: int = 0
) -> bytes:
    img = Image.open(stego_image_path).convert('RGB')
    flat_pixels = np.array(img, dtype=np.uint8).flatten()
    
    channel_index = start_pixel_offset * 3
    bit_mask = (1 << bits_per_channel) - 1
    
    # Extract raw bit stream from channels
    extracted_bit_stream = ""
    
    # Read first 32 bits (4 bytes) to determine payload length
    while len(extracted_bit_stream) < 32:
        val = flat_pixels[channel_index] & bit_mask
        extracted_bit_stream += f"{val:0{bits_per_channel}b}"
        channel_index += 1
        
    payload_length_bytes = int(extracted_bit_stream[:32], 2)
    total_required_bits = 32 + (payload_length_bytes * 8)
    
    # Read remaining bits up to total_required_bits
    while len(extracted_bit_stream) < total_required_bits:
        val = flat_pixels[channel_index] & bit_mask
        extracted_bit_stream += f"{val:0{bits_per_channel}b}"
        channel_index += 1
        
    payload_bits = extracted_bit_stream[32:total_required_bits]
    return bits_to_bytes(payload_bits)


# ==========================================
# 3. UNIT TESTS
# ==========================================

def run_tests():
    print("==================================================")
    print("      RUNNING INF2005 STEGANOGRAPHY TESTS        ")
    print("==================================================\n")

    if not os.path.exists("sample.png"):
        print("[!] ERROR: 'sample.png' not found in root folder.")
        print("Please place a PNG image named 'sample.png' in your project root folder.")
        return

    print("[1] Generating RSA Key Pairs...")
    private_key_A, public_key_A = generate_key_pair()
    private_key_B, public_key_B = generate_key_pair()
    
    save_public_key_to_file(public_key_A, "keys/public_key.pem")
    print("    -> Saved legitimate public key to 'keys/public_key.pem'")

    print("\n[2] Creating and Signing Payload...")
    payload_dict = create_payload_dict(
        media_id="PNG_TEST_001", 
        file_path="sample.png", 
        custom_metadata="SIT INF2005 Assignment"
    )
    signed_bytes = sign_payload(payload_dict, private_key_A)
    print(f"    -> Payload signed. Package size: {len(signed_bytes)} bytes")

    print("\n[3] Embedding Payload into 'sample.png'...")
    embed_payload_in_image(
        cover_image_path="sample.png",
        payload_bytes=signed_bytes,
        output_stego_path="stego_sample.png",
        bits_per_channel=2,      # 2 LSBs
        start_pixel_offset=500   # Custom start location
    )
    print("    -> Successfully created 'stego_sample.png'")

    print("\n--------------------------------------------------")
    print(" TEST CASE 1: POSITIVE TEST (Valid Public Key)")
    print("--------------------------------------------------")
    
    extracted_bytes = extract_payload_from_image(
        stego_image_path="stego_sample.png",
        bits_per_channel=2,
        start_pixel_offset=500
    )
    extracted_dict, sig = unpack_payload_package(extracted_bytes)
    
    loaded_pub_key = load_public_key_from_file("keys/public_key.pem")
    is_valid_1 = verify_signature(extracted_dict, sig, loaded_pub_key)
    
    print(f"Media ID : {extracted_dict['media_id']}")
    print(f"Result   : {'[PASS] AUTHENTIC' if is_valid_1 else '[FAIL] UNEXPECTED REJECTION'}")

    print("\n--------------------------------------------------")
    print(" TEST CASE 2: NEGATIVE TEST (Wrong Public Key)")
    print("--------------------------------------------------")
    
    is_valid_2 = verify_signature(extracted_dict, sig, public_key_B)
    
    print(f"Result   : {'[FAIL] SIGNATURE INVALID (EXPECTED BEHAVIOR)' if not is_valid_2 else '[FAIL] INCORRECTLY ACCEPTED'}")
    print("==================================================\n")

if __name__ == "__main__":
    run_tests()